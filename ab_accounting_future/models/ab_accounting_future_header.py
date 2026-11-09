from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AbAccountingFutureHeader(models.Model):
    _name = 'ab_accounting_future_header'
    _description = 'ab_accounting_future_header'
    _inherit = ['ab_data_from_excel', 'abdin_et.extra_tools']

    account_id = fields.Many2one('ab_accounting_account_guide',
                                 index=True,
                                 domain=[
                                     ('own_account', '=', True),
                                 ],
                                 bypass_search_access=True,
                                 required=True)

    sett_account_id = fields.Many2one('ab_accounting_account_guide',
                                      index=True,
                                      domain=[
                                          '|',
                                          ('own_account', '=', True),
                                          ('allow_account', '=', True)
                                      ],
                                      bypass_search_access=True, string='Settlement Account',
                                      required=True)

    user_id = fields.Many2one('res.users', readonly=True, default=lambda self: self.env.user.id)
    doc_no = fields.Char(default='0', index=True)
    store_id = fields.Many2one('ab_store', domain=lambda self: [('id', 'not in', self.env.user.store_ids.ids)]
                               , index=True)
    line_ids = fields.One2many('ab_accounting_future', 'header_id')
    from_excel = fields.Text()
    order_type = fields.Selection([
        ('deposit', 'Cash/Cheque Deposit'),
        ('payment', 'Cash/Cheque Payment'),
    ], required=True, default='deposit')

    def unlink(self):
        for rec in self:
            if rec.line_ids:
                raise ValidationError(_("Record has Lines, Delete Inner Lines First!"))
        res = super().unlink()
        return res

    def btn_add_data_from_excel(self):
        number_of_lines = len(self.from_excel.strip().split('\n')) - 1
        self.data_from_excel(model_name='ab_accounting_future',
                             x2many_field='line_ids',
                             excel_data=self.from_excel.strip('\n'), update_only=False)

        message = _("""<span class='h4 text-success'>%s</span> lines added  
        <span class='h4 text-success'>successfully</span>  
        by user <span class='h4 font-italic text-muted'>%s</span>""") % (number_of_lines, self.env.user.name)
        return self.ab_msg(message=message)
