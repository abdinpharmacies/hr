from odoo import models


class SelfInventoryCountSheetXlsx(models.AbstractModel):
    _name = 'report.ab_self_inventory.count_sheet_xlsx'
    _description = 'Self Inventory Count Sheet XLSX'
    _inherit = 'report.report_xlsx.abstract'

    def generate_xlsx_report(self, workbook, data, processes):
        header_format = workbook.add_format({
            'bold': True,
            'font_color': '#333333',
            'bg_color': '#dddddd',
            'align': 'center',
            'valign': 'vcenter',
        })
        cell_format = workbook.add_format({'valign': 'vcenter'})
        headers = ['Product Code', 'Product Name', 'System Qty', 'Actual Qty', 'Explanation']
        for process in processes:
            sheet = workbook.add_worksheet((process.name or 'Count Sheet')[:31])
            for col, header in enumerate(headers):
                sheet.write(0, col, header, header_format)
            for row_index, line in enumerate(process.line_ids, 1):
                sheet.write(row_index, 0, line.product_code or line.eplus_item_code or '', cell_format)
                sheet.write(row_index, 1, line.product_id.display_name or '', cell_format)
                sheet.write(row_index, 2, line.system_qty or 0.0, cell_format)
                sheet.write(row_index, 3, line.actual_qty or 0.0, cell_format)
                sheet.write(row_index, 4, line.explanation or '', cell_format)
            widths = [18, 42, 14, 14, 35]
            for col, width in enumerate(widths):
                sheet.set_column(col, col, width)
