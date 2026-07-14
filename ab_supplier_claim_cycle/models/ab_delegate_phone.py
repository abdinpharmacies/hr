from odoo import api, models, fields


class AbDelegatePhone(models.Model):
    _name = 'ab.delegate.phone'
    _description = 'Delegate Phone Number'
    _rec_name = 'name'

    name = fields.Char(string='Phone Number', required=True)
    partner_id = fields.Many2one('ab_costcenter', string='Supplier')
    is_default = fields.Boolean(string='Default')

    @api.model
    def name_create(self, name):
        partner_id = self.env.context.get('default_partner_id')
        new = self.create({'name': name, 'partner_id': partner_id})
        return (new.id, new.display_name)

    def write(self, vals):
        if vals.get('is_default'):
            for rec in self:
                if rec.partner_id:
                    self.search([
                        ('partner_id', '=', rec.partner_id.id),
                        ('is_default', '=', True),
                        ('id', '!=', rec.id),
                    ]).write({'is_default': False})
        return super().write(vals)