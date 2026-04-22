from odoo import models, fields, api

class PayrollRuleSystem(models.Model):
    _name = 'payroll.rule.system'
    _description = 'Payroll Rule System'

    name = fields.Char(string='System Name', required=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed')
    ], string='State', default='draft')
    policy_type = fields.Selection([
        ('daily_hours', 'Daily Hours System'),
        ('fixed_monthly', 'Fixed Monthly System'),
        ('mixed', 'Mixed/Custom System')
    ], string='Policy Type', readonly=True)
    policy_narrative = fields.Html(string='Policy Analysis', readonly=True)
    user_instructions = fields.Text(string='User Instructions', help="Enter any notes for the AI engine (e.g., handle column X as net salary)")
    rule_ids = fields.One2many('payroll.rule.item', 'system_id', string='Rules')

    def action_confirm(self):
        self.write({'state': 'confirmed'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})

class PayrollRuleItem(models.Model):
    _name = 'payroll.rule.item'
    _description = 'Payroll Rule Item'
    _order = 'sequence'

    name = fields.Char(string='Rule Name', required=True)
    code = fields.Char(string='Code', required=True, help="Used in other equations")
    equation = fields.Text(string='Equation', required=True, help="Python equation, example: basic * 0.30")
    sequence = fields.Integer(string='Sequence', default=10)
    system_id = fields.Many2one('payroll.rule.system', string='Rule System', ondelete='cascade')

    _sql_constraints = [
        ('code_uniq', 'unique(system_id, code)', 'Code must be unique within the system!')
    ]
