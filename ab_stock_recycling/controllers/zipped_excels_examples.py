########################################################################
import pandas as pd
import zipfile
import io
from urllib.parse import quote
from odoo import models, http


class OdooModel(models.Model):
    _name = 'my_odoo_model'

    def btn_download_need_files(self):
        # Convert the list of ids to a string
        http.request.session['my_record_id'] = self.id
        # Return an action of type 'ir.actions.act_url'
        return {
            'type': 'ir.actions.act_url',
            'url': '/stock_need_download',
            'target': 'self',
        }


class NeedStockFileDownloader(http.Controller):
    @http.route('/stock_need_download', type='http', auth='user')
    def download_files(self, **kw):
        # Get the attachment ids from the URL parameters
        my_record_id = http.request.session.get('my_record_id', 0)
        odoo_model = http.request.env['my_odoo_model']

        data_to_excel = odoo_model.search([('id', '=', my_record_id)])

        # Assuming df1, df2 are your dataframes
        df1 = pd.DataFrame({'Data': [10, 20, 30, 20, 15, 30, 45]})
        df2 = pd.DataFrame({'Data': [100, 200, 300, 200, 150, 300, 450]})

        # Create a new zip file
        zip_buffer = io.BytesIO()

        # df_groups = df1.groupby(by=['Data'])

        with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
            for name, df in enumerate([df1, df2], 1):
                # Write each DataFrame to a BytesIO buffer
                excel_buffer = io.BytesIO()
                with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
                    df.to_excel(writer)

                # Write the BytesIO buffer to the zip file
                excel_buffer.seek(0)
                zip_file.writestr(f'{name}.xlsx', excel_buffer.read())

        # Properly close the ZipFile instance to finalize the archive
        zip_buffer.seek(0)

        # Reset the cursor of the BytesIO object to the beginning
        zip_buffer.seek(0)
        file_name = 'myfile_name.zip'
        encoded_file_name = quote(file_name.encode('utf-8'))

        return http.request.make_response(
            zip_buffer,
            headers=[
                ('Content-Type', 'application/octet-stream'),
                ('Content-Disposition', f"attachment; filename*=UTF-8''{encoded_file_name};"),
            ]
        )

###############################################
