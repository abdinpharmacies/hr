from datetime import date, datetime
from decimal import Decimal

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.translate import _


BRANCH_STOCK_SQL = """
    SELECT
        main.itm_id AS itm_id,
        ic.itm_code AS itm_code,
        SUM(main.itm_qty / NULLIF(ic.itm_unit1_unit3, 0)) AS system_qty
    FROM Item_Class_Store main WITH (NOLOCK)
    JOIN Item_Catalog ic WITH (NOLOCK) ON ic.itm_id = main.itm_id
    WHERE main.sto_id = ?
    GROUP BY main.itm_id, ic.itm_code
    HAVING SUM(main.itm_qty) <> 0
    ORDER BY ic.itm_code, main.itm_id
"""


class SelfInventoryRequest(models.Model):
    _name = 'ab_self_inventory_request'
    _inherit = ['ab_eplus_connect']
    _description = 'Self Inventory Request'
    _order = 'id desc'

    name = fields.Char(default='New', readonly=True, copy=False)
    requester_id = fields.Many2one('res.users', default=lambda self: self.env.user, required=True, readonly=True)
    branch_id = fields.Many2one(
        'ab_store',
        string='Branch',
        required=True,
        domain="[('store_type', '=', 'branch')]",
    )
    note = fields.Text()
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
    line_ids = fields.One2many('ab_self_inventory_request_line', 'request_id', string='Fetched Products')
    selected_line_count = fields.Integer(compute='_compute_selected_line_count')
    process_id = fields.Many2one('ab_self_inventory_process', readonly=True, copy=False)
    submitted_date = fields.Datetime(readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('ab_self_inventory_request') or 'New'
        return super().create(vals_list)

    @api.depends('line_ids.selected')
    def _compute_selected_line_count(self):
        for rec in self:
            rec.selected_line_count = len(rec.line_ids.filtered('selected'))

    def write(self, vals):
        protected_fields = {'branch_id', 'line_ids'}
        if protected_fields.intersection(vals):
            for rec in self:
                if rec.state != 'draft':
                    raise ValidationError(_("Only draft self inventory requests can be changed."))
        return super().write(vals)

    def action_fetch_branch_stock(self):
        for rec in self:
            rec._check_can_fetch_stock()
            rows = rec._fetch_branch_stock_rows()
            products_by_serial = rec._get_products_by_eplus_serial([row['itm_id'] for row in rows])
            products_by_code = rec._get_products_by_code([row['itm_code'] for row in rows if row['itm_code']])
            line_commands = [(5, 0, 0)]
            for row in rows:
                product = products_by_serial.get(row['itm_id'])
                matched_by = 'eplus_serial' if product else 'none'
                if not product and row['itm_code']:
                    product = products_by_code.get(row['itm_code'])
                    matched_by = 'code' if product else 'none'
                line_commands.append((0, 0, {
                    'product_id': product.id if product else False,
                    'eplus_item_id': row['itm_id'],
                    'eplus_item_code': row['itm_code'],
                    'system_qty': row['system_qty'],
                    'matched_by': matched_by,
                    'selected': bool(product),
                    'extra_data': row['extra_data'],
                }))
            rec.write({'line_ids': line_commands})
        return True

    def action_submit_request(self):
        for rec in self:
            if rec.state != 'draft':
                continue
            selected_lines = rec.line_ids.filtered(lambda line: line.selected and line.product_id)
            if not selected_lines:
                raise ValidationError(_("Select at least one matched product before submitting."))
            process = rec._create_process_from_request(selected_lines)
            rec.write({
                'state': 'submitted',
                'submitted_date': fields.Datetime.now(),
                'process_id': process.id,
            })
        return True

    def action_select_all_lines(self):
        for rec in self:
            rec._check_can_update_lines()
            rec.line_ids.write({'selected': True})
        return True

    def action_unselect_all_lines(self):
        for rec in self:
            rec._check_can_update_lines()
            rec.line_ids.write({'selected': False})
        return True

    def action_delete_selected_lines(self):
        for rec in self:
            rec._check_can_update_lines()
            rec.line_ids.filtered('selected').unlink()
        return True

    def action_delete_unselected_lines(self):
        for rec in self:
            rec._check_can_update_lines()
            rec.line_ids.filtered(lambda line: not line.selected).unlink()
        return True

    def action_cancel(self):
        for rec in self:
            if rec.process_id and rec.process_id.state != 'draft':
                raise ValidationError(_("You cannot cancel a request after the inventory process is submitted."))
            rec.state = 'cancelled'
        return True

    def action_reset_to_draft(self):
        for rec in self:
            if rec.process_id and rec.process_id.state != 'draft':
                raise ValidationError(_("You cannot reset a request after the inventory process is submitted."))
            rec.state = 'draft'
        return True

    def action_open_process(self):
        self.ensure_one()
        if not self.process_id:
            raise UserError(_("No self inventory process has been created yet."))
        return {
            'name': self.process_id.display_name,
            'type': 'ir.actions.act_window',
            'res_model': 'ab_self_inventory_process',
            'view_mode': 'form',
            'res_id': self.process_id.id,
        }

    def _check_can_fetch_stock(self):
        self.ensure_one()
        if self.state != 'draft':
            raise ValidationError(_("Only draft requests can fetch branch stock."))
        if not self.branch_id.eplus_serial:
            raise ValidationError(_("Selected branch has no e-plus serial."))

    def _check_can_update_lines(self):
        self.ensure_one()
        if self.state != 'draft':
            raise ValidationError(_("Only draft requests can update fetched product lines."))

    def _fetch_branch_stock_rows(self):
        self.ensure_one()
        with self.connect_eplus(param_str='?', charset='CP1256') as conn:
            with conn.cursor() as cursor:
                cursor.execute(BRANCH_STOCK_SQL, (int(self.branch_id.eplus_serial),))
                columns = [column[0] for column in (cursor.description or [])]
                return [self._normalize_branch_stock_row(row, columns) for row in cursor.fetchall()]

    @api.model
    def _normalize_branch_stock_row(self, row, columns):
        if not isinstance(row, dict):
            row = dict(zip(columns, row))
        normalized = {str(key).lower(): value for key, value in row.items()}
        return {
            'itm_id': int(normalized.get('itm_id') or 0),
            'itm_code': str(normalized.get('itm_code') or '').strip(),
            'system_qty': float(normalized.get('system_qty') or 0.0),
            'extra_data': {
                key: self._json_safe_value(value)
                for key, value in normalized.items()
                if key not in {'itm_id', 'itm_code', 'system_qty'}
            },
        }

    @api.model
    def _json_safe_value(self, value):
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        return value

    @api.model
    def _get_products_by_eplus_serial(self, item_ids):
        products = self.env['ab_product'].sudo().with_context(active_test=False).search([
            ('eplus_serial', 'in', item_ids),
        ])
        result = {}
        for product in products:
            result.setdefault(int(product.eplus_serial or 0), product)
        return result

    @api.model
    def _get_products_by_code(self, item_codes):
        products = self.env['ab_product'].sudo().with_context(active_test=False).search([
            ('code', 'in', item_codes),
        ])
        result = {}
        for product in products:
            code = (product.code or '').strip()
            if code:
                result.setdefault(code, product)
        return result

    def _create_process_from_request(self, selected_lines):
        self.ensure_one()
        Process = self.env['ab_self_inventory_process'].sudo()
        process = self.process_id
        vals = {
            'request_id': self.id,
            'requester_id': self.requester_id.id,
            'branch_id': self.branch_id.id,
            'request_note': self.note,
            'state': 'draft',
            'line_ids': [(5, 0, 0)] + [
                (0, 0, {
                    'product_id': line.product_id.id,
                    'eplus_item_id': line.eplus_item_id,
                    'eplus_item_code': line.eplus_item_code,
                    'system_qty': line.system_qty,
                    'requested': True,
                })
                for line in selected_lines
            ],
        }
        if process and process.state == 'draft':
            process.write(vals)
        else:
            process = Process.create(vals)
        return process


class SelfInventoryRequestLine(models.Model):
    _name = 'ab_self_inventory_request_line'
    _description = 'Self Inventory Request Line'
    _order = 'request_id desc, product_id, eplus_item_code'

    request_id = fields.Many2one('ab_self_inventory_request', required=True, ondelete='cascade', index=True)
    selected = fields.Boolean(default=True)
    product_id = fields.Many2one('ab_product', string='Product', index=True)
    product_code = fields.Char(related='product_id.code', readonly=True)
    eplus_item_id = fields.Integer(string='E-plus Item ID', readonly=True, index=True)
    eplus_item_code = fields.Char(string='E-plus Item Code', readonly=True, index=True)
    system_qty = fields.Float(string='E-stock Qty', digits=(12, 3), readonly=True)
    matched_by = fields.Selection(
        selection=[
            ('eplus_serial', 'E-plus ID'),
            ('code', 'Item Code'),
            ('none', 'Not Matched'),
        ],
        default='none',
        required=True,
        readonly=True,
    )
    note = fields.Char()
    extra_data = fields.Json(readonly=True)

    def write(self, vals):
        for rec in self:
            if rec.request_id.state != 'draft':
                raise ValidationError(_("Only draft self inventory request lines can be changed."))
        return super().write(vals)

    def unlink(self):
        for rec in self:
            if rec.request_id.state != 'draft':
                raise ValidationError(_("Only draft self inventory request lines can be deleted."))
        return super().unlink()
