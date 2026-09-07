import base64
import io

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

try:
    import openpyxl
except ImportError:
    openpyxl = None


class SelfInventoryImportWizard(models.TransientModel):
    _name = 'ab_self_inventory_import_wizard'
    _description = 'Self Inventory Actual Count Import'

    process_id = fields.Many2one('ab_self_inventory_process', required=True)
    file = fields.Binary(required=True)
    filename = fields.Char()

    def action_import(self):
        self.ensure_one()
        if not openpyxl:
            raise UserError(_("openpyxl is required to import Excel files."))
        if self.process_id.state not in ('draft', 'in_progress'):
            raise ValidationError(_("Only active self inventory processes can import actual counts."))
        self.process_id._check_can_update_process_line_grid()

        try:
            workbook = openpyxl.load_workbook(io.BytesIO(base64.b64decode(self.file)), data_only=True)
        except Exception as exc:
            raise UserError(_("Could not read Excel file: %s") % exc)

        sheet = workbook.active
        header_row = next(sheet.iter_rows(min_row=1, max_row=1, values_only=True), None)
        if not header_row:
            raise ValidationError(_("The Excel file is empty."))
        headers = {str(value or '').strip().lower(): index for index, value in enumerate(header_row)}
        code_indexes = self._header_indexes(headers, 'product code', 'e-plus item code', 'e-plus item id', 'item code')
        actual_index = self._first_header(headers, 'actual qty', 'actual quantity')
        balance_at_count_index = self._first_header(headers, 'balance at count', 'system qty', 'e-stock qty')
        if not code_indexes or actual_index is None:
            raise ValidationError(_("Excel must contain Product Code and Actual Qty columns."))

        lines_by_code = {}
        lines_by_product_id = {}
        for line in self.process_id.line_ids:
            if line.product_id:
                lines_by_product_id[line.product_id.id] = line
            for code in (line.product_code, line.eplus_item_code):
                if code:
                    lines_by_code[self._code_key(code)] = line
        for line in self.process_id.line_ids:
            if line.eplus_item_id:
                lines_by_code.setdefault(self._code_key(line.eplus_item_id), line)

        import_rows = []
        seen_codes = set()
        duplicate_codes = []
        for row in sheet.iter_rows(min_row=2, values_only=True):
            code = self._row_code(row, code_indexes)
            if not code:
                continue
            code_key = self._code_key(code)
            if code_key in seen_codes:
                duplicate_codes.append(code)
                continue
            seen_codes.add(code_key)
            import_rows.append({
                'code': code,
                'code_key': code_key,
                'actual_value': row[actual_index],
                'balance_value': row[balance_at_count_index] if balance_at_count_index is not None else None,
            })

        if duplicate_codes:
            raise ValidationError(
                _("Duplicate product code in Excel: %s")
                % ', '.join(duplicate_codes[:10])
            )

        products_by_code = self._get_products_by_import_codes([row['code'] for row in import_rows])
        missing_codes = []
        for import_row in import_rows:
            line = lines_by_code.get(import_row['code_key'])
            product = products_by_code.get(import_row['code_key'])
            if not line and product:
                line = lines_by_product_id.get(product.id)
            if not line and not product:
                missing_codes.append(import_row['code'])
                continue
            import_row['line'] = line
            import_row['product'] = product or line.product_id

        if missing_codes:
            raise ValidationError(
                _("Unknown product code(s) in Excel: %s")
                % ', '.join(missing_codes[:20])
            )

        seen_product_ids = {}
        duplicate_product_codes = []
        for import_row in import_rows:
            product = import_row.get('product')
            if not product:
                continue
            if product.id in seen_product_ids:
                duplicate_product_codes.append(import_row['code'])
                continue
            seen_product_ids[product.id] = import_row['code']

        if duplicate_product_codes:
            raise ValidationError(
                _("Duplicate product code in Excel: %s")
                % ', '.join(duplicate_product_codes[:10])
            )

        updated = 0
        created = 0
        new_lines = self.env['ab_self_inventory_process_line']
        for import_row in import_rows:
            if import_row.get('line'):
                line = import_row['line']
                if import_row['actual_value'] in (None, ''):
                    continue
                values = {'actual_qty': self._to_float(import_row['actual_value'], import_row['code'], 'actual')}
                if import_row['balance_value'] not in (None, ''):
                    values.update({
                        'count_snapshot_qty': self._to_float(import_row['balance_value'], import_row['code'], 'balance'),
                        'count_snapshot_taken': True,
                    })
                line.sudo().with_context(ab_self_inventory_allow_count_snapshot_sync=True).write(values)
                updated += 1
                continue

            product = import_row['product']
            values = {
                'process_id': self.process_id.id,
                'product_id': product.id,
                'eplus_item_id': int(product.eplus_serial or 0),
                'eplus_item_code': product.code or '',
                'requested': True,
                'system_qty': 0.0,
                'unit_cost': product.default_cost or product.default_price or 0.0,
            }
            if import_row['actual_value'] not in (None, ''):
                values.update({
                    'actual_qty': self._to_float(import_row['actual_value'], import_row['code'], 'actual'),
                })
            new_lines |= self.env['ab_self_inventory_process_line'].sudo().create(values)
            created += 1

        if new_lines:
            quantities_by_line = self.process_id.sudo()._fetch_requested_line_stock_quantities(new_lines)
            for line in new_lines:
                system_qty = quantities_by_line.get(line.id, 0.0)
                line.sudo().with_context(
                    ab_self_inventory_allow_system_qty_sync=True,
                    ab_self_inventory_allow_count_snapshot_sync=True,
                ).write({
                    'system_qty': system_qty,
                    'count_snapshot_qty': system_qty,
                    'count_snapshot_taken': True,
                })

        if not updated and not created:
            raise ValidationError(_("No matching inventory lines were updated."))
        message = _("Updated %(updated)s inventory line(s). Added %(created)s new product line(s).") % {
            'updated': updated,
            'created': created,
        }
        return {
            'type': 'ir.actions.client',
            'tag': 'ab_self_inventory_close_dialog_reload',
            'params': {'title': _('Import Complete'), 'message': message, 'type': 'success', 'sticky': False},
        }

    def _header_indexes(self, headers, *names):
        return [headers[name] for name in names if name in headers]

    def _first_header(self, headers, *names):
        for name in names:
            if name in headers:
                return headers[name]
        return None

    def _row_code(self, row, code_indexes):
        for code_index in code_indexes:
            if code_index >= len(row):
                continue
            code = self._normalize_excel_code(row[code_index])
            if code:
                return code
        return ''

    def _normalize_excel_code(self, value):
        if value in (None, ''):
            return ''
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value).strip()

    def _code_key(self, code):
        return self._normalize_excel_code(code).upper()

    def _get_products_by_import_codes(self, codes):
        code_values = []
        eplus_ids = []
        for code in codes:
            normalized = self._normalize_excel_code(code)
            if not normalized:
                continue
            code_values.append(normalized)
            try:
                eplus_ids.append(int(normalized))
            except ValueError:
                pass

        Product = self.env['ab_product'].sudo()
        products = Product.browse()
        if code_values:
            products |= Product.search([('code', 'in', list(set(code_values)))])
        if eplus_ids:
            products |= Product.search([('eplus_serial', 'in', list(set(eplus_ids)))])

        products_by_code = {}
        for product in products:
            if product.code:
                products_by_code.setdefault(self._code_key(product.code), product)
            if product.eplus_serial:
                products_by_code.setdefault(self._code_key(product.eplus_serial), product)
        return products_by_code

    def _to_float(self, value, code, column_type):
        try:
            return float(value or 0.0)
        except (TypeError, ValueError):
            if column_type == 'balance':
                raise ValidationError(_("Balance at Count must be numeric for product code %s.") % code)
            raise ValidationError(_("Actual quantity must be numeric for product code %s.") % code)


