import logging

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.translate import _


_logger = logging.getLogger(__name__)


BRANCH_PROCESS_STOCK_PRODUCTS_SQL = """
    SELECT
        main.itm_id AS itm_id,
        ic.itm_code AS itm_code
    FROM Item_Class_Store main WITH (NOLOCK)
    JOIN Item_Catalog ic WITH (NOLOCK) ON ic.itm_id = main.itm_id
    WHERE main.sto_id = ?
    GROUP BY main.itm_id, ic.itm_code
    HAVING SUM(main.itm_qty) <> 0
"""

BRANCH_PROCESS_PRODUCT_STOCK_SQL = """
    SELECT
        SUM(main.itm_qty / NULLIF(ic.itm_unit1_unit3, 0)) AS system_qty
    FROM Item_Class_Store main WITH (NOLOCK)
    JOIN Item_Catalog ic WITH (NOLOCK) ON ic.itm_id = main.itm_id
    WHERE main.sto_id = ? AND (main.itm_id = ? OR ic.itm_code = ?)
    HAVING SUM(main.itm_qty) <> 0
"""


class SelfInventoryProcess(models.Model):
    _name = 'ab_self_inventory_process'
    _inherit = ['ab_eplus_connect']
    _description = 'Self Inventory Process'
    _order = 'id desc'

    name = fields.Char(default='New', readonly=True, copy=False)
    request_id = fields.Many2one('ab_self_inventory_request', readonly=True, index=True, ondelete='set null')
    requester_id = fields.Many2one('res.users', readonly=True, index=True)
    branch_id = fields.Many2one('ab_store', string='Branch', required=True, readonly=True, index=True)
    receiver_id = fields.Many2one('res.users', string='Received By', default=lambda self: self.env.user)
    request_note = fields.Text(readonly=True)
    branch_note = fields.Text()
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('submitted', 'Submitted'),
            ('cancelled', 'Cancelled'),
        ],
        default='draft',
        required=True,
        index=True,
    )
    line_ids = fields.One2many('ab_self_inventory_process_line', 'process_id', string='Inventory Lines')
    submitted_date = fields.Datetime(readonly=True, copy=False)
    shortage_qty = fields.Float(compute='_compute_totals', digits=(12, 3))
    extra_qty = fields.Float(compute='_compute_totals', digits=(12, 3))
    available_product_ids = fields.Many2many(
        'ab_product',
        compute='_compute_available_product_ids',
        string='Branch Stock Products',
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('ab_self_inventory_process') or 'New'
        return super().create(vals_list)

    @api.depends('line_ids.shortage_qty', 'line_ids.extra_qty')
    def _compute_totals(self):
        for rec in self:
            rec.shortage_qty = sum(rec.line_ids.mapped('shortage_qty'))
            rec.extra_qty = sum(rec.line_ids.mapped('extra_qty'))

    def _compute_available_product_ids(self):
        for rec in self:
            rec.available_product_ids = rec._get_branch_stock_products()

    def write(self, vals):
        protected_fields = {'branch_id', 'request_id', 'requester_id', 'line_ids', 'branch_note'}
        if protected_fields.intersection(vals):
            for rec in self:
                if rec.state != 'draft':
                    raise ValidationError(_("Only draft self inventory processes can be changed."))
        return super().write(vals)

    def action_submit_process(self):
        for rec in self:
            if rec.state != 'draft':
                continue
            if not rec.line_ids:
                raise ValidationError(_("Add at least one product line before submitting."))
            missing_actual = rec.line_ids.filtered(lambda line: not line.actual_qty_set)
            if missing_actual:
                raise ValidationError(_("Set actual quantity for all self inventory lines before submitting."))
            rec.write({
                'state': 'submitted',
                'submitted_date': fields.Datetime.now(),
                'receiver_id': self.env.user.id,
            })
        return True

    def action_cancel(self):
        for rec in self:
            if rec.state == 'submitted':
                raise ValidationError(_("Submitted self inventory processes cannot be cancelled."))
            rec.state = 'cancelled'
        return True

    def action_reset_to_draft(self):
        for rec in self:
            if rec.state == 'submitted':
                raise ValidationError(_("Submitted self inventory processes cannot be reset to draft."))
            rec.state = 'draft'
        return True

    def _get_branch_stock_products(self):
        self.ensure_one()
        if not self.branch_id.eplus_serial:
            return self.env['ab_product']
        try:
            rows = self._fetch_branch_stock_product_rows()
        except Exception as ex:
            _logger.exception("Could not fetch branch stock products for self inventory process %s", self.id)
            return self.env['ab_product']

        item_ids = [row['itm_id'] for row in rows]
        item_codes = [row['itm_code'] for row in rows if row['itm_code']]
        products = self.env['ab_product'].sudo().with_context(active_test=False)
        products_by_serial = {
            int(product.eplus_serial or 0): product.id
            for product in products.search([('eplus_serial', 'in', item_ids)])
        }
        products_by_code = {
            (product.code or '').strip(): product.id
            for product in products.search([('code', 'in', item_codes)])
            if product.code
        }
        product_ids = []
        for row in rows:
            product_id = products_by_serial.get(row['itm_id']) or products_by_code.get(row['itm_code'])
            if product_id:
                product_ids.append(product_id)
        return products.browse(product_ids)

    def _fetch_branch_stock_product_rows(self):
        self.ensure_one()
        with self.connect_eplus(param_str='?', charset='CP1256') as conn:
            with conn.cursor() as cursor:
                cursor.execute(BRANCH_PROCESS_STOCK_PRODUCTS_SQL, (int(self.branch_id.eplus_serial),))
                columns = [column[0] for column in (cursor.description or [])]
                rows = []
                for row in cursor.fetchall():
                    if not isinstance(row, dict):
                        row = dict(zip(columns, row))
                    normalized = {str(key).lower(): value for key, value in row.items()}
                    rows.append({
                        'itm_id': int(normalized.get('itm_id') or 0),
                        'itm_code': str(normalized.get('itm_code') or '').strip(),
                    })
                return rows

    def _get_branch_product_stock_qty(self, product):
        self.ensure_one()
        product.ensure_one()
        product_code = (product.code or '').strip()
        if not self.branch_id.eplus_serial or (not product.eplus_serial and not product_code):
            return None
        with self.connect_eplus(param_str='?', charset='CP1256') as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    BRANCH_PROCESS_PRODUCT_STOCK_SQL,
                    (int(self.branch_id.eplus_serial), int(product.eplus_serial or 0), product_code),
                )
                row = cursor.fetchone()
                if not row:
                    return None
                if isinstance(row, dict):
                    stock_qty = row.get('system_qty') or row.get('SYSTEM_QTY')
                else:
                    stock_qty = row[0]
                return float(stock_qty or 0.0)


