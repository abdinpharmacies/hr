# -*- coding: utf-8 -*-
import io
from odoo.tools.translate import _
from odoo.tools.misc import xlsxwriter
from odoo.exceptions import UserError
from odoo.http import request
from odoo.addons.web.controllers.main import ExportXlsxWriter


# I ask 'Bing AI' and this method - to change class all original class instance - is called 'Monkey Patching'
# You write all code again and modify whatever you want
# Problem is: if odoo developers change default __init__ then a BUGs may happen
# According to 'Bing AI', this is the only way to modify orginal __init__ of class
class ExportXlsx(ExportXlsxWriter):
    def __myinit__(self, field_names, row_count=0):
        self.field_names = field_names
        self.output = io.BytesIO()
        self.workbook = xlsxwriter.Workbook(self.output, {'in_memory': True})
        self.base_style = self.workbook.add_format({'text_wrap': False})
        self.header_style = self.workbook.add_format({'bold': True})
        self.header_bold_style = self.workbook.add_format({'text_wrap': True, 'bold': True, 'bg_color': '#e9ecef'})
        self.date_style = self.workbook.add_format({'text_wrap': False, 'num_format': 'yyyy-mm-dd'})
        self.datetime_style = self.workbook.add_format({'text_wrap': False, 'num_format': 'yyyy-mm-dd hh:mm:ss'})
        self.worksheet = self.workbook.add_worksheet()
        self.value = False
        self.float_format = '#,##0.00'
        decimal_places = [res['decimal_places'] for res in
                          request.env['res.currency'].search_read([], ['decimal_places'])]
        self.monetary_format = f'#,##0.{max(decimal_places or [2]) * "0"}'

        if row_count > self.worksheet.xls_rowmax:
            raise UserError(
                _('There are too many rows (%s rows, limit: %s) to export as Excel 2007-2013 (.xlsx) format. Consider splitting the export.') % (
                    row_count, self.worksheet.xls_rowmax))

    ExportXlsxWriter.__init__ = __myinit__
