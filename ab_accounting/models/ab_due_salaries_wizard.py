from odoo import api, fields, models, _


class DueSalariesWizard(models.TransientModel):
    _name = 'ab_due_salaries_wizard'
    _description = 'ab_due_salaries_wizard'
    _rec_name = 'id'

    user_id = fields.Many2one('res.users', domain=[('share', '=', False)])
    costcenter_codes = fields.Text()
    payment_redirect_to_ids = fields.One2many('ab_due_salaries_payment_redirect_to',
                                              'user_id',
                                              compute='_compute_payment_redirect_to_ids', )

    costcenter_deduction_forbidden_ids = fields.One2many('ab_costcenter_deduction_forbidden',
                                                         'costcenter_id',
                                                         compute='_compute_costcenter_deduction_forbidden_ids', )

    costcenter_deduction_month_prevented_ids = fields.One2many('ab_costcenter_deduction_month_prevented',
                                                               'costcenter_id',
                                                               compute='_compute_costcenter_deduction_month_prevented_ids', )
    till_month = fields.Date()

    def btn_do_action(self):
        action_type = self.env.context.get('action_type')
        if action_type == 'add_redirected_ids':
            costcenter_ids = self._get_costcenter_ids()
            for cc_id in costcenter_ids:
                if cc_id not in self.payment_redirect_to_ids.mapped('costcenter_id.id'):
                    self.env['ab_due_salaries_payment_redirect_to'].create(
                        {'costcenter_id': cc_id, 'user_id': self.user_id.id})
        elif action_type == 'remove_redirected_ids':
            costcenter_ids = self._get_costcenter_ids()
            self.env['ab_due_salaries_payment_redirect_to'].search([('costcenter_id', 'in', costcenter_ids),
                                                                    ('user_id', '=', self.user_id.id), ]).unlink()
        elif action_type == 'add_forbidden_ids':
            costcenter_ids = self._get_costcenter_ids()
            self.add_forbidden_ids(costcenter_ids)

        elif action_type == 'remove_forbidden_ids':
            costcenter_ids = self._get_costcenter_ids()
            self.env['ab_costcenter_deduction_forbidden'].search([('costcenter_id', 'in', costcenter_ids), ]).unlink()

        elif action_type == 'add_month_prevented_ids':
            costcenter_ids = self._get_costcenter_ids()
            till_month = self.till_month
            self.add_month_prevented_ids(costcenter_ids, till_month)

        elif action_type == 'remove_month_prevented_ids':
            costcenter_ids = self._get_costcenter_ids()
            self.env['ab_costcenter_deduction_month_prevented'].search(
                [('costcenter_id', 'in', costcenter_ids), ]).unlink()

    def add_month_prevented_ids(self, costcenter_ids, till_month):
        for cc_id in costcenter_ids:
            self.env['ab_costcenter_deduction_month_prevented'].create(
                {'costcenter_id': cc_id, 'till_month': till_month})

    def add_forbidden_ids(self, costcenter_ids):
        for cc_id in costcenter_ids:
            if not self.env['ab_costcenter_deduction_forbidden'].search_count([('costcenter_id', '=', cc_id)]):
                self.env['ab_costcenter_deduction_forbidden'].create({'costcenter_id': cc_id})

    def _get_costcenter_ids(self):
        costcenter_codes = self.costcenter_codes or ""
        return self.env['ab_costcenter'].sudo().search([('code', 'in', costcenter_codes.split('\n'))]).ids

    @api.depends('user_id')
    def _compute_payment_redirect_to_ids(self):
        for rec in self:
            rec.payment_redirect_to_ids = self.env['ab_due_salaries_payment_redirect_to'].search(
                [('user_id', '=', rec.user_id.id)])

    def _compute_costcenter_deduction_forbidden_ids(self):
        for rec in self:
            rec.costcenter_deduction_forbidden_ids = self.env['ab_costcenter_deduction_forbidden'].search([])

    def _compute_costcenter_deduction_month_prevented_ids(self):
        for rec in self:
            rec.costcenter_deduction_month_prevented_ids = self.env['ab_costcenter_deduction_month_prevented'].search(
                [])


class DueSalariesSettings(models.Model):
    _name = 'ab_due_salaries_payment_redirect_to'
    _description = 'ab_due_salaries_payment_redirect_to'
    _rec_name = 'costcenter_id'
    costcenter_id = fields.Many2one('ab_costcenter', index=True, required=True, )
    costcenter_code = fields.Char(related='costcenter_id.code')
    user_id = fields.Many2one('res.users', index=True, required=True, domain=[('share', '=', False)])


class CostcentersDeductionForbidden(models.Model):
    _name = 'ab_costcenter_deduction_forbidden'
    _description = 'ab_costcenter_deduction_forbidden'
    _rec_name = 'costcenter_id'
    costcenter_id = fields.Many2one('ab_costcenter', index=True)
    costcenter_code = fields.Char(compute='_compute_costcenter_code')

    @api.depends('costcenter_id')
    def _compute_costcenter_code(self):
        for rec in self:
            rec.costcenter_code = rec.costcenter_id.code


class CostcentersDeductionPreventedMonth(models.Model):
    _name = 'ab_costcenter_deduction_month_prevented'
    _description = 'ab_costcenter_deduction_month_prevented'
    _rec_name = 'costcenter_id'
    costcenter_id = fields.Many2one('ab_costcenter', index=True)
    costcenter_code = fields.Char(compute='_compute_costcenter_code')
    till_month = fields.Date(required=True)

    @api.depends('costcenter_id')
    def _compute_costcenter_code(self):
        for rec in self:
            rec.costcenter_code = rec.costcenter_id.code
