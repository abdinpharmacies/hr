from datetime import date

from odoo import models
from odoo.exceptions import UserError


class AbPurchaseHeader(models.Model):
    _name = 'ab_purchase_header'
    _inherit = ['ab_purchase_header', 'ab_eplus_connect']

    def write(self, values):
        old_supplier_serials = self.mapped('supplier_id.eplus_serial')
        res = super().write(values)
        for i, rec in enumerate(self):
            old_supplier_serial = old_supplier_serials[i] if len(old_supplier_serials) > (i + 1) else 0
            if rec.status != 'prepending':
                to_update_set = {'supplier_id', 'doc_code', 'doc_date', 'description'} & set(values)
                if to_update_set:
                    rec._change_pur_data_on_eplus(old_supplier_serial, to_update_set)

        return res

    def _change_pur_data_on_eplus(self, old_supplier_serial, to_update_set):
        with self.connect_eplus(param_str='?') as cnx:
            with cnx.cursor() as crx:
                try:
                    if 'supplier_id' in to_update_set:
                        self._change_pur_supplier(crx)
                        self._change_pur_suppliers_balance(crx, old_supplier_serial)
                    if 'doc_code' in to_update_set:
                        self._change_pur_doc_code(crx)
                    if 'doc_date' in to_update_set:
                        self._change_pur_doc_date(crx)
                    if 'description' in to_update_set:
                        self._change_pur_description(crx)

                    cnx.commit()
                except Exception as e:
                    cnx.rollback()
                    raise UserError(repr(e))

    def _change_pur_doc_code(self, crx):
        crx.execute("""
                    BEGIN TRY        
                        UPDATE pur_trans_h SET ven_bill_no=? WHERE pth_id=?
                    END TRY
                    BEGIN CATCH

                    END CATCH   

                    """, (self.doc_code, self.eplus_serial,))

    def _change_pur_doc_date(self, crx):
        crx.execute("""
                    BEGIN TRY        
                        UPDATE pur_trans_h SET ven_bill_date=? WHERE pth_id=?
                    END TRY
                    BEGIN CATCH

                    END CATCH   

                    """, (self.doc_date, self.eplus_serial,))

    def _change_pur_description(self, crx):
        crx.execute("""
                    BEGIN TRY        
                        UPDATE pur_trans_h SET pth_notice=? WHERE pth_id=?
                    END TRY
                    BEGIN CATCH

                    END CATCH   

                    """, (self.description, self.eplus_serial,))

    ###############################################################################################
    def _change_pur_supplier(self, crx):
        new_supplier_serial = self.supplier_id.eplus_serial
        crx.execute("""
        BEGIN TRY        
            UPDATE pur_trans_h SET ven_id=? WHERE pth_id=?
        END TRY
        BEGIN CATCH

        END CATCH   

        """, (new_supplier_serial, self.eplus_serial,))

    ###############################################################################################
    def _change_pur_suppliers_balance(self, crx, old_supplier_serial):
        new_supplier_serial = self.supplier_id.eplus_serial

        sql = """
        BEGIN TRY
            update Vendor set ven_current_credit=ven_current_credit
            -(select top 1 h.total_bill from pur_trans_h h where pth_id=? ) 
            where ven_id=?

        END TRY
        BEGIN CATCH

        END CATCH   

            """

        crx.execute(sql, (self.eplus_serial, old_supplier_serial,))

        sql = """
        BEGIN TRY        
            update Vendor set ven_current_credit=ven_current_credit
            +(select top 1 h.total_bill from pur_trans_h h where pth_id=? ) 
            where ven_id=?
        END TRY
        BEGIN CATCH

        END CATCH   

        """

        crx.execute(sql, (self.eplus_serial, new_supplier_serial,))
