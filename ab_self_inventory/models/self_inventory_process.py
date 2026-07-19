import logging

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.translate import _


_logger = logging.getLogger(__name__)

REQUESTED_STOCK_SYNC_CHUNK_SIZE = 800


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


def _get_process_branch_eplus_serial(branch):
    raw_serial = str(branch.eplus_serial or '').replace(',', '').strip()
    if not raw_serial:
        raise ValidationError(_("Branch %s has no e-plus serial.") % branch.display_name)
    try:
        return int(raw_serial)
    except ValueError as error:
        raise ValidationError(
            _("Branch %s has invalid e-plus serial: %s") % (branch.display_name, branch.eplus_serial)
        ) from error


class SelfInventoryProcess(models.Model):
    _name = 'ab_self_inventory_process'
    _inherit = ['ab_eplus_connect']
    _description = 'Self Inventory Process'
    _order = 'id desc'

    name = fields.Char(default='New', readonly=True, copy=False)
    request_id = fields.Many2one('ab_self_inventory_request', readonly=True, index=True, ondelete='set null')
    requester_id = fields.Many2one('res.users', readonly=True, index=True)
    branch_id = fields.Many2one('ab_store', string='Branch', required=True, readonly=True, index=True)
    receiver_id = fields.Many2one('res.users', string='Received By')
    deadline = fields.Datetime(readonly=True)
    request_note = fields.Text(readonly=True)
    branch_note = fields.Text()
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('in_progress', 'In Progress'),
            ('submitted', 'Submitted'),
            ('cancelled', 'Cancelled'),
        ],
        default='in_progress',
        required=True,
        index=True,
    )
    line_ids = fields.One2many('ab_self_inventory_process_line', 'process_id', string='Inventory Lines')
    line_count = fields.Integer(compute='_compute_line_count')
    counted_line_count = fields.Integer(compute='_compute_implementation_progress')
    pending_line_count = fields.Integer(compute='_compute_implementation_progress')
    implementation_percent = fields.Float(
        string='Implementation %',
        compute='_compute_implementation_progress',
        digits=(5, 2),
    )
    submitted_date = fields.Datetime(readonly=True, copy=False)
    can_sync_requested_stock = fields.Boolean(compute='_compute_can_sync_requested_stock')
    shortage_qty = fields.Float(string='Shortage Cost', compute='_compute_totals', digits=(12, 2))
    extra_qty = fields.Float(string='Extra Cost', compute='_compute_totals', digits=(12, 2))
    requested_total_cost = fields.Float(
        string='Requested Products Cost',
        compute='_compute_totals',
        digits=(12, 2),
    )
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
            if vals.get('branch_id') and not vals.get('receiver_id'):
                vals['receiver_id'] = self._get_branch_receiver_user_id(vals['branch_id'])
        return super().create(vals_list)

    @api.model
    def _get_branch_receiver_user_id(self, branch_id):
        if not branch_id:
            return False
        department = self.env['ab_hr_department'].sudo().search([
            ('store_id', '=', branch_id),
            ('user_id', '!=', False),
        ], limit=1)
        return department.user_id.id if department else False

    @api.depends(
        'line_ids.shortage_qty',
        'line_ids.extra_qty',
        'line_ids.requested',
        'line_ids.system_qty',
        'line_ids.unit_cost',
    )
    def _compute_totals(self):
        for rec in self:
            rec.shortage_qty = sum(rec.line_ids.mapped('shortage_qty'))
            rec.extra_qty = sum(rec.line_ids.mapped('extra_qty'))
            rec.requested_total_cost = sum(
                (line.system_qty or 0.0) * (line.unit_cost or 0.0)
                for line in rec.line_ids
                if line.requested
            )

    @api.depends('line_ids')
    def _compute_line_count(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)

    @api.depends(
        'line_ids.is_counted',
        'line_ids.actual_qty',
        'line_ids.explanation',
    )
    def _compute_implementation_progress(self):
        for rec in self:
            metrics = rec._get_implementation_metrics()
            rec.counted_line_count = metrics['counted']
            rec.pending_line_count = metrics['pending']
            rec.implementation_percent = metrics['percent']

    def _get_implementation_metrics(self):
        self.ensure_one()
        total = len(self.line_ids)
        counted = len(self.line_ids.filtered(lambda line: line._is_inventory_counted()))
        return {
            'total': total,
            'counted': counted,
            'pending': max(total - counted, 0),
            'percent': round(counted / total * 100, 2) if total else 0.0,
        }

    @api.depends('state', 'branch_id')
    @api.depends_context('uid')
    def _compute_can_sync_requested_stock(self):
        user = self.env.user
        is_receiver = user.has_group('ab_self_inventory.group_ab_self_inventory_receiver')
        is_manager = user.has_group('ab_self_inventory.group_ab_self_inventory_manager')
        receiver_branches = user.ab_self_inventory_branch_ids
        for rec in self:
            rec.can_sync_requested_stock = bool(
                rec.state in ('draft', 'in_progress')
                and is_receiver
                and not is_manager
                and rec.branch_id
                and rec.branch_id in receiver_branches
            )

    @api.depends('branch_id', 'line_ids.product_id')
    def _compute_available_product_ids(self):
        for rec in self:
            rec.available_product_ids = rec._get_branch_stock_products()

    def write(self, vals):
        auto_receiver = False
        if vals.get('branch_id') and 'receiver_id' not in vals:
            vals = dict(vals)
            vals['receiver_id'] = self._get_branch_receiver_user_id(vals['branch_id'])
            auto_receiver = True
        protected_fields = {'branch_id', 'request_id', 'requester_id', 'line_ids', 'branch_note'}
        if (
            'receiver_id' in vals
            and not auto_receiver
            and not self.env.context.get('ab_self_inventory_allow_receiver_write')
        ):
            raise ValidationError(_("Receiver is set automatically and cannot be changed manually."))
        if protected_fields.intersection(vals):
            for rec in self:
                if rec.state not in ('draft', 'in_progress'):
                    raise ValidationError(_("Only active self inventory processes can be changed."))
        return super().write(vals)

    def action_submit_process(self):
        for rec in self:
            if rec.state not in ('draft', 'in_progress'):
                continue
            if not rec.line_ids:
                raise ValidationError(_("Add at least one product line before submitting."))
            request = rec.sudo().request_id
            submitted_date = fields.Datetime.now()
            rec.with_context(ab_self_inventory_allow_receiver_write=True).write({
                'state': 'submitted',
                'submitted_date': submitted_date,
                'receiver_id': self.env.user.id,
            })
            if request:
                request.with_context(ab_self_inventory_allow_in_progress_manager_write=True).write({
                    'state': 'submitted',
                    'submitted_date': submitted_date,
                })
        if (
            self.env.user.has_group('ab_self_inventory.group_ab_self_inventory_receiver')
            and not self.env.user.has_group('ab_self_inventory.group_ab_self_inventory_manager')
        ):
            return {
                'type': 'ir.actions.act_window',
                'name': _('Self Inventory Processes'),
                'res_model': 'ab_self_inventory_process',
                'view_mode': 'list,kanban,form',
                'domain': [('state', 'in', ['in_progress', 'submitted'])],
                'context': {'create': False},
            }
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
        existing_product_ids = set(self.line_ids.mapped('product_id').ids)
        return products.browse(product_ids).filtered(lambda product: product.id not in existing_product_ids)

    def _fetch_branch_stock_product_rows(self):
        self.ensure_one()
        with self.connect_eplus(param_str='?', charset='CP1256') as conn:
            with conn.cursor() as cursor:
                cursor.execute(BRANCH_PROCESS_STOCK_PRODUCTS_SQL, (_get_process_branch_eplus_serial(self.branch_id),))
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
                    (_get_process_branch_eplus_serial(self.branch_id), int(product.eplus_serial or 0), product_code),
                )
                row = cursor.fetchone()
                if not row:
                    return None
                if isinstance(row, dict):
                    stock_qty = row.get('system_qty') or row.get('SYSTEM_QTY')
                else:
                    stock_qty = row[0]
                return float(stock_qty or 0.0)

    def action_sync_requested_product_quantities(self):
        total_updated = 0
        total_unchanged = 0
        total_missing_identifiers = 0
        for rec in self:
            rec._check_can_sync_requested_product_quantities()
            requested_lines = rec.line_ids.filtered('requested')
            if not requested_lines:
                raise ValidationError(_("There are no requested products to sync."))

            quantities_by_line = {}
            try:
                for offset in range(0, len(requested_lines), REQUESTED_STOCK_SYNC_CHUNK_SIZE):
                    line_chunk = requested_lines[offset:offset + REQUESTED_STOCK_SYNC_CHUNK_SIZE]
                    quantities_by_line.update(rec._fetch_requested_line_stock_quantities(line_chunk))
            except ValidationError:
                raise
            except Exception as error:
                _logger.exception("Could not sync requested product quantities for self inventory process %s", rec.id)
                raise ValidationError(_("E-plus Connection Error: %s") % error) from error

            total_missing_identifiers += len(requested_lines) - len(quantities_by_line)
            for line in requested_lines:
                if line.id not in quantities_by_line:
                    continue
                new_qty = quantities_by_line[line.id]
                if abs((line.system_qty or 0.0) - new_qty) <= 0.0001:
                    total_unchanged += 1
                    continue
                line.with_context(ab_self_inventory_allow_system_qty_sync=True).write({'system_qty': new_qty})
                total_updated += 1

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Sync Complete'),
                'message': _(
                    'Requested product quantities synced. Updated: %(updated)d. Unchanged: %(unchanged)d. Missing identifiers: %(missing)d.'
                ) % {
                    'updated': total_updated,
                    'unchanged': total_unchanged,
                    'missing': total_missing_identifiers,
                },
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            },
        }

    def _check_can_sync_requested_product_quantities(self):
        self.ensure_one()
        if self.state not in ('draft', 'in_progress'):
            raise ValidationError(_("Submitted self inventory processes cannot sync E-stock quantities."))
        user = self.env.user
        if user.has_group('ab_self_inventory.group_ab_self_inventory_manager'):
            raise ValidationError(_("Managers cannot sync active branch self inventory quantities."))
        if not user.has_group('ab_self_inventory.group_ab_self_inventory_receiver'):
            raise ValidationError(_("Only the branch receiver can sync requested product quantities."))
        if self.branch_id not in user.ab_self_inventory_branch_ids:
            raise ValidationError(_("You can only sync self inventory quantities for your assigned branch."))
        if not self.branch_id.eplus_serial:
            raise ValidationError(_("Selected branch has no e-plus serial."))

    def _fetch_requested_line_stock_quantities(self, lines):
        self.ensure_one()
        lines = lines.filtered(lambda line: line.process_id == self)
        item_ids = sorted({
            int(line.eplus_item_id or 0)
            for line in lines
            if int(line.eplus_item_id or 0)
        })
        item_codes = sorted({
            (line.eplus_item_code or line.product_code or '').strip()
            for line in lines
            if (line.eplus_item_code or line.product_code or '').strip()
        })
        if not item_ids and not item_codes:
            return {}

        where_parts = []
        params = [_get_process_branch_eplus_serial(self.branch_id)]
        if item_ids:
            where_parts.append("main.itm_id IN (%s)" % ', '.join(['?'] * len(item_ids)))
            params.extend(item_ids)
        if item_codes:
            where_parts.append("ic.itm_code IN (%s)" % ', '.join(['?'] * len(item_codes)))
            params.extend(item_codes)

        stock_sql = """
            SELECT
                main.itm_id AS itm_id,
                ic.itm_code AS itm_code,
                SUM(main.itm_qty / NULLIF(ic.itm_unit1_unit3, 0)) AS system_qty
            FROM Item_Class_Store main WITH (NOLOCK)
            JOIN Item_Catalog ic WITH (NOLOCK) ON ic.itm_id = main.itm_id
            WHERE main.sto_id = ? AND (%s)
            GROUP BY main.itm_id, ic.itm_code
        """ % ' OR '.join(where_parts)

        stock_by_item_id = {}
        stock_by_code = {}
        with self.connect_eplus(param_str='?', charset='CP1256') as conn:
            with conn.cursor() as cursor:
                cursor.execute(stock_sql, params)
                columns = [column[0] for column in (cursor.description or [])]
                for row in cursor.fetchall():
                    if not isinstance(row, dict):
                        row = dict(zip(columns, row))
                    normalized = {str(key).lower(): value for key, value in row.items()}
                    item_id = int(normalized.get('itm_id') or 0)
                    item_code = str(normalized.get('itm_code') or '').strip()
                    system_qty = float(normalized.get('system_qty') or 0.0)
                    if item_id:
                        stock_by_item_id[item_id] = system_qty
                    if item_code:
                        stock_by_code[item_code] = system_qty

        result = {}
        for line in lines:
            item_id = int(line.eplus_item_id or 0)
            item_code = (line.eplus_item_code or line.product_code or '').strip()
            if not item_id and not item_code:
                continue
            result[line.id] = stock_by_item_id.get(item_id, stock_by_code.get(item_code, 0.0))
        return result

    def action_export_count_sheet(self):
        return self.env.ref('ab_self_inventory.action_self_inventory_count_sheet_xlsx').report_action(self)

    def action_open_import_wizard(self):
        self.ensure_one()
        return {
            'name': _('Import Actual Counts'),
            'type': 'ir.actions.act_window',
            'res_model': 'ab_self_inventory_import_wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_process_id': self.id},
        }

    def action_get_analytics(self):
        self.ensure_one()
        metrics = self._get_implementation_metrics()
        return {
            'branch_count': 1 if self.branch_id and metrics['total'] else 0,
            'total_products': metrics['total'],
            'selected_products': metrics['counted'],
            'counted_products': metrics['counted'],
            'pending_products': metrics['pending'],
            'matched_pct': round(metrics['percent']),
            'implementation_percent': metrics['percent'],
        }

    def action_get_branch_counts(self):
        self.ensure_one()
        if not self.branch_id:
            return []
        line_count = len(self.line_ids)
        return [{
            'id': self.branch_id.id,
            'name': self.branch_id.display_name or self.branch_id.name or '',
            'count': line_count,
        }] if line_count else []

    def _get_process_line_domain(self, search=None):
        self.ensure_one()
        domain = [('process_id', '=', self.id)]
        if search:
            domain += [
                '|', '|', '|',
                ('product_id.name', 'ilike', search),
                ('product_code', 'ilike', search),
                ('eplus_item_code', 'ilike', search),
                ('explanation', 'ilike', search),
            ]
        return domain

    def _get_process_line_grid_values(self, line):
        self.ensure_one()
        is_counted = line._is_inventory_counted()
        return {
            'id': line.id,
            'branch_id': self.branch_id.id,
            'branch_name': self.branch_id.display_name or self.branch_id.name or '',
            'selected': False,
            'requested': line.requested,
            'is_counted': is_counted,
            'product_name': line.product_id.display_name or line.product_id.name or '' if line.product_id else '',
            'product_code': line.product_code or '',
            'eplus_item_code': line.eplus_item_code or '',
            'system_qty': line.system_qty,
            # Keep untouched quantities blank so entering a real zero triggers
            # a change and marks the item as counted.
            'actual_qty': line.actual_qty if is_counted else False,
            'difference_qty': line.difference_qty,
            'shortage_qty': line.shortage_qty,
            'extra_qty': line.extra_qty,
            'explanation': line.explanation or '',
        }

    def action_get_grouped_rows(self, search=None, limit=50, branch_id=None, branch_ids=None):
        self.ensure_one()
        domain = self._get_process_line_domain(search=search)
        Line = self.env['ab_self_inventory_process_line']
        lines = Line.search(domain, limit=limit, order='requested DESC, product_id asc')
        total = Line.search_count(domain)
        if not total:
            return []
        return [{
            'branch_id': self.branch_id.id,
            'branch_name': self.branch_id.display_name or self.branch_id.name or '',
            'rows': [self._get_process_line_grid_values(line) for line in lines],
            'count': len(lines),
            'total': total,
        }]

    def action_get_grid_rows(self, branch_id=None, branch_ids=None, search=None, offset=0, limit=50, sort_by='product_name', sort_order='asc'):
        self.ensure_one()
        domain = self._get_process_line_domain(search=search)
        sort_map = {
            'product_id': 'product_id',
            'product_name': 'product_id',
            'product_code': 'product_code',
            'eplus_item_code': 'eplus_item_code',
            'system_qty': 'system_qty',
            'actual_qty': 'actual_qty',
            'difference_qty': 'difference_qty',
            'shortage_qty': 'shortage_qty',
            'extra_qty': 'extra_qty',
            'requested': 'requested',
        }
        sort_field = sort_map.get(sort_by, 'product_id')
        sort_order = sort_order if sort_order in ('asc', 'desc') else 'asc'
        offset = max(0, int(offset or 0))
        limit = max(1, min(int(limit or 50), 500))
        order = '%s %s, id asc' % (sort_field, sort_order)
        Line = self.env['ab_self_inventory_process_line']
        lines = Line.search(domain, offset=offset, limit=limit, order=order)
        total = Line.search_count(domain)
        return {
            'rows': [self._get_process_line_grid_values(line) for line in lines],
            'total': total,
            'selected_total': 0,
        }

    def action_update_process_line(self, line_id, values):
        self.ensure_one()
        self._check_can_update_process_line_grid()
        values = values or {}
        line = self.env['ab_self_inventory_process_line'].browse(line_id).exists()
        if not line or line.process_id != self:
            raise ValidationError(_("Self inventory line was not found."))
        allowed_fields = {'actual_qty', 'explanation'}
        clean_values = {field: values[field] for field in allowed_fields if field in values}
        if 'actual_qty' in clean_values:
            try:
                clean_values['actual_qty'] = float(clean_values['actual_qty'] or 0.0)
            except (TypeError, ValueError) as error:
                raise ValidationError(_("Actual quantity must be numeric.")) from error
        if 'explanation' in clean_values:
            clean_values['explanation'] = clean_values['explanation'] or False
        if not clean_values:
            return {'row': self._get_process_line_grid_values(line)}
        line.write(clean_values)
        return {'row': self._get_process_line_grid_values(line)}

    def _check_can_update_process_line_grid(self):
        self.ensure_one()
        if self.state not in ('draft', 'in_progress'):
            raise ValidationError(_("Only active self inventory process lines can be changed."))
        user = self.env.user
        if user.has_group('ab_self_inventory.group_ab_self_inventory_manager'):
            raise ValidationError(_("Managers cannot edit active branch self inventory quantities."))
        if not user.has_group('ab_self_inventory.group_ab_self_inventory_receiver'):
            raise ValidationError(_("Only the branch receiver can edit active self inventory quantities."))
        if self.branch_id not in user.ab_self_inventory_branch_ids:
            raise ValidationError(_("You can only edit self inventory quantities for your assigned branch."))


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
    unit_cost = fields.Float(digits=(12, 2), default=0.0)
    actual_qty = fields.Float(digits=(12, 3))
    difference_qty = fields.Float(compute='_compute_difference_qty', digits=(12, 3), store=True)
    shortage_qty = fields.Float(string='Shortage Cost', compute='_compute_difference_qty', digits=(12, 2), store=True)
    extra_qty = fields.Float(string='Extra Cost', compute='_compute_difference_qty', digits=(12, 2), store=True)
    explanation = fields.Char()
    is_counted = fields.Boolean(
        string='Counted',
        default=False,
        readonly=True,
        copy=False,
        help='Set when an actual quantity is entered, including a counted quantity of zero.',
    )

    @api.model_create_multi
    def create(self, vals_list):
        self._check_duplicate_products(vals_list)
        for vals in vals_list:
            process = self.env['ab_self_inventory_process'].browse(vals.get('process_id')).exists()
            if process and process.state not in ('draft', 'in_progress'):
                raise ValidationError(_("Only active self inventory processes can receive new lines."))
            self._prepare_product_values(vals)
            if 'actual_qty' in vals:
                vals['is_counted'] = True
        return super().create(vals_list)

    def write(self, vals):
        mark_counted = 'actual_qty' in vals
        for rec in self:
            if rec.process_id.state not in ('draft', 'in_progress'):
                raise ValidationError(_("Only active self inventory process lines can be changed."))
            rec._check_locked_fields(vals)
        if mark_counted:
            vals = dict(vals, is_counted=True)
        return super().write(vals)

    def unlink(self):
        for rec in self:
            if rec.process_id.state not in ('draft', 'in_progress'):
                raise ValidationError(_("Only active self inventory process lines can be deleted."))
            if rec.requested:
                raise ValidationError(_("Requested self inventory products cannot be deleted."))
        return super().unlink()

    def action_delete_manual_line(self):
        self.unlink()
        return True

    @api.model
    def _check_duplicate_products(self, vals_list):
        incoming_by_process = {}
        for vals in vals_list:
            process_id = vals.get('process_id')
            product_id = vals.get('product_id')
            if not process_id or not product_id:
                continue
            key = (process_id, product_id)
            if key in incoming_by_process:
                raise ValidationError(_("already exists product"))
            incoming_by_process[key] = True

        if not incoming_by_process:
            return
        domain = [
            ('process_id', 'in', list({process_id for process_id, product_id in incoming_by_process})),
            ('product_id', 'in', list({product_id for process_id, product_id in incoming_by_process})),
        ]
        for line in self.search(domain):
            if (line.process_id.id, line.product_id.id) in incoming_by_process:
                raise ValidationError(_("already exists product"))

    def _check_locked_fields(self, vals):
        locked_fields = {
            'process_id',
            'product_id',
            'eplus_item_id',
            'eplus_item_code',
            'requested',
            'system_qty',
            'unit_cost',
            'is_counted',
        }
        if self.env.context.get('ab_self_inventory_allow_system_qty_sync'):
            locked_fields.discard('system_qty')
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
                vals.setdefault('unit_cost', product.default_cost or product.default_price or 0.0)
                process = self.env['ab_self_inventory_process'].browse(vals.get('process_id')).exists()
                if process and not vals.get('requested'):
                    system_qty = process._get_branch_product_stock_qty(product)
                    if system_qty is None:
                        raise ValidationError(_("Selected product is not available in this branch stock."))
                    vals['system_qty'] = system_qty

    @api.depends('system_qty', 'actual_qty', 'unit_cost', 'is_counted', 'explanation')
    def _compute_difference_qty(self):
        for rec in self:
            if not rec._is_inventory_counted():
                rec.difference_qty = 0.0
                rec.shortage_qty = 0.0
                rec.extra_qty = 0.0
                continue
            difference = (rec.actual_qty or 0.0) - (rec.system_qty or 0.0)
            rec.difference_qty = difference
            rec.shortage_qty = abs(difference) * (rec.unit_cost or 0.0) if difference < 0 else 0.0
            rec.extra_qty = difference * (rec.unit_cost or 0.0) if difference > 0 else 0.0

    def _is_inventory_counted(self):
        self.ensure_one()
        # The explicit flag preserves a valid counted quantity of zero. The
        # other values keep existing records compatible without a data hook.
        return bool(self.is_counted or self.actual_qty or self.explanation)

    @api.onchange('product_id')
    def _onchange_product_id(self):
        for rec in self:
            if rec.product_id:
                duplicate_line = rec.process_id.line_ids.filtered(
                    lambda line: line != rec and line.product_id == rec.product_id
                )
                if duplicate_line:
                    rec.product_id = False
                    rec.eplus_item_id = 0
                    rec.eplus_item_code = False
                    rec.unit_cost = 0.0
                    rec.system_qty = 0.0
                    return {
                        'warning': {
                            'title': _("Duplicate Product"),
                            'message': _("already exists product"),
                        }
                    }
                rec.eplus_item_id = rec.product_id.eplus_serial or 0
                rec.eplus_item_code = rec.product_id.code or ''
                rec.unit_cost = rec.product_id.default_cost or rec.product_id.default_price or 0.0
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
            if rec.actual_qty < 0:
                raise ValidationError(_("Actual quantity cannot be negative."))
