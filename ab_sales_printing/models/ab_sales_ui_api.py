from odoo import _, api, models
from odoo.exceptions import UserError


class AbSalesPrintingUiApi(models.TransientModel):
    _inherit = 'ab_sales_ui_api'

    def _sales_printing_check_access(self):
        self.check_access('read')
        guard = getattr(self, '_raise_sales_prevented', None)
        if guard:
            guard()

    def _sales_printing_receipt(self, header_id, print_format):
        self._sales_printing_check_access()
        if print_format not in ('a4', 'pos_80mm'):
            raise UserError(_("Select a supported paper format."))
        record_type, record_id = self._bill_wizard_decode_ref(header_id)
        model = 'ab_sales_return_header' if record_type == 'return' else 'ab_sales_header'
        record = self.env[model].browse(record_id).exists()
        record.check_access('read')
        if not record:
            raise UserError(_("Select a bill to print."))
        # Keep the caller's ACLs and record rules on both header and line reads.
        record_type, header, lines, fmt, settings, _content = self._bill_wizard_prepare_print_content(
            header_id, print_format=print_format,
        )
        if not lines:
            raise UserError(_("No lines to print."))
        html = self._bill_wizard_build_print_html(
            header=header, lines=lines, print_format=fmt,
            receipt_header=_("Sales Return Receipt") if record_type == 'return' else (
                settings.get('receipt_header') or _("Sales Receipt")
            ), record_type=record_type, printer_name='',
        )
        return {'ok': True, 'content': str(html), 'print_format': fmt}

    @api.model
    def bill_wizard_cups_render(self, header_id, print_format='a4'):
        """Use the same authorized receipt for preview and browser printing."""
        return self._sales_printing_receipt(header_id, print_format)

    @api.model
    def bill_wizard_cups_print(self, header_id, printer_name, print_format='a4'):
        receipt = self._sales_printing_receipt(header_id, print_format)
        service = self.env['ab_printing_service']
        if printer_name not in service.list_printers():
            raise UserError(_("The selected CUPS printer is no longer available. Refresh the printer list."))
        html = receipt['content']
        if receipt['print_format'] == 'a4':
            # Private PDF spacing for the existing fixed-width RTL A4 receipt.
            html = html.replace('</head>', (
                '<style>body { width: 520px; margin: 0 auto; }'
                '.receipt-page { width: 520px; padding: 4px 10px; }</style></head>'
            ), 1)
        result = service._print_html(
            self._prepare_print_html(html), printer=printer_name,
            print_format=receipt['print_format'],
        )
        return dict(result, print_format=receipt['print_format'])

    @api.model
    def bill_wizard_cups_options(self):
        self._sales_printing_check_access()
        # Reuse Sales defaults and its optional business guards. Return only
        # queue names/paper sizes, never the existing printer connection data.
        options = self.bill_wizard_get_print_options()
        formats = {
            rec['printer_name']: rec['paper_size']
            for rec in options.get('available_printer_records', [])
        }
        queues = self.env['ab_printing_service'].list_printers()
        return {
            'print_format': options.get('print_format', 'a4'),
            'available_printer_records': [
                {'id': index, 'label': queue, 'name': queue, 'printer_name': queue,
                 'paper_size': formats.get(queue, 'a4'), 'protocol': 'connected'}
                for index, queue in enumerate(queues, start=1)
            ],
        }
