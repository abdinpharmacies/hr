from odoo import api, fields, models, _


class ClsUserAuth(models.Model):
    _name = 'res.users'
    _inherit = 'res.users'

    accounting_auth_group_id = fields.Many2one('ab_accounting_auth_group')

    account_auth_ids = fields.One2many(related='accounting_auth_group_id.account_auth_ids')
    doctype_ids = fields.Many2many(related='accounting_auth_group_id.doctype_ids')
    allowed_field_ids = fields.One2many(related='accounting_auth_group_id.allowed_field_ids')

    store_ids = fields.Many2many(comodel_name="ab_store",
                                 relation="ab_store_user_auth_rel",
                                 column1="user_id",
                                 column2="acc_id",
                                 string="Forbidden Store Auth", )

    costcenter_ids = fields.Many2many(comodel_name="ab_costcenter",
                                      compute='_compute_costcenter_ids',
                                      compute_sudo=True)

    responsible_for_ids = fields.Many2many(comodel_name='res.users',
                                           relation='ab_accounting_users_users_rel',
                                           column1='responsible_id',
                                           column2='user_id',
                                           context={'active_test': False})

    @api.depends('responsible_for_ids')
    def _compute_costcenter_ids(self):
        for rec in self:
            costcenters_for_manager = self.env['ab_costcenter']
            costcenters_for_user = self.env['ab_due_salaries_payment_redirect_to'].search(
                [('user_id', '=', rec.id)]).mapped('costcenter_id')
            for responsible in rec.responsible_for_ids:
                costcenters_for_manager += self.env['ab_due_salaries_payment_redirect_to'].search(
                    [('user_id', '=', responsible.id)]).mapped('costcenter_id')
            costcenter_ids = costcenters_for_user + costcenters_for_manager
            rec.costcenter_ids = costcenter_ids

    def remove_branch_auth(self):
        self.ensure_one()
        self.write({'store_ids': [(5, 0, 0)]})

    def btn_all_branch_auth(self):
        self.ensure_one()
        self.write({
            'store_ids': self.env['ab_store'].search([])
        })
