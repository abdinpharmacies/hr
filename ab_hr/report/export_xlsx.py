# -*- coding: utf-8 -*-
import datetime

from odoo import models


class ExtraParams:
    sheet = None
    wb = None


# Creating Excel Report
# https://www.youtube.com/watch?v=cCyMy2kxxZs&list=PLqRRLx0cl0hoJhjFWkFYowveq2Zn55dhM&index=46
class QueryXLS(models.AbstractModel, ExtraParams):
    _name = 'report.ab_hr_salary_details_report_model'
    _description = 'ab_hr_salary_details_report_model'
    _inherit = ['report.report_xlsx.abstract']

    def generate_xlsx_report(self, workbook, data, objs):
        title = objs[0].explain
        rows = []
        headers = []
        sal_model = objs[0].sal_ids
        flds = sal_model.fields_get()
        flds_ar = sal_model.with_context(lang='ar_001').fields_get()
        all_headers = {k: v['string'] for k, v in flds.items()}
        targ_headers = ['id', 'status', 'accid', 'employee_id', 'job_id', 'user_line_owner',
                        'territory', 'workplace', 'hr_name_entry', 'store_id', 'due_date', 'section', 'section_type',
                        'section_value']
        for header in targ_headers:
            org_header = all_headers[header]
            translated_header = flds_ar.get(header, {}).get('string')

            if translated_header:
                headers.append(translated_header)
            else:
                headers.append(org_header)

        for sal in objs[0].sal_ids:
            row = (
                sal.id,
                sal.status,
                sal.accid,
                sal.employee_id.name,
                sal.job_id.name,
                sal.user_line_owner.name,
                sal.territory,
                sal.workplace.name,
                sal.hr_name_entry,
                sal.store_id.name,
                sal.due_date.strftime("%d/%m/%Y"),
                sal.section.name,
                sal.section_type,
                sal.section_value,
            )
            rows.append(row)
        self.add_data_to_wb(workbook, title, headers, rows)

    def add_data_to_wb(self, wb, title, headers, rows):
        format1 = wb.add_format({'font_size': 14,
                                 'font_color': '#333333',
                                 'bg_color': '#dddddd',
                                 'align': 'center',
                                 'valign': 'vcenter',
                                 'bold': True})
        # format1.set_font_color('#ccc')
        format2 = wb.add_format({'font_size': 14, 'align': 'vcenter'})

        self.sheet = wb.add_worksheet('Query Result')

        no_of_cols = len(headers) - 1
        self.add_title(title, no_of_cols, format1)

        self.add_headers(headers, format1)

        self.add_rows(rows, format2)

        self.cols_autofit(rows)

    def add_title(self, title, no_of_cols, format):
        # self.sheet.write(0, 0, title)
        self.sheet.merge_range(0, 0, 0, no_of_cols, title, format)

    def add_headers(self, headers, format):
        for i, header in enumerate(headers):
            self.sheet.write(1, i, header if (header is not None) else '', format)

    def add_rows(self, rows, format):
        for i, row in enumerate(rows, 2):
            for j, item in enumerate(row):
                self.sheet.write(i, j, item if (item is not None) else '', format)

    def cols_autofit(self, rows):
        if not rows:
            return False
        for j in range(len(rows[0])):
            mycol = [len(str(rows[i][j])) for i, row in enumerate(rows)]
            self.sheet.set_column(j, j, max(mycol) + 4)


class ExcelWriter(models.AbstractModel, ExtraParams):
    _name = 'excel_writer'
    _description = 'Inherit this to call excel functions'

    def add_data_to_wb(self, wb, headers, rows):
        self.wb = wb

        # format1.set_font_color('#ccc')
        self.sheet = wb.add_worksheet('Query Result')

        self.add_headers(headers)

        self.add_rows(rows)

        self.cols_autofit(rows)

    def add_headers(self, headers):
        format_header = self.wb.add_format({'font_size': 14,
                                            'font_color': '#333333',
                                            'bg_color': '#dddddd',
                                            'align': 'center',
                                            'valign': 'vcenter',
                                            'bold': True, })

        for j, header in enumerate(headers):
            if type(header) == datetime.date:
                header = format(header, '%B-%Y')
            self.sheet.write(0, j, "{0}".format(header) if (header is not None) else '', format_header)

    def add_rows(self, rows):
        format_dict = {'font_size': 14, 'align': 'vcenter', }
        formatting = self.wb.add_format(format_dict)
        for i, row in enumerate(rows, 1):
            for j, item in enumerate(row):
                if type(item) == float:
                    formatting = self.wb.add_format(dict(**format_dict, num_format='#,##0.00'))
                    item = round(item, 2)
                    self.sheet.write(i, j, item, formatting)
                elif type(item) == datetime.date:
                    formatting = self.wb.add_format(dict(**format_dict, num_format='yyyy-mm-dd'))
                    self.sheet.write(i, j, item, formatting)
                elif type(item) == datetime.datetime:
                    formatting = self.wb.add_format(dict(**format_dict, num_format='yyyy-mm-dd HH:MM:ss'))
                    self.sheet.write(i, j, item, formatting)
                elif type(item) == int:
                    self.sheet.write(i, j, item, formatting)
                elif not item:
                    self.sheet.write(i, j, '', formatting)
                else:
                    self.sheet.write(i, j, item, formatting)

    def cols_autofit(self, rows):
        try:
            for j in range(len(rows[0])):
                mycol = [len(str(rows[i][j])) for i, row in enumerate(rows)]
                self.sheet.set_column(j, j, max(mycol) + 4)
        except Exception as e:
            pass


class SalariesReport(models.AbstractModel, ExtraParams):
    _name = 'report.salaries_xlsx_model'
    _description = 'Salaries Report'
    _inherit = ['excel_writer', 'report.report_xlsx.abstract']

    def generate_xlsx_report(self, workbook, data, objs):
        data = objs[0]._get_salaries_html()
        if data:
            headers = data['headers']
            rows = data['rows']
            self.add_data_to_wb(workbook, headers, rows)


class SalariesCompareReport(models.AbstractModel, ExtraParams):
    _name = 'report.salaries_compare_xlsx'
    _description = 'Salaries Compare Report'
    _inherit = ['excel_writer', 'report.report_xlsx.abstract']

    def generate_xlsx_report(self, workbook, data, objs):
        data = objs[0]._get_salaries_compare_html()
        if data:
            headers = data['headers']
            rows = data['rows']
            self.add_data_to_wb(workbook, headers, rows)
