from datetime import date, datetime
from decimal import Decimal
import re

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
    deadline = fields.Datetime()
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
    batch_id = fields.Many2one('ab_self_inventory_request_batch', readonly=True, copy=False, index=True)
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
            if not rows:
                raise ValidationError(_("No stock rows were returned from B-Connect for branch %s.") % rec.branch_id.display_name)
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
                    'selected': False,
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
            'deadline': self.deadline,
            'state': 'draft',
            'line_ids': [(5, 0, 0)] + [
                (0, 0, {
                    'product_id': line.product_id.id,
                    'eplus_item_id': line.eplus_item_id,
                    'eplus_item_code': line.eplus_item_code,
                    'system_qty': line.system_qty,
                    'unit_cost': line.product_id.default_cost or line.product_id.default_price or 0.0,
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
    selected = fields.Boolean(default=False)
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


class SelfInventoryRequestBatch(models.Model):
    _name = 'ab_self_inventory_request_batch'
    _inherit = ['ab_eplus_connect']
    _description = 'Self Inventory Request Batch'
    _order = 'id desc'

    name = fields.Char(default='New', readonly=True, copy=False)
    requester_id = fields.Many2one('res.users', default=lambda self: self.env.user, required=True, readonly=True)
    branch_ids = fields.Many2many(
        'ab_store',
        string='Branches',
        domain="[('store_type', '=', 'branch')]",
    )
    branch_governorate_name = fields.Char(string='Governorate Name Filter')
    governorate_branch_count = fields.Integer(compute='_compute_governorate_branch_count')
    deadline = fields.Datetime()
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
    line_ids = fields.One2many('ab_self_inventory_request_batch_line', 'batch_id', string='Fetched Products')
    request_ids = fields.One2many('ab_self_inventory_request', 'batch_id', readonly=True)
    process_ids = fields.Many2many('ab_self_inventory_process', compute='_compute_process_ids')
    product_codes_text = fields.Text(string='Product Codes')
    last_code_import_message = fields.Text(readonly=True, copy=False)
    selected_line_count = fields.Integer(compute='_compute_selected_line_count')
    line_count = fields.Integer(compute='_compute_line_count')
    request_count = fields.Integer(compute='_compute_request_count')
    process_count = fields.Integer(compute='_compute_process_count')
    submitted_date = fields.Datetime(readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('ab_self_inventory_request_batch') or 'New'
        return super().create(vals_list)

    @api.depends('line_ids.selected')
    def _compute_selected_line_count(self):
        for rec in self:
            rec.selected_line_count = len(rec.line_ids.filtered('selected'))

    @api.depends('line_ids')
    def _compute_line_count(self):
        for rec in self:
            rec.line_count = len(rec.line_ids.filtered(lambda line: line.matched_by != 'none'))

    @api.depends('branch_governorate_name')
    def _compute_governorate_branch_count(self):
        Store = self.env['ab_store'].sudo()
        for rec in self:
            if not (rec.branch_governorate_name or '').strip():
                rec.governorate_branch_count = 0
                continue
            rec.governorate_branch_count = Store.search_count(rec._get_governorate_branch_domain())

    @api.depends('request_ids')
    def _compute_request_count(self):
        for rec in self:
            rec.request_count = len(rec.request_ids)

    @api.depends('request_ids.process_id')
    def _compute_process_ids(self):
        for rec in self:
            rec.process_ids = rec.request_ids.mapped('process_id')

    @api.depends('process_ids')
    def _compute_process_count(self):
        for rec in self:
            rec.process_count = len(rec.process_ids)

    def write(self, vals):
        protected_fields = {
            'branch_ids',
            'branch_governorate_name',
            'deadline',
            'note',
            'line_ids',
            'product_codes_text',
        }
        if protected_fields.intersection(vals):
            for rec in self:
                if rec.state != 'draft':
                    raise ValidationError(_("Only draft self inventory request batches can be changed."))
        return super().write(vals)

    def action_fetch_branch_stocks(self):
        for rec in self:
            rec._check_can_fetch_stock()
            line_commands = [(5, 0, 0)]
            for branch in rec.branch_ids:
                rows = rec._fetch_branch_stock_rows(branch)
                if not rows:
                    raise ValidationError(_("No stock rows were returned from B-Connect for branch %s.") % branch.display_name)
                line_commands.extend(rec._prepare_batch_line_commands(branch, rows))
            rec.write({
                'line_ids': line_commands,
                'last_code_import_message': False,
            })
        return True

    def action_add_product_codes(self):
        for rec in self:
            rec._check_can_fetch_stock()
            rec._check_can_update_lines()
            requested_codes = rec._parse_product_codes()
            if not requested_codes:
                raise ValidationError(_("Enter at least one product code."))

            existing_keys = {
                (line.branch_id.id, (line.eplus_item_code or '').strip().upper())
                for line in rec.line_ids
                if line.eplus_item_code
            }
            requested_code_set = set(requested_codes)
            line_commands = []
            found_by_branch = {}
            missing_by_branch = {}
            for branch in rec.branch_ids:
                rows = rec._fetch_branch_stock_rows(branch)
                rows_by_code = {
                    row['itm_code'].strip().upper(): row
                    for row in rows
                    if row.get('itm_code')
                }
                found_codes = requested_code_set.intersection(rows_by_code)
                missing_codes = requested_code_set - found_codes
                found_by_branch[branch.display_name] = sorted(found_codes)
                missing_by_branch[branch.display_name] = sorted(missing_codes)

                rows_to_add = [
                    rows_by_code[code]
                    for code in requested_codes
                    if code in rows_by_code and (branch.id, code) not in existing_keys
                ]
                line_commands.extend(rec._prepare_batch_line_commands(branch, rows_to_add, selected=False))
                existing_keys.update((branch.id, code) for code in found_codes)

            if not line_commands:
                raise ValidationError(_("No new matching branch stock rows were found for the entered product codes."))

            rec.write({
                'line_ids': line_commands,
                'last_code_import_message': rec._format_code_import_message(found_by_branch, missing_by_branch),
            })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Product Codes Added'),
                'message': _('Matching product codes were added to the selected branch groups.'),
                'type': 'success',
                'sticky': False,
            },
        }

    def action_add_governorate_branches(self):
        for rec in self:
            rec._check_can_update_branches()
            if not (rec.branch_governorate_name or '').strip():
                raise ValidationError(_("Enter a governorate name before adding branches."))
            branches = self.env['ab_store'].sudo().search(rec._get_governorate_branch_domain(), order='name, code, id')
            if not branches:
                raise ValidationError(_("No branch stores were found with this governorate text and فرع in their name."))
            rec.write({'branch_ids': [(4, branch.id) for branch in branches]})
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Branches Added'),
                'message': _('All matching branch stores were added.'),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            },
        }

    def action_submit_batch(self):
        Request = self.env['ab_self_inventory_request']
        for rec in self:
            if rec.state != 'draft':
                continue
            selected_lines = rec.line_ids.filtered(lambda line: line.selected and line.product_id)
            if not selected_lines:
                raise ValidationError(_("Select at least one matched product before submitting."))

            for branch in selected_lines.mapped('branch_id'):
                branch_lines = selected_lines.filtered(lambda line: line.branch_id == branch)
                request = Request.create({
                    'batch_id': rec.id,
                    'branch_id': branch.id,
                    'deadline': rec.deadline,
                    'note': rec.note,
                    'line_ids': [
                        (0, 0, {
                            'selected': True,
                            'product_id': line.product_id.id,
                            'eplus_item_id': line.eplus_item_id,
                            'eplus_item_code': line.eplus_item_code,
                            'system_qty': line.system_qty,
                            'matched_by': line.matched_by,
                            'note': line.note,
                            'extra_data': line.extra_data,
                        })
                        for line in branch_lines
                    ],
                })
                request.action_submit_request()
                branch_lines.write({'request_id': request.id})
            rec.write({
                'state': 'submitted',
                'submitted_date': fields.Datetime.now(),
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
            if rec.request_ids.filtered(lambda request: request.process_id and request.process_id.state != 'draft'):
                raise ValidationError(_("You cannot cancel a batch after any inventory process is submitted."))
            rec.state = 'cancelled'
        return True

    def action_reset_to_draft(self):
        for rec in self:
            if rec.request_ids.filtered(lambda request: request.process_id and request.process_id.state != 'draft'):
                raise ValidationError(_("You cannot reset a batch after any inventory process is submitted."))
            rec.state = 'draft'
        return True

    def action_open_requests(self):
        self.ensure_one()
        return {
            'name': _('Self Inventory Requests'),
            'type': 'ir.actions.act_window',
            'res_model': 'ab_self_inventory_request',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.request_ids.ids)],
            'context': {'default_batch_id': self.id},
        }

    def action_open_processes(self):
        self.ensure_one()
        return {
            'name': _('Self Inventory Processes'),
            'type': 'ir.actions.act_window',
            'res_model': 'ab_self_inventory_process',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.process_ids.ids)],
        }

    def action_open_lines(self):
        self.ensure_one()
        return {
            'name': _('Batch Product Lines'),
            'type': 'ir.actions.act_window',
            'res_model': 'ab_self_inventory_request_batch_line',
            'view_mode': 'list,form',
            'domain': [('batch_id', '=', self.id), ('matched_by', '!=', 'none')],
            'context': {
                'default_batch_id': self.id,
                'search_default_group_branch': 1,
            },
        }

    def _check_can_fetch_stock(self):
        self.ensure_one()
        if self.state != 'draft':
            raise ValidationError(_("Only draft batches can fetch branch stock."))
        if not self.branch_ids:
            raise ValidationError(_("Select at least one branch before fetching stock."))
        missing_eplus = self.branch_ids.filtered(lambda branch: not branch.eplus_serial)
        if missing_eplus:
            raise ValidationError(
                _("These branches have no e-plus serial: %s") % ', '.join(missing_eplus.mapped('display_name'))
            )

    def _check_can_update_lines(self):
        self.ensure_one()
        if self.state != 'draft':
            raise ValidationError(_("Only draft batches can update fetched product lines."))

    def _check_can_update_branches(self):
        self.ensure_one()
        if self.state != 'draft':
            raise ValidationError(_("Only draft batches can update branches."))

    def _get_governorate_branch_domain(self):
        self.ensure_one()
        return [
            ('store_type', '=', 'branch'),
            ('name', 'ilike', (self.branch_governorate_name or '').strip()),
            ('name', 'ilike', 'فرع'),
        ]

    def _fetch_branch_stock_rows(self, branch):
        with self.connect_eplus(param_str='?', charset='CP1256') as conn:
            with conn.cursor() as cursor:
                cursor.execute(BRANCH_STOCK_SQL, (int(branch.eplus_serial),))
                columns = [column[0] for column in (cursor.description or [])]
                return [
                    self.env['ab_self_inventory_request']._normalize_branch_stock_row(row, columns)
                    for row in cursor.fetchall()
                ]

    def _prepare_batch_line_commands(self, branch, rows, selected=None):
        Request = self.env['ab_self_inventory_request']
        products_by_serial = Request._get_products_by_eplus_serial([row['itm_id'] for row in rows])
        products_by_code = Request._get_products_by_code([row['itm_code'] for row in rows if row['itm_code']])
        commands = []
        for row in rows:
            product = products_by_serial.get(row['itm_id'])
            matched_by = 'eplus_serial' if product else 'none'
            if not product and row['itm_code']:
                product = products_by_code.get(row['itm_code'])
                matched_by = 'code' if product else 'none'
            commands.append((0, 0, {
                'branch_id': branch.id,
                'product_id': product.id if product else False,
                'eplus_item_id': row['itm_id'],
                'eplus_item_code': row['itm_code'],
                'system_qty': row['system_qty'],
                'matched_by': matched_by,
                'selected': False if selected is None else selected and bool(product),
                'extra_data': row['extra_data'],
            }))
        return commands

    def _parse_product_codes(self):
        self.ensure_one()
        raw_codes = re.split(r'[\s,;]+', self.product_codes_text or '')
        codes = []
        seen = set()
        for raw_code in raw_codes:
            code = raw_code.strip().upper()
            if code and code not in seen:
                codes.append(code)
                seen.add(code)
        return codes

    @api.model
    def _format_code_import_message(self, found_by_branch, missing_by_branch):
        lines = []
        for branch_name in sorted(found_by_branch):
            found_codes = found_by_branch[branch_name]
            missing_codes = missing_by_branch.get(branch_name) or []
            lines.append(
                _("%(branch)s: added %(added_count)s code(s), missing %(missing_count)s code(s).") % {
                    'branch': branch_name,
                    'added_count': len(found_codes),
                    'missing_count': len(missing_codes),
                }
            )
            if missing_codes:
                lines.append(_("Missing: %s") % ', '.join(missing_codes))
        return '\n'.join(lines)


