from odoo import models, _


class AccountingXlsx(models.AbstractModel):
    _name = 'report.ab_accounting.financial_xlsx'
    _inherit = 'report.report_xlsx.abstract'
    _description = 'Accounting XLSX Report'

    def generate_xlsx_report(self, workbook, data, reports):
        title = workbook.add_format({'bold': True})
        number = workbook.add_format({'num_format': '#,##0.00'})
        for index, report in enumerate(reports):
            values = report.get_report_data()
            sheet = workbook.add_worksheet(_('Accounting') + ' ' + str(index + 1))
            sheet.freeze_panes(1, 0)
            sheet.set_column(0, len(values['columns']) - 1, 22)
            for col, label in enumerate(values['columns']):
                sheet.write_string(0, col, label, title)
            for row, cells in enumerate(values['rows'], 1):
                for col, value in enumerate(cells):
                    if isinstance(value, (int, float)):
                        sheet.write_number(row, col, value, number)
                    else:
                        sheet.write_string(row, col, str(value or ''))
