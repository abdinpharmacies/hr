import base64
import io

from odoo import _, fields, models
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
        if self.process_id.state != 'draft':
            raise ValidationError(_("Only draft self inventory processes can import actual counts."))

        try:
            workbook = openpyxl.load_workbook(io.BytesIO(base64.b64decode(self.file)), data_only=True)
        except Exception as exc:
            raise UserError(_("Could not read Excel file: %s") % exc)

        sheet = workbook.active
        header_row = next(sheet.iter_rows(min_row=1, max_row=1, values_only=True), None)
        if not header_row:
            raise ValidationError(_("The Excel file is empty."))
        headers = {str(value or '').strip().lower(): index for index, value in enumerate(header_row)}
        code_index = self._first_header(headers, 'product code', 'e-plus item code', 'item code')
        actual_index = self._first_header(headers, 'actual qty', 'actual quantity')
        explanation_index = self._first_header(headers, 'explanation', 'note')
        if code_index is None or actual_index is None:
            raise ValidationError(_("Excel must contain Product Code and Actual Qty columns."))

        lines_by_code = {}
        for line in self.process_id.line_ids:
            for code in (line.product_code, line.eplus_item_code, str(line.eplus_item_id or '')):
                if code:
                    lines_by_code[str(code).strip()] = line

        updated = 0
        missing_codes = []
        for row in sheet.iter_rows(min_row=2, values_only=True):
            code = str(row[code_index] or '').strip()
            if not code:
                continue
            line = lines_by_code.get(code)
            if not line:
                missing_codes.append(code)
                continue
            vals = {'actual_qty': float(row[actual_index] or 0.0)}
            if explanation_index is not None:
                vals['explanation'] = str(row[explanation_index] or '').strip()
            line.write(vals)
            updated += 1

        if not updated:
            raise ValidationError(_("No matching inventory lines were updated."))
        message = _("Updated %s inventory lines.") % updated
        if missing_codes:
            message += _(" Missing product codes: %s") % ', '.join(missing_codes[:10])
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'title': _('Import Complete'), 'message': message, 'type': 'success', 'sticky': False},
        }

    def _first_header(self, headers, *names):
        for name in names:
            if name in headers:
                return headers[name]
        return None
