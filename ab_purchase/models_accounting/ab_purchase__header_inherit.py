from time import perf_counter

import datetime

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


def _normalize_je_amounts(vals):
    for field_name in ('debit_val', 'credit_val'):
        amount = vals.get(field_name)
        if amount is not None and -1 < amount < 0:
            vals[field_name] = 0
    return vals


class PurchaseHeaderInherit(models.Model):
    _name = 'ab_purchase_header'
    _inherit = ['ab_purchase_header', 'ab_purchase_je_line_data']

    is_closed = fields.Boolean(default=False)

    def btn_submit_inventory(self):
        start1 = perf_counter()
        res = super().btn_submit_inventory()
        start2 = perf_counter()
        # if start2 - start1 > 0.1:
        #     print(f"Inventory Takes {start2 - start1}")
        try:
            if not self.line_ids:
                return res

            sudo_self = self.sudo()
            # today = datetime.date.today()
            costcenter_id = self.supplier_id.costcenter_id.id
            supplier_account_id = sudo_self.env.ref('ab_accounting.ab_accounting_account_guide_suppliers').id
            vat_account_id = sudo_self.env.ref('ab_accounting.ab_accounting_account_guide_vat').id
            inventory_account_id = sudo_self.env.ref('ab_accounting.ab_accounting_account_guide_inventory').id

            # Preparing data
            supplier_data = {
                'account_id': supplier_account_id,
                'debit_val': 0,
                'credit_val': self.net_invoice
            }
            inventory_data = {
                'account_id': inventory_account_id,
                'debit_val': self.net_invoice - self.net_tax,
                'credit_val': 0
            }

            taxes_data = {
                # @todo: add 'ab_accounting_account_guide_vat' to account_guide.xml data
                # @todo: update res_id '' of 'ab_accounting_account_guide_vat' to
                'account_id': vat_account_id,
                'debit_val': self.net_tax,
                'credit_val': 0
            }

            fixed_data = {
                'store_id': self.store_id.id or 78,
                'due_date': self.doc_date,
                'doc_no': self.doc_code,
                'costcenter_id': costcenter_id,
                'explain': f'PURCHASE -- {self.description}',
            }

            if sudo_self.je_header_id.line_ids:
                sudo_self.je_header_id.sudo().line_ids.unlink()

            lines = [
                (0, 0, _normalize_je_amounts({**fixed_data, **supplier_data, })),
                (0, 0, _normalize_je_amounts({**fixed_data, **inventory_data, })),
                round(self.net_tax, 1) and (
                    0, 0, _normalize_je_amounts({**fixed_data, **taxes_data, })
                ),
            ]

            lines = [line for line in lines if line]

            sudo_self.je_header_id.write({
                'is_posted': True,
                'line_ids': lines
            })

            sudo_self.je_header_id.sudo_confirm_all_je()
        except ValidationError as ve:
            raise ValidationError(str(ve) + f"\nIN INVOICE ID: {self.id}.")

        start3 = perf_counter()
        # if start3 - start2 > 0.1:
        #     print(f"JE Takes {start3 - start2}")

        return res
