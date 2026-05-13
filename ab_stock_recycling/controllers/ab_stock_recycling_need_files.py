# -*- coding: utf-8 -*-
import io
from urllib.parse import quote
import zipfile
from odoo import _, http
import xlsxwriter
from itertools import groupby
from operator import attrgetter

from datetime import datetime


def adjust_columns_width(worksheet, headers):
    # Update max_col_widths for each row
    # Initialize a list to store the maximum length of data in each column
    max_col_widths = [len(str(value)) for value in headers]

    # Set the column widths
    for i, width in enumerate(max_col_widths):
        worksheet.set_column(0, i, width)


def add_data_in_table(worksheet, data):
    # Calculate table size
    # Define your variables
    x = len(data)  # number of rows
    y = len(data[0])  # number of columns

    # Convert the cell indices to Excel notation (1-indexed)
    start_cell = xlsxwriter.utility.xl_rowcol_to_cell(0, 0)  # cell (1,1)
    end_cell = xlsxwriter.utility.xl_rowcol_to_cell(x - 1, y - 1)  # cell (x,y)

    # Prepare the list of column names and the data
    headers = data[0]
    table_data = data[1:]

    # Add the table
    worksheet.add_table(f'{start_cell}:{end_cell}',
                        {'data': table_data, 'columns': [{'header': header} for header in headers]})


def write_summary(worksheet, rows, headers, title_format, data_format):
    # Write Summary Data values
    total_cost = sum(row[3] for row in rows)
    total_price = sum(row[4] for row in rows)
    products_count = len(rows)
    products_count_title = _('Products Count')
    total_price_title = _('Total Price')
    total_cost_title = _('Total Cost')
    worksheet.set_column(0, len(headers) + 2, len(products_count_title))
    worksheet.set_column(1, len(headers) + 2, len(total_cost_title))
    worksheet.set_column(2, len(headers) + 2, len(total_price_title))
    worksheet.write(0, len(headers) + 2, products_count_title, title_format)
    worksheet.write(0, len(headers) + 3, products_count, data_format)
    worksheet.write(1, len(headers) + 2, total_cost_title, title_format)
    worksheet.write(1, len(headers) + 3, total_cost, data_format)
    worksheet.write(2, len(headers) + 2, total_price_title, title_format)
    worksheet.write(2, len(headers) + 3, total_price, data_format)


def write_data(worksheet, data):
    for i, row in enumerate(data):
        for j, value in enumerate(row):
            worksheet.write(i, j, value)


class NeedStockFileDownloader(http.Controller):
    @http.route('/stock_need_download', type='http', auth='user')
    def download_files(self, **kw):
        # Get the attachment ids from the URL parameters
        stock_recycling_header_id = http.request.session.get('stock_recycling_header_id', 0)
        data_dict = self._get_supplier_groups(stock_recycling_header_id)
        supplier_groups = data_dict['supplier_groups']
        file_name = data_dict['file_name']
        headers = data_dict['headers']

        # Create a BytesIO object for the ZIP file
        zip_io = io.BytesIO()
        with zipfile.ZipFile(zip_io, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for group in supplier_groups:
                # Create a BytesIO object for the Excel file
                excel_io = io.BytesIO()
                workbook = xlsxwriter.Workbook(excel_io, {'in_memory': True})
                worksheet = workbook.add_worksheet()

                # Write data to the XLSX file
                rows = list(group[1])

                data = [headers, *rows]

                # Create a format for the header
                title_format = workbook.add_format({'bold': True,
                                                    'bg_color': '#000000',
                                                    'color': '#ffffff', })
                title_format.set_border(style=1)

                data_format = workbook.add_format({'bold': True, })
                data_format.set_border(style=1)

                # Write the data
                write_data(worksheet, data)
                add_data_in_table(worksheet, data)
                adjust_columns_width(worksheet, headers)
                write_summary(worksheet, rows, headers, title_format, data_format)

                workbook.close()

                # Add the Excel file to the ZIP file
                zipf.writestr(f'{file_name}-{group[0]}.xlsx', excel_io.getvalue())

            # Reset the cursor of the BytesIO object to the beginning
        zip_io.seek(0)
        file_name += '.zip'
        encoded_file_name = quote(file_name.encode('utf-8'))

        return http.request.make_response(
            zip_io,
            headers=[
                ('Content-Type', 'application/octet-stream'),
                ('Content-Disposition', f"attachment; filename*=UTF-8''{encoded_file_name};"),
            ]
        )

    def _get_supplier_groups(self, stock_recycling_header_id):
        stock_need_model = http.request.env['ab_stock_recycling_need']

        need_lines = stock_need_model.search(
            [('header_id', '=', stock_recycling_header_id)])
        header_id = need_lines and need_lines[0].header_id
        time_string = datetime.now().strftime("__%Y-%m-%d___%H-%M-%S")
        file_name = f"{header_id.name}{time_string}" if header_id else f"file{time_string}"
        # file_name = f"file{time_string}"

        need_lines = sorted(need_lines, key=attrgetter('supplier_id.id', 'parent_item_id.id'))
        need_tuples = []
        need_groups = groupby(need_lines, key=lambda x: x.parent_item_id)
        for group in need_groups:
            item = group[0]
            lines = list(group[1])
            need_tuples.append(
                (item.company_id.name or '',
                 item.code,
                 item.name,
                 item.default_cost,
                 item.default_price,
                 sum(line.sales_qty for line in lines),
                 sum(line.balance for line in lines),
                 sum(line.qty for line in lines),
                 ))

        return {
            'supplier_groups': groupby(need_tuples, key=lambda x: x[0]),
            'file_name': file_name,
            'headers': (_('Supplier Name'),
                        _('Product Code'),
                        _('----- Product Name -----'),
                        _('Approx. Cost'),
                        _('Price'),
                        _('Sales'),
                        _('Balance'),
                        _('Required Quantity'))

        }
