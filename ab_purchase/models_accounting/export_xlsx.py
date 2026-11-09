# -*- coding: utf-8 -*-
from odoo import models

from datetime import date


class ExcelWriter(models.AbstractModel):
    _name = 'excel_writer'
    _description = 'Inherit this to call excel functions'

    _excel = {}

    def add_data_to_wb(self, wb, headers, rows):
        format1 = wb.add_format({'font_size': 14,
                                 'font_color': '#333333',
                                 'bg_color': '#dddddd',
                                 'align': 'center',
                                 'valign': 'vcenter',
                                 'bold': True})
        # format1.set_font_color('#ccc')
        format2 = wb.add_format({'font_size': 14, 'align': 'vcenter'})

        # date format
        date_format = wb.add_format({'num_format': 'yyyy-mm-dd'})
        self._excel['sheet'] = wb.add_worksheet('Query Result')

        self.add_headers(headers, format1)

        self.add_rows(rows, format2, date_format)

        self.cols_autofit(rows)

    def add_headers(self, headers, format):
        for i, header in enumerate(headers):
            self._excel['sheet'].write(0, i, header if (header is not None) else '', format)

    def add_rows(self, rows, format, date_format=None):

        for i, row in enumerate(rows, 1):
            for j, item in enumerate(row):
                if isinstance(item, date) and date_format:
                    "format item as excel date"
                    self._excel['sheet'].write_datetime(i, j, item, date_format)
                else:
                    self._excel['sheet'].write(i, j, item if (item is not None) else '', format)

    def cols_autofit(self, rows):
        try:
            for j in range(len(rows[0])):
                mycol = [len(str(rows[i][j])) for i, row in enumerate(rows)]
                self._excel['sheet'].set_column(j, j, max(mycol) + 4)
        except Exception as e:
            pass


class ReportExcel(models.AbstractModel):
    _name = 'report.ab_supplier_balances_excel'
    _description = 'report.ab_supplier_balances_excel'
    _inherit = ['excel_writer', 'report.report_xlsx.abstract']

    def generate_xlsx_report(self, workbook, data, objs):
        data = objs[0].get_je_data()
        if data:
            headers = data['headers']
            rows = data['rows']
            self.add_data_to_wb(workbook, headers, rows)
