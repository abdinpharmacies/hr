# -*- coding: utf-8 -*-

import datetime

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

PARAM_STR = "%s"


class JournalEntriesInh(models.Model):
    _name = 'ab_accounting_je_line'
    _inherit = ['ab_accounting_je_line', 'ab_eplus_connect']

    vendor_id = fields.Many2one('abdin_eplus.vendor')
    msg = fields.Text(readonly=True)
    is_paid = fields.Boolean(default=False, readonly=True)

    # def _get_internal_type_selection(self):
    #     account_guide = self.env['ab_accounting_account_guide']
    #     account_guide_fields = account_guide.fields_get(allfields=['internal_type'])
    #     return account_guide_fields['internal_type']['selection']

    def btn_pay_bill(self):
        try:
            with self.connect_eplus(param_str=PARAM_STR, charset='UTF-8') as cnx:
                for rec in self:
                    bill_data = self._get_bill_data(rec, cnx)
                    rec.msg = self._check_bill_valid(cnx=cnx, **bill_data)
                    if not (rec.msg or self.is_paid):
                        self._pay_bill(cnx, **bill_data)
                        self.is_paid = True
                        self.flush_model()
        except Exception as ex:
            raise UserError(str(ex))

    def btn_check_bill_valid(self):
        with self.connect_eplus(param_str=PARAM_STR) as cnx:
            for rec in self:
                bill_data = self._get_bill_data(rec, cnx)
                rec.msg = self._check_bill_valid(cnx=cnx, **bill_data).strip()

    def btn_check_bill_valid_accountant(self):
        with self.connect_eplus(param_str=PARAM_STR) as cnx:
            for rec in self:
                bill_data = self._get_bill_data(rec, cnx)
                msg = self._check_bill_valid(cnx=cnx, **bill_data)
                rec.msg = msg and msg.strip() or ""
                if rec.msg:
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _("Not Valid ❌"),
                            'message': rec.msg or "",
                            'type': 'danger',  # types: success,warning,danger,info
                            'sticky': True,  # True/False will display for few seconds if false
                        },
                    }
                else:
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _("Valid ✔"),
                            'message': _("Valid ✔✔✔"),
                            'type': 'success',  # types: success,warning,danger,info
                            'sticky': True,  # True/False will display for few seconds if false
                        },
                    }

    @staticmethod
    def _get_bill_data(rec, cnx):
        return {'vendor': rec.vendor_id,
                'debit_val': rec.debit_val,
                'doc_no': rec.doc_no,
                'explain': rec.explain}

    ####################################################################################################
    def _check_bill_valid(self, cnx, vendor, debit_val, doc_no, explain, **kw):
        try:
            cursor = cnx.cursor()
            msg = ''
            if doc_no and doc_no.isdigit():
                doc_no = int(doc_no)
            else:
                raise UserError(_("Doc No must be integer"))

            # Get bill details from BeConnect
            cursor.execute("""
                select p.total_after_back, p.ven_id, p.pth_paid, v.ven_active  
                from pur_trans_h p 
                left join vendor v on p.ven_id = v.ven_id
                where p.pth_id=%s""", (doc_no,))

            bill_details = cursor.fetchone()
            if not bill_details or not bill_details[0]:
                msg += _('Bill Serial Not Found!')
            else:
                bill_value, ven_id, paid_value, vendor_active, *__ = bill_details
                vendor = self.env['abdin_eplus.vendor'].browse(int(ven_id))
                ven_code = vendor.ven_code
                if debit_val <= 0:
                    msg += _('Bill Value Is Zero!')
                if paid_value >= bill_value:
                    msg += _('\nThis Bill Has Been Paid Before!')
                elif bill_value > debit_val + 1:
                    if not (explain and explain.find(ven_code) != -1):
                        msg += _(
                            "\nThis is a partial payment, write vendor code %s in Explain to confirm!"
                        ) % ven_code

                if bill_value < 1:
                    msg += _('\nBill value is less than 1 LE, may be this bill is fully returned!')
                if debit_val > bill_value - paid_value + 1:
                    msg += _("\nEntered value more than available payment, available payment =%s") % str(
                        bill_value - paid_value)
                if vendor_active == '2' and explain.find(ven_code) == -1:
                    msg += _(
                        "\nThis vendor is not active, write vendor code %s in Explain to confirm!"
                    ) % ven_code

                if ven_id and vendor.search([('id', '=', ven_id)]):
                    self.vendor_id = int(ven_id)
                else:
                    msg += _('\nVendor not found, Please do replication!')
        except Exception as ex:
            raise UserError(_(f"Unknown Error ({type(ex).__name__}): {str(ex)}"))

        return msg

    ####################################################################################################
    def _pay_bill(self, cnx, debit_val, vendor, doc_no, **kw):
        msg = ""
        try:
            cursor = cnx.cursor()
            sql = """update  pur_trans_h 
            set pth_paid = pth_paid + %(pth_paid)s , 
            sec_update_date = %(sec_update_date)s,
            pth_notice = CONCAT(pth_notice,  %(pth_notice)s)
            where pth_id=%(pth_id)s"""

            # update purchase table
            _logger.info(f" ---from odoo by user {self.env.user.name}")
            cursor.execute(sql, {'pth_paid': debit_val,
                                 'pth_id': doc_no,
                                 'sec_update_date': datetime.datetime.now(),
                                 'pth_notice': f" ---from odoo by user {self.env.user.name}"
                                 })
            msg = "update pur_trans_h"

            # update vendor balance table
            sql = """
            Update Vendor 
            SET sec_update_date=getdate(),
            ven_current_credit=ven_current_credit - %s 
            Where ven_id=%s ;
            """
            cursor.execute(sql, (debit_val, vendor.id))
            msg = "update Vendor Balance"
            sql = """            
            INSERT INTO F_Notices (fn_type,fn_who_type,fn_value,fn_who_id,fn_cause_id,fn_notes,sec_insert_uid) 
            VALUES ('2','1',%s,%s,2, %s,1);
            """
            cursor.execute(sql, (debit_val, vendor.id, f'from_odoo_for_bill_no_{doc_no}'))
            msg = "update F_Notices"

            cnx.commit()
        except Exception as e:
            cnx.rollback()
            raise UserError(f"{debit_val}\n{vendor.id}\n{doc_no}\n{str(e)}\n{msg}")
