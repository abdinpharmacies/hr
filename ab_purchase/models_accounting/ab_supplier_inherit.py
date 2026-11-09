from odoo import api, fields, models, _


class AbSupplier(models.Model):
    _name = 'ab_supplier'
    _inherit = 'ab_supplier'

    def write(self, vals):
        if 'costcenter_id' in vals:
            je_mo = self.env['ab_accounting_je_header'].sudo()
            pur_mo = self.env['ab_purchase_header'].sudo()
            pur_notice_mo = self.env['ab_purchase_notice_header'].sudo()
            pur_headers = pur_mo.search([('supplier_id', '=', self.id)])
            pur_notice_headers = pur_notice_mo.search([('supplier_id', '=', self.id)])

            je_pur_headers = je_mo.search([
                ('res_header_ref', '=', 'ab_purchase_header'),
                ('res_header_id', 'in', pur_headers.ids),
            ])
            je_pur_notice_headers = je_mo.search([
                ('res_header_ref', '=', 'ab_purchase_notice_header'),
                ('res_header_id', 'in', pur_notice_headers.ids),
            ])

            je_pur_headers.line_ids.write({'costcenter_id': vals['costcenter_id']})
            je_pur_notice_headers.line_ids.write({'costcenter_id': vals['costcenter_id']})

        return super().write(vals)
