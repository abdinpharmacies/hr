# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ExtraParams:
    sheet = None
    wb = None


class ExcelWriter(models.AbstractModel, ExtraParams):
    _name = 'excel_writer'
    _description = 'Inherit this to call excel functions'

    def add_data_to_wb(self, wb, headers, rows):
        format1 = wb.add_format({'font_size': 14,
                                 'font_color': '#333333',
                                 'bg_color': '#dddddd',
                                 'align': 'center',
                                 'valign': 'vcenter',
                                 'bold': True})
        # format1.set_font_color('#ccc')
        format2 = wb.add_format({'font_size': 14, 'align': 'vcenter'})

        self.sheet = wb.add_worksheet('Query Result')

        self.add_headers(headers, format1)

        self.add_rows(rows, format2)

        self.cols_autofit(rows)

    def add_headers(self, headers, format):
        for i, header in enumerate(headers):
            self.sheet.write(0, i, header if (header is not None) else '', format)

    def add_rows(self, rows, format):
        for i, row in enumerate(rows, 1):
            for j, item in enumerate(row):
                self.sheet.write(i, j, item if (item is not None) else '', format)

    def cols_autofit(self, rows):
        try:
            for j in range(len(rows[0])):
                mycol = [len(str(rows[i][j])) for i, row in enumerate(rows)]
                self.sheet.set_column(j, j, max(mycol) + 4)
        except Exception as e:
            pass


class AccountStatementExcel(models.AbstractModel, ExtraParams):
    _name = 'report.overstock_no_need'
    _description = 'Overstock No Need'
    _inherit = ['excel_writer', 'report.report_xlsx.abstract']

    sheet = None

    def generate_xlsx_report(self, workbook, data, objs):
        data = objs[0].get_overstock_no_need_data()
        if data:
            headers = data['headers']
            rows = data['rows']
            self.add_data_to_wb(workbook, headers, rows)
