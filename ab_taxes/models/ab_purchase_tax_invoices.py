import contextlib
from odoo import fields, models, _, api
import requests
from datetime import datetime, timedelta
import base64
import time


class PurchaseTaxInvoices(models.Model):
    _name = 'ab_purchase_tax_invoices'
    _description = 'purchase_tax_invoices'

    internal_id = fields.Char(required=True, index=True)
    uuid = fields.Char(required=True)
    submission_uuid = fields.Char(required=True)
    long_id = fields.Char(required=True)
    public_url = fields.Char(required=True)
    type_name = fields.Char(required=True)
    issuer_id = fields.Char(required=True, index=True)
    issuer_name = fields.Char(required=True)
    issuer_type = fields.Char(required=True)
    receiver_id = fields.Char(required=True)
    receiver_name = fields.Char(required=True)
    receiver_type = fields.Char(required=True)
    datetime_issued = fields.Datetime(required=True)
    datetime_received = fields.Datetime(required=True)
    total_sales = fields.Float(required=True)
    total_discount = fields.Float(required=True)
    net_amount = fields.Float(required=True)
    total_tax = fields.Float(compute='compute_total_tax', digits=(12, 3))
    total = fields.Float(required=True)
    reject_request_date = fields.Datetime()
    reject_request_delayed_date = fields.Datetime()
    decline_reject_request_date = fields.Datetime()
    status = fields.Char(required=True)
    pdf_file = fields.Binary(string='PDF')

    def name_get(self):
        return [
            (rec.id, f'{rec.internal_id} _ {rec.issuer_name}_ {rec.total} ')
            for rec in self
        ]

    def compute_total_tax(self):
        for rec in self:
            rec.total_tax = rec.total - rec.net_amount

    def btn_reject_tax_invoice(self):
        token = self._tax_api_token()
        for rec in self:
            url_get = "https://api.invoicing.eta.gov.eg/api/v1.0/documents/{0}/state".format(
                rec.uuid)
            body = {'status': 'rejected',
                    'reason': 'incorrect invoice from the seller'
                    }
            requests.get(url_get, data=body, headers={
                'Authorization': "Bearer {0}".format(token)})

    def btn_update_tax_invoices(self):
        token = self._tax_api_token()
        url_get = "https://api.invoicing.eta.gov.eg/api/v1.0/documents/search"
        continuationtoken = ''
        submissiondatefrom = self._get_submissiondatefrom()
        submissiondateto = self._get_submissiondateto(submissiondatefrom)
        while continuationtoken != 'EndofResultSet':
            params = {'submissionDateFrom': submissiondatefrom,
                      'submissionDateTo': submissiondateto,
                      'direction': 'Received',
                      'pageSize': '1000',
                      'continuationToken': continuationtoken,
                      }
            get_response = requests.get(url_get, params=params, headers={
                'Authorization': "Bearer {0}".format(token)})
            get_response_json = get_response.json()
            invoices = get_response_json['result']
            continuationtoken = get_response_json['metadata']['continuationToken'] or 'EndofResultSet'
            if invoices:
                self._push_invoices(invoices=invoices)

    def _get_submissiondatefrom(self):
        latest_record_date = self.search(
            [], order='datetime_received desc', limit=1).datetime_received
        if latest_record_date:
            latest_record_date = latest_record_date - timedelta(days=14)
            latest_record_date = latest_record_date.strftime(
                "%Y-%m-%dT%H:%M:%SZ")
        else:
            latest_record_date = '2020-01-01T00:00Z'
        return latest_record_date

    def _get_submissiondateto(self, submissiondatefrom=None):
        date_obj = datetime.strptime(submissiondatefrom, '%Y-%m-%dT%H:%M:%SZ')
        new_date_obj = date_obj + timedelta(days=31)
        return new_date_obj.strftime('%Y-%m-%dT%H:%M:%SZ')

    def _push_invoices(self, invoices=None):
        for invoice in invoices:
            invoice_exist = self.search(
                [('uuid', '=', invoice['uuid'])])
            if invoice_exist:
                self._write_tax_invoice_line(
                    invoice, invoice_exist)
            else:
                self._create_tax_invoice_line(invoice)

    def get_invoice_pdf(self):
        token = self._tax_api_token()
        attachments = self.env['ir.attachment'].search(
            [('res_model', '=', 'ab_purchase_tax_invoices'), ('res_field', '=', 'pdf_file')])
        record_ids = attachments.mapped('res_id')
        invoices = self.search([('id', 'not in', record_ids)])
        start_time = time.time()
        for rec in invoices:
            token = token if time.time() - start_time < 3600 else self._tax_api_token()
            with contextlib.suppress(Exception):
                url_get = "https://api.invoicing.eta.gov.eg/api/v1.0/documents/{0}/pdf".format(
                    rec.uuid)
                response = requests.get(url_get, headers={
                    'Authorization': "Bearer {0}".format(token), "Content-Type": "application/octet-stream"})
                if response.status_code == 200:
                    self.create_attachment(rec=rec, pdf=response.content)
                self.env.cr.commit()

    def create_attachment(self, rec=None, pdf=None):
        pdf_data_base64 = base64.b64encode(pdf)
        attachment = self.env['ir.attachment'].create({
            'name': f'{rec.uuid}-{rec.internal_id}.pdf',
            'datas': pdf_data_base64,
            'res_model': 'ab_purchase_tax_invoices',
            'res_id': rec.id,
            'res_field': 'pdf_file',
        })
        rec.pdf_file = pdf_data_base64

    def _tax_api_token(self):
        url_post = "https://id.eta.gov.eg/connect/token"
        credentials = {'grant_type': 'client_credentials',
                       'client_id': '7ffbcbcc-2f62-4e14-965a-6ca2959f0b14',
                       'client_secret': '214dbe99-1f46-4506-8b91-dcc0e30df3e2'}
        post_response = requests.post(url_post, data=credentials)
        post_response_json = post_response.json()
        return post_response_json['access_token']

    def _create_tax_invoice_line(self, json):
        self.create({'internal_id': json['internalId'],
                     'uuid': json['uuid'],
                     'submission_uuid': json['submissionUUID'],
                     'long_id': json['longId'],
                     'public_url': json['publicUrl'],
                     'type_name': json['documentTypeNamePrimaryLang'],
                     'issuer_id': json['issuerId'],
                     'issuer_name': json['issuerName'],
                     'issuer_type': json['issuerType'],
                     'receiver_id': json['receiverId'],
                     'receiver_name': json['receiverName'],
                     'receiver_type': json['receiverType'],
                     'datetime_issued': self._convert_time_zone(json['dateTimeIssued']),
                     'datetime_received': self._convert_time_zone(json['dateTimeReceived'], sec_part=True),
                     'total_sales': json['totalSales'],
                     'total_discount': json['totalDiscount'],
                     'net_amount': json['netAmount'],
                     'total': json['total'],
                     'reject_request_date': self._convert_time_zone(json['rejectRequestDate'], sec_part=True),
                     'reject_request_delayed_date': self._convert_time_zone(json['rejectRequestDelayedDate'],
                                                                            sec_part=True),
                     'decline_reject_request_date': self._convert_time_zone(json['declineRejectRequestDate'],
                                                                            sec_part=True),
                     'status': json['status']})

    def _write_tax_invoice_line(self, json, invoice_exist):
        invoice_exist.write({'internal_id': json['internalId'],
                             'uuid': json['uuid'],
                             'submission_uuid': json['submissionUUID'],
                             'long_id': json['longId'],
                             'public_url': json['publicUrl'],
                             'type_name': json['documentTypeNamePrimaryLang'],
                             'issuer_id': json['issuerId'],
                             'issuer_name': json['issuerName'],
                             'issuer_type': json['issuerType'],
                             'receiver_id': json['receiverId'],
                             'receiver_name': json['receiverName'],
                             'receiver_type': json['receiverType'],
                             'datetime_issued': self._convert_time_zone(json['dateTimeIssued']),
                             'datetime_received': self._convert_time_zone(json['dateTimeReceived'], sec_part=True),
                             'total_sales': json['totalSales'],
                             'total_discount': json['totalDiscount'],
                             'net_amount': json['netAmount'],
                             'total': json['total'],
                             'reject_request_date': self._convert_time_zone(json['rejectRequestDate'], sec_part=True),
                             'reject_request_delayed_date': self._convert_time_zone(json['rejectRequestDelayedDate'],
                                                                                    sec_part=True),
                             'decline_reject_request_date': self._convert_time_zone(json['declineRejectRequestDate'],
                                                                                    sec_part=True),
                             'status': json['status']})

    def _convert_time_zone(self, datetimeZone, sec_part=False):
        if datetimeZone:
            return (
                datetime.strptime(datetimeZone[:-2], "%Y-%m-%dT%H:%M:%S.%f")
                if sec_part
                else datetime.strptime(datetimeZone, "%Y-%m-%dT%H:%M:%SZ")
            )

    @api.model
    def _name_search(self, name='', args=None, operator='ilike', limit=100, name_get_uid=None):
        args = list(args or [])
        if name:
            args += [('internal_id', operator, name)]
        return self._search(args, limit=limit, access_rights_uid=name_get_uid)


