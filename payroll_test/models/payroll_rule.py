from odoo import models, fields, api

class PayrollRuleSystem(models.Model):
    _name = 'payroll.rule.system'
    _description = 'نظام قواعد الرواتب'

    name = fields.Char(string='اسم النظام', required=True)
    state = fields.Selection([
        ('draft', 'مسودة (تحت المراجعة)'),
        ('confirmed', 'معتمد (قيد التطبيق)')
    ], string='الحالة', default='draft')
    policy_type = fields.Selection([
        ('daily_hours', 'نظام ساعات يومية'),
        ('fixed_monthly', 'نظام شهري ثابت'),
        ('mixed', 'نظام مختلط / مخصص')
    ], string='نوع السياسة المستنتجة', readonly=True)
    policy_narrative = fields.Html(string='تقرير فهم النظام (Policy Analysis)', readonly=True)
    user_instructions = fields.Text(string='تعليمات إضافية للمحرك الذكي', help="اكتب هنا أي ملاحظات تريد أن يأخذها المحرك في الاعتبار (مثلاً: تعامل مع عمود X كعمود الصافي)")
    rule_ids = fields.One2many('payroll.rule.item', 'system_id', string='القواعد')

    def action_confirm(self):
        self.write({'state': 'confirmed'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})

class PayrollRuleItem(models.Model):
    _name = 'payroll.rule.item'
    _description = 'بند قاعدة الراتب'
    _order = 'sequence'

    name = fields.Char(string='اسم البند', required=True)
    code = fields.Char(string='الكود البرمجي', required=True, help="يستخدم هذا الكود داخل المعادلات الأخرى")
    equation = fields.Text(string='المعادلة', required=True, help="معادلة برمجية بايثون، مثال: basic * 0.30")
    sequence = fields.Integer(string='التسلسل', default=10)
    system_id = fields.Many2one('payroll.rule.system', string='نظام القواعد', ondelete='cascade')

    _sql_constraints = [
        ('code_uniq', 'unique(system_id, code)', 'الكود البرمجي يجب أن يكون فريداً داخل النظام الواحد!')
    ]
