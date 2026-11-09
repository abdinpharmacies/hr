# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models
from datetime import datetime
import base64
import io
import zipfile


class AccountSalesJe(models.TransientModel):
    _name = 'ab_download_tax_invoices_pdf_wizard'
    _description = 'ab_download_tax_invoices_pdf_wizard'

    start_date = fields.Datetime(default=datetime.now(), required=True)
    end_date = fields.Datetime(default=datetime.now(), required=True)
    issuer_id = fields.Char()

    def action_confirm(self):
        attachments = self.env['ir.attachment'].sudo().search(
            [('res_model', '=', 'ab_purchase_tax_invoices'), ('res_field', '=', 'pdf_file')])
        record_ids = attachments.mapped('res_id')
        if self.issuer_id:
            records = self.env['ab_purchase_tax_invoices'].search([('datetime_issued', '>=', self.start_date),
                                                                   ('datetime_issued',
                                                                    '<=', self.end_date),
                                                                   ('issuer_id', '=',
                                                                    self.issuer_id),
                                                                   ('id', 'in',
                                                                    record_ids)
                                                                   ])
        else:
            records = self.env['ab_purchase_tax_invoices'].search([('datetime_issued', '>=', self.start_date),
                                                                   ('datetime_issued',
                                                                    '<=', self.end_date),
                                                                   ('id', 'in',
                                                                    record_ids)
                                                                   ])
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zf:
            for record in records:
                attachment = attachments.filtered(
                    lambda a: a.res_id == record.id)
                folder_name = record.issuer_id
                zf.writestr(f'{folder_name}/{attachment.name}',
                            base64.b64decode(attachment.datas))
        zip_attachment = self.env['ir.attachment'].sudo().create({
            'name': f'{self.end_date}-{self.start_date}.zip',
            'datas': base64.b64encode(zip_buffer.getvalue()),
            'mimetype': 'application/zip',
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{zip_attachment.id}/{zip_attachment.name}?download=true',
            'target': 'self',
        }
