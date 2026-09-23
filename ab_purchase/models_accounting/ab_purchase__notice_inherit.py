from odoo import api, fields, models, _
from odoo.exceptions import UserError


def _normalize_je_amounts(vals):
    for field_name in ('debit_val', 'credit_val'):
        amount = vals.get(field_name)
        if amount is not None and -1 < amount < 0:
            vals[field_name] = 0
    return vals


class PurchaseNoticeHeader(models.Model):
    _name = 'ab_purchase_notice_header'
    _inherit = ['ab_purchase_notice_header']

    def btn_submit_inventory(self):
        res = super().btn_submit_inventory()
        if not self.line_ids:
            return res

        sudo_self = self.sudo()
        # today = datetime.date.today()

        store_id = self.line_ids[0].last_inventory_id.store_id.id

        costcenter_id = self.supplier_id.costcenter_id.id
        supplier_account_id = sudo_self.env.ref('ab_accounting.ab_accounting_account_guide_suppliers').id
        vat_account_id = sudo_self.env.ref('ab_accounting.ab_accounting_account_guide_vat').id
        inventory_account_id = sudo_self.env.ref('ab_accounting.ab_accounting_account_guide_inventory').id
        # Preparing data
        supplier_data = {
            'account_id': supplier_account_id,
            'debit_val': self.total_cost,
            'credit_val': 0
        }
        inventory_data = {
            'account_id': inventory_account_id,
            'debit_val': 0,
            'credit_val': self.total_cost - self.total_taxes_value
        }

        taxes_data = {
            # @todo: add 'ab_accounting_account_guide_vat' to account_guide.xml data
            # @todo: update res_id '' of 'ab_accounting_account_guide_vat' to
            'account_id': vat_account_id,
            'debit_val': 0,
            'credit_val': self.total_taxes_value
        }
        pur_doc_codes = self.purchase_header_id.doc_code
        doc_code = (pur_doc_codes and pur_doc_codes) or self.doc_code or '0'

        fixed_data = {
            'store_id': store_id or 78,
            'costcenter_id': costcenter_id,
            'due_date': self.doc_date,
            'doc_no': doc_code,
            'explain': ('NOTICE' if self.purchase_header_id else 'G.NOTICE') + f' -- {self.description}',
        }

        lines = [
            (0, 0, _normalize_je_amounts({**fixed_data, **supplier_data, })),
            (0, 0, _normalize_je_amounts({**fixed_data, **inventory_data, })),
            round(self.total_taxes_value, 1) and (
                0, 0, _normalize_je_amounts({**fixed_data, **taxes_data, })
            ),
        ]
        lines = [line for line in lines if line]
        if sudo_self.je_header_id.line_ids:
            sudo_self.je_header_id.line_ids.unlink()

        sudo_self.je_header_id.write({
            'is_posted': True,
            'line_ids': lines
        })

        sudo_self.je_header_id.sudo_confirm_all_je()

        return res

    def adjust_notice_jes(self, eplus_serials=None):
        domain = [('status', '=', 'saved')]
        # domain = []
        if eplus_serials:
            domain = [('eplus_serial_calc', 'in', eplus_serials)]
        try:
            self = self.with_context(from_header=True, sudo_confirm=True)
            pur_notice_mo = self.env['ab_purchase_notice_header'].sudo()
            notices = pur_notice_mo.search(domain)
            supplier_account = self.env.ref('ab_accounting.ab_accounting_account_guide_suppliers')
            inventory_account = self.env.ref('ab_accounting.ab_accounting_account_guide_inventory')
            tax_account = self.env.ref('ab_accounting.ab_accounting_account_guide_vat')
            for n in self.web_progress_iter(notices, msg='Looping Notices ...'):
                lines = n.je_header_id.line_ids
                supplier_line = lines.filtered(lambda l: l.account_id == supplier_account)
                inventory_line = lines.filtered(lambda l: l.account_id == inventory_account)
                tax_line = lines.filtered(lambda l: l.account_id == tax_account)

                total_cost = n.total_cost
                supplier_debit_val = total_cost if total_cost > 0 else 0
                supplier_credit_val = total_cost * -1 if total_cost < 0 else 0

                total_taxes = n.total_taxes_value
                taxes_credit_val = total_taxes if total_taxes > 0 else 0
                taxes_debit_val = total_taxes * -1 if total_taxes < 0 else 0

                inventory_val = total_cost - total_taxes
                inventory_credit_val = inventory_val if inventory_val > 0 else 0
                inventory_debit_val = inventory_val * -1 if inventory_val < 0 else 0

                vals = [
                    (1, supplier_line.id, {'debit_val': supplier_debit_val, 'credit_val': supplier_credit_val}),
                    (1, inventory_line.id, {'debit_val': inventory_debit_val, 'credit_val': inventory_credit_val}),
                ]

                if tax_line:
                    vals.append((1, tax_line.id, {'debit_val': taxes_debit_val, 'credit_val': taxes_credit_val}))
                elif total_taxes:
                    vals.append((0, 0,
                                 {
                                     'account_id': tax_account.id,
                                     'costcenter_id': supplier_line.costcenter_id.id,
                                     'store_id': supplier_line.store_id.id,
                                     'doc_no': supplier_line.doc_no,
                                     'explain': supplier_line.explain,
                                     'due_date': supplier_line.due_date,
                                     'debit_val': taxes_debit_val,
                                     'credit_val': taxes_credit_val
                                 }))
                n.je_header_id.write({'line_ids': vals})
        except Exception as ex:
            raise UserError(f"adjust_notice_jes: {repr(ex)}")