class SelfInventoryProcessLine(models.Model):
    _name = 'ab_self_inventory_process_line'
    _description = 'Self Inventory Process Line'
    _order = 'process_id desc, requested desc, product_id'

    process_id = fields.Many2one('ab_self_inventory_process', required=True, ondelete='cascade', index=True)
    product_id = fields.Many2one('ab_product', required=True, index=True)
    product_code = fields.Char(related='product_id.code', readonly=True)
    eplus_item_id = fields.Integer(string='E-plus Item ID', readonly=True, index=True)
    eplus_item_code = fields.Char(string='E-plus Item Code', readonly=True, index=True)
    requested = fields.Boolean(default=False, readonly=True)
    system_qty = fields.Float(string='E-stock Qty', digits=(12, 3), required=True, default=0.0)
    actual_qty = fields.Float(digits=(12, 3))
    actual_qty_set = fields.Boolean(string='Actual Qty Set')
    difference_qty = fields.Float(compute='_compute_difference_qty', digits=(12, 3), store=True)
    shortage_qty = fields.Float(compute='_compute_difference_qty', digits=(12, 3), store=True)
    extra_qty = fields.Float(compute='_compute_difference_qty', digits=(12, 3), store=True)
    explanation = fields.Char()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            process = self.env['ab_self_inventory_process'].browse(vals.get('process_id')).exists()
            if process and process.state != 'draft':
                raise ValidationError(_("Only draft self inventory processes can receive new lines."))
            self._prepare_product_values(vals)
        return super().create(vals_list)

    def write(self, vals):
        for rec in self:
            if rec.process_id.state != 'draft':
                raise ValidationError(_("Only draft self inventory process lines can be changed."))
            rec._check_locked_fields(vals)
        vals = dict(vals)
        return super().write(vals)

    def unlink(self):
        raise ValidationError(_("Self inventory products cannot be deleted after the request is received."))

    def _check_locked_fields(self, vals):
        locked_fields = {
            'process_id',
            'product_id',
            'eplus_item_id',
            'eplus_item_code',
            'requested',
            'system_qty',
        }
        if locked_fields.intersection(vals):
            raise ValidationError(_("Self inventory products cannot be changed after the request is received."))

    @api.model
    def _prepare_product_values(self, vals):
        product_id = vals.get('product_id')
        if product_id:
            product = self.env['ab_product'].browse(product_id).exists()
            if product:
                vals.setdefault('eplus_item_id', product.eplus_serial or 0)
                vals.setdefault('eplus_item_code', product.code or '')
                process = self.env['ab_self_inventory_process'].browse(vals.get('process_id')).exists()
                if process and not vals.get('requested'):
                    system_qty = process._get_branch_product_stock_qty(product)
                    if system_qty is None:
                        raise ValidationError(_("Selected product is not available in this branch stock."))
                    vals['system_qty'] = system_qty

    @api.depends('system_qty', 'actual_qty', 'actual_qty_set')
    def _compute_difference_qty(self):
        for rec in self:
            if not rec.actual_qty_set:
                rec.difference_qty = 0.0
                rec.shortage_qty = 0.0
                rec.extra_qty = 0.0
                continue
            difference = (rec.actual_qty or 0.0) - (rec.system_qty or 0.0)
            rec.difference_qty = difference
            rec.shortage_qty = abs(difference) if difference < 0 else 0.0
            rec.extra_qty = difference if difference > 0 else 0.0

    @api.onchange('product_id')
    def _onchange_product_id(self):
        for rec in self:
            if rec.product_id:
                rec.eplus_item_id = rec.product_id.eplus_serial or 0
                rec.eplus_item_code = rec.product_id.code or ''
                if rec.process_id and not rec.requested:
                    system_qty = rec.process_id._get_branch_product_stock_qty(rec.product_id)
                    if system_qty is None:
                        rec.product_id = False
                        rec.system_qty = 0.0
                        return {
                            'warning': {
                                'title': _("Branch Stock"),
                                'message': _("Selected product is not available in this branch stock."),
                            }
                        }
                    rec.system_qty = system_qty

    @api.constrains('actual_qty')
    def _check_actual_qty(self):
        for rec in self:
            if rec.actual_qty_set and rec.actual_qty < 0:
                raise ValidationError(_("Actual quantity cannot be negative."))