"""
select inv.internal_id, pur.ven_bill_no,length(ven_bill_no) as ven_bill_len
,(SELECT abs(extract(day from pur.sec_insert_date::timestamp - inv.datetime_issued::timestamp))) diff
from ab_purchase_tax_invoices inv
join abdin_eplus_supplier ven on ven.ven_tel = inv.issuer_id
join abdin_eplus_pur_trans_h pur on ven.ven_id = pur.ven_id
where

(SELECT abs(extract(day from pur.sec_insert_date::timestamp - inv.datetime_issued::timestamp))) < 10

and
(pur.ven_bill_no = right(inv.internal_id, 16)
or  pur.ven_bill_no = right(inv.internal_id, 15)
or  pur.ven_bill_no = right(inv.internal_id, 14)
or  pur.ven_bill_no = right(inv.internal_id, 13)
or  pur.ven_bill_no = right(inv.internal_id, 12)
or  pur.ven_bill_no = right(inv.internal_id, 11)
or  pur.ven_bill_no = right(inv.internal_id, 10)
or  pur.ven_bill_no = right(inv.internal_id, 9)
or  pur.ven_bill_no = right(inv.internal_id, 8)
or  pur.ven_bill_no = right(inv.internal_id, 7)
or  pur.ven_bill_no = right(inv.internal_id, 6)
or  pur.ven_bill_no = right(inv.internal_id, 5)
or  pur.ven_bill_no = right(inv.internal_id, 4)
or  pur.ven_bill_no = right(inv.internal_id, 3))
order by ven_bill_len desc


"""
