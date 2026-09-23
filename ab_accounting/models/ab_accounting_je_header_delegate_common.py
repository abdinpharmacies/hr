from odoo import api, fields, models, _


class AccountingHeaderCommon(models.AbstractModel):
    """Inherit this model so if:
        1. add je_header_id field.
        2. override:
            a. unlink method to delete je_header too.
            b. write method to write res_header_ref and res_header_id.
            c. create method to set res_header_ref and res_header_id.
    """

    _name = 'ab_accounting_je_header_delegate_common'
    _description = 'ab_accounting_je_header_delegate_common'

    je_header_id = fields.Many2one('ab_accounting_je_header',
                                   delegate=True,
                                   ondelete='cascade', required=True, index=True)

    je_header_ro_id = fields.Many2one(related='je_header_id', string='J.E. Header')

    _model_map = {}

    def unlink(self):
        for rec in self:
            rec.je_header_id.unlink()

        res = super().unlink()
        return res

    def write(self, vals):
        self = self.with_context(from_header=True)
        res = super().write(vals)
        for rec in self:
            if not rec.je_header_id.res_header_id:
                rec.je_header_id.res_header_id = rec.id
            if not rec.je_header_id.res_header_ref:
                rec.je_header_id.res_header_ref = rec._name
        return res

    @api.model
    def create(self, values):
        res = super().create(values)
        res.je_header_id.res_header_id = res.id
        res.je_header_id.res_header_ref = res._name
        return res