class SelfInventoryAddLineWizard(models.TransientModel):
    _name = 'ab_self_inventory_batch_add_line_wizard'
    _description = 'Self Inventory Manual Add Line'

    request_id = fields.Many2one('ab_self_inventory_request', readonly=True)
    batch_id = fields.Many2one('ab_self_inventory_request_batch', readonly=True)
    process_id = fields.Many2one('ab_self_inventory_process', readonly=True)
    branch_ids = fields.Many2many(
        'ab_store',
        string='Branches',
        domain="[('store_type', '=', 'branch')]",
    )
    product_ids = fields.Many2many('ab_product', string='Products', required=True)
    excluded_product_ids = fields.Many2many(
        'ab_product',
        compute='_compute_excluded_product_ids',
    )
    note = fields.Char()

    @api.depends(
        'request_id.line_ids.product_id',
        'batch_id.line_ids.product_id',
        'process_id.line_ids.product_id',
        'branch_ids',
    )
    def _compute_excluded_product_ids(self):
        for wizard in self:
            used_products = self.env['ab_product']
            if wizard.request_id:
                used_products = wizard.request_id.line_ids.mapped('product_id')
            elif wizard.batch_id:
                branches = wizard.branch_ids or wizard.batch_id.branch_ids
                lines = wizard.batch_id.line_ids
                if branches:
                    lines = lines.filtered(lambda line: line.branch_id in branches)
                used_products = lines.mapped('product_id')
            elif wizard.process_id:
                used_products = wizard.process_id.line_ids.mapped('product_id')
            wizard.excluded_product_ids = used_products

    def action_add_lines(self):
        self.ensure_one()
        if self.request_id:
            self._add_request_lines()
        elif self.batch_id:
            self._add_batch_lines()
        elif self.process_id:
            self._add_process_lines()
        else:
            raise ValidationError(_("Open Add Line from a self inventory request, batch, or process."))
        return {'type': 'ir.actions.act_window_close'}

    def _add_process_lines(self):
        process = self.process_id
        process._check_can_update_process_line_grid()
        if not self.product_ids:
            raise ValidationError(_("Select at least one product."))
        existing_products = set(process.line_ids.mapped('product_id').ids)
        duplicate_products = self.product_ids.filtered(
            lambda product: product.id in existing_products
        )
        if duplicate_products:
            raise ValidationError(
                _("These products already exist on this process: %s")
                % ', '.join(duplicate_products.mapped('display_name')[:10])
            )
        self.env['ab_self_inventory_process_line'].create([
            {
                'process_id': process.id,
                'product_id': product.id,
                'explanation': self.note,
            }
            for product in self.product_ids
        ])

    def _add_request_lines(self):
        request = self.request_id
        if request.state != 'draft':
            raise ValidationError(_("You cannot add lines after the request is submitted."))
        if not self.product_ids:
            raise ValidationError(_("Select at least one product."))
        line_values = []
        existing_products = set(request.line_ids.mapped('product_id').ids)
        duplicate_products = self.product_ids.filtered(lambda product: product.id in existing_products)
        if duplicate_products:
            raise ValidationError(
                _("These products already exist on this request: %s")
                % ', '.join(duplicate_products.mapped('display_name')[:10])
            )
        for product in self.product_ids:
            line_values.append({
                'request_id': request.id,
                'product_id': product.id,
                'eplus_item_id': int(product.eplus_serial or 0),
                'eplus_item_code': product.code or '',
                'system_qty': 0.0,
                'matched_by': 'code' if product.code else 'none',
                'selected': True,
                'sell_price': product.default_price or 0.0,
                'note': self.note,
            })
        if not line_values:
            raise ValidationError(_("Selected products already exist on this request."))
        self.env['ab_self_inventory_request_line'].create(line_values)

    def _add_batch_lines(self):
        batch = self.batch_id
        if batch.state != 'draft':
            raise ValidationError(_("You cannot add lines after the batch is submitted."))
        if not self.product_ids:
            raise ValidationError(_("Select at least one product."))
        branches = self.branch_ids or batch.branch_ids
        if not branches:
            raise ValidationError(_("Select at least one branch."))
        missing_branches = branches - batch.branch_ids
        if missing_branches:
            batch.write({'branch_ids': [(4, branch.id) for branch in missing_branches]})
        line_values = []
        existing_keys = {
            (line.branch_id.id, line.product_id.id)
            for line in batch.line_ids
            if line.branch_id and line.product_id
        }
        duplicate_names = []
        for branch in branches:
            for product in self.product_ids:
                if (branch.id, product.id) in existing_keys:
                    duplicate_names.append("%s / %s" % (branch.display_name, product.display_name))
        if duplicate_names:
            raise ValidationError(
                _("These products already exist in the result table: %s")
                % ', '.join(duplicate_names[:10])
            )
        for branch in branches:
            for product in self.product_ids:
                key = (branch.id, product.id)
                existing_keys.add(key)
                line_values.append({
                    'batch_id': batch.id,
                    'branch_id': branch.id,
                    'product_id': product.id,
                    'eplus_item_id': int(product.eplus_serial or 0),
                    'eplus_item_code': product.code or '',
                    'system_qty': 0.0,
                    'matched_by': 'code' if product.code else 'none',
                    'selected': True,
                    'sell_price': product.default_price or 0.0,
                    'note': self.note,
                })
        if not line_values:
            raise ValidationError(_("Selected products already exist for the selected branches."))
        self.env['ab_self_inventory_request_batch_line'].create(line_values)
