# -*- coding: utf-8 -*-
from odoo.http import request
from odoo.addons.web.controllers.export import ExportXlsxWriter


def _patch_export_xlsx_writer():
    if getattr(ExportXlsxWriter, '_abdin_disable_text_wrap_patched', False):
        return

    original_init = ExportXlsxWriter.__init__

    def init_without_text_wrap(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        decimal_places = request.env['res.currency']._read_group(
            [],
            aggregates=['decimal_places:max'],
        )[0][0]
        decimal_places = decimal_places or 2

        self.base_style = self.workbook.add_format({'text_wrap': False})
        self.date_style = self.workbook.add_format({
            'text_wrap': False,
            'num_format': 'yyyy-mm-dd',
        })
        self.datetime_style = self.workbook.add_format({
            'text_wrap': False,
            'num_format': 'yyyy-mm-dd hh:mm:ss',
        })
        self.float_style = self.workbook.add_format({
            'text_wrap': False,
            'num_format': '#,##0.00',
        })
        self.monetary_style = self.workbook.add_format({
            'text_wrap': False,
            'num_format': f'#,##0.{decimal_places * "0"}',
        })

    ExportXlsxWriter.__init__ = init_without_text_wrap
    ExportXlsxWriter._abdin_disable_text_wrap_patched = True


_patch_export_xlsx_writer()
