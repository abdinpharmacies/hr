from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _


class AbReplicaDb(models.Model):
    _name = 'ab_replica_db'
    _inherit = 'ab_replica_db'

    invoices_text = fields.Text(
        string='Excluded Invoice Numbers',
        help='Invoice ePlus serials excluded from the return-window days check. Use one invoice per line.',
    )

    @api.model
    def _parse_invoice_exclusion_text(self, text, raise_empty=False, strict=False):
        serials = []
        seen = set()
        tokens = (text or '').strip().split()
        for token in tokens:
            try:
                serial_int = int(token)
            except (TypeError, ValueError):
                if strict:
                    raise UserError(_("Invalid invoice number: %s") % token)
                continue
            if serial_int and serial_int not in seen:
                seen.add(serial_int)
                serials.append(serial_int)
        if raise_empty and not serials:
            raise UserError(_("Paste at least one invoice number first."))
        return serials

    @api.model
    def _format_invoice_exclusion_serials(self, serials):
        return "\n".join(str(serial) for serial in serials)

    def _get_excluded_invoice_serials(self):
        self.ensure_one()
        return self._parse_invoice_exclusion_text(self.invoices_text)

    def _is_invoice_excluded_from_return_window(self, eplus_serial):
        self.ensure_one()
        try:
            eplus_serial = int(eplus_serial or 0)
        except (TypeError, ValueError):
            return False
        return eplus_serial in set(self._get_excluded_invoice_serials())

    def _check_invoice_exclusion_group(self):
        if not (
                self.env.user.has_group('ab_store.see_stores_ips')
                or self.env.user.has_group('base.group_system')
        ):
            raise UserError(_("You can not manage excluded invoices."))

    def _update_invoice_exclusion_text(self, text, operation):
        self.ensure_one()
        self._check_invoice_exclusion_group()
        pasted_serials = self._parse_invoice_exclusion_text(text, raise_empty=True, strict=True)
        current_serials = self._get_excluded_invoice_serials()
        current_set = set(current_serials)
        pasted_set = set(pasted_serials)

        if operation == 'add':
            changed_serials = [serial for serial in pasted_serials if serial not in current_set]
            next_serials = current_serials + changed_serials
            unchanged_count = len(pasted_set & current_set)
            changed_key = 'added'
            unchanged_key = 'existing'
        elif operation == 'remove':
            changed_serials = [serial for serial in current_serials if serial in pasted_set]
            next_serials = [serial for serial in current_serials if serial not in pasted_set]
            unchanged_count = len(pasted_set - set(changed_serials))
            changed_key = 'removed'
            unchanged_key = 'not_listed'
        else:
            raise UserError(_("Unsupported invoice exclusion operation."))

        value = self._format_invoice_exclusion_serials(next_serials)
        self.sudo().write({'invoices_text': value})
        return {
            'value': value,
            changed_key: len(changed_serials),
            unchanged_key: unchanged_count,
            'total': len(next_serials),
        }

    def btn_add_invoices(self, text=None):
        return self._update_invoice_exclusion_text(text, 'add')

    def btn_remove_invoices(self, text=None):
        return self._update_invoice_exclusion_text(text, 'remove')