class SelfInventoryRequestBatchLine(models.Model):
    _name = 'ab_self_inventory_request_batch_line'
    _description = 'Self Inventory Request Batch Line'
    _order = 'batch_id desc, branch_id, product_id, eplus_item_code'

    batch_id = fields.Many2one('ab_self_inventory_request_batch', required=True, ondelete='cascade', index=True)
    branch_id = fields.Many2one('ab_store', required=True, readonly=True, index=True)
    selected = fields.Boolean(default=False)
    product_id = fields.Many2one('ab_product', string='Product', index=True, readonly=True)
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
    request_id = fields.Many2one('ab_self_inventory_request', readonly=True, copy=False)
    extra_data = fields.Json(readonly=True)

    def action_select_all_lines(self):
        self._get_context_batch().action_select_all_lines()
        return self._reload_action()

    def action_unselect_all_lines(self):
        self._get_context_batch().action_unselect_all_lines()
        return self._reload_action()

    def action_delete_selected_lines(self):
        self._get_context_batch().action_delete_selected_lines()
        return self._reload_action()

    def action_delete_unselected_lines(self):
        self._get_context_batch().action_delete_unselected_lines()
        return self._reload_action()

    def write(self, vals):
        for rec in self:
            if rec.batch_id.state != 'draft':
                raise ValidationError(_("Only draft self inventory batch lines can be changed."))
        return super().write(vals)

    def unlink(self):
        for rec in self:
            if rec.batch_id.state != 'draft':
                raise ValidationError(_("Only draft self inventory batch lines can be deleted."))
        return super().unlink()

    def _get_context_batch(self):
        batch_id = self.env.context.get('default_batch_id')
        if not batch_id and self:
            batches = self.mapped('batch_id')
            if len(batches) == 1:
                batch_id = batches.id
        batch = self.env['ab_self_inventory_request_batch'].browse(batch_id).exists()
        if not batch:
            raise ValidationError(_("Open these lines from a self inventory batch before using bulk line actions."))
        batch.ensure_one()
        return batch

    @api.model
    def _reload_action(self):
        return {'type': 'ir.actions.client', 'tag': 'reload'}
