from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AbAccountingFuture(models.Model):
    _name = 'ab_accounting_future'
    _description = 'ab_accounting_future'

    # Header and related fields
    header_id = fields.Many2one('ab_accounting_future_header', bypass_search_access=True, ondelete='restrict')
    store_id = fields.Many2one(related='header_id.store_id', readonly=False, store=True, required=True, precompute=True)

    costcenter_id = fields.Many2one('ab_costcenter', index=True, required=True)
    sett_costcenter_id = fields.Many2one('ab_costcenter', index=True)

    doc_no = fields.Char(related='header_id.doc_no', readonly=False, store=True, default="0")

    account_id = fields.Many2one(related='header_id.account_id', readonly=False, store=True, required=True, precompute=True)
    sett_account_id = fields.Many2one(related='header_id.sett_account_id', readonly=False, store=True, required=True, precompute=True)
    user_id = fields.Many2one('res.users', readonly=True,
                              store=True,
                              default=lambda self: self.env.user.id, )

    # Entry fields
    credit_val = fields.Float(default=0, required=True, digits=(16, 2), string='Credit Value')
    debit_val = fields.Float(default=0, required=True, digits=(16, 2), string='Debit Value')
    due_date = fields.Date(default=lambda self: self._context.get('date', fields.Date.context_today(self)),
                           index=True)
    explain = fields.Text(required=True)
    je_created = fields.Boolean(readonly=True, default=False)
    order_type = fields.Selection([
        ('deposit', 'Cash/Cheque Deposit'),
        ('payment', 'Cash/Cheque Payment'),
    ], required=True, default='deposit')

    def btn_create_je(self):
        if self.je_created:
            raise ValidationError(_("JE already created!"))

        target_je = {
            "due_date": self.due_date,
            "store_id": self.store_id.id,
            "costcenter_id": self.costcenter_id.id,
            "explain": self.explain,
            "debit_val": self.debit_val,
            "credit_val": self.credit_val,
            "account_id": self.account_id.id,
        }

        sett_je = {
            "due_date": self.due_date,
            "store_id": self.store_id.id,
            "costcenter_id": self.sett_costcenter_id.id or self.costcenter_id.id,
            "explain": self.explain,
            "debit_val": self.credit_val,
            "credit_val": self.debit_val,
            "account_id": self.sett_account_id.id,
        }

        account_header_mo = self.env['ab_accounting_je_header']
        account_header = account_header_mo.create({"account_id": self.account_id.id, "doctype_id": 7,
                                                   "line_ids": [
                                                       (0, 0, target_je),
                                                       (0, 0, sett_je),
                                                   ]})

        account_header.btn_post_je()
        self.sudo().je_created = True

        # Only confirm if current user is not Future JE creator
        if self.user_id.id != self.env.user.id:
            account_header.sudo_confirm_all_je()
