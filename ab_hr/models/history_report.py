from odoo import models, fields, api, _


class HistoryReport(models.Model):
    _name = 'ab_hr_history_report'
    _description = 'History Report'
    _auto = False
    _order = 'action_date desc,id'
    employee_id = fields.Many2one('ab_hr_employee')
    job_id = fields.Many2one('ab_hr_job_occupied')
    accid = fields.Char(related='employee_id.accid')
    action_date = fields.Date()

    action_type = fields.Many2one('ab_hr_history_action_type')

    notes = fields.Text()

    def get_default_workplace(self):
        return self.employee_id.department_id.id

    def get_default_job(self):
        return self.employee_id.job_id.id

    workplace_id = fields.Many2one('ab_hr_department', string='Workplace')

    job_title_id = fields.Many2one('ab_hr_job', string='Job Title')

    territory = fields.Selection(selection=[('1', 'North'), ('2', 'South'), ('3', 'Both')],
                                 required=True, string='Territory')
    workplace_region = fields.Many2one(related='workplace_id.workplace_region')
    parent_department_id = fields.Many2one(related='workplace_id.parent_id', string='Superior Department')

    payroll_action_month = fields.Char()

    is_applied = fields.Boolean()
    alt_job_id = fields.Many2one('ab_hr_emp_history', string='Alternative Job')
    start_fir_date = fields.Date()
    replacement_date = fields.Date(related='alt_job_id.action_date', string="Replacement Date")
    termination_date = fields.Date(related='job_id.termination_date', string="Termination Date")
    manpower_effect = fields.Selection(selection=[('increase', 'Increase'),
                                                  ('decrease', 'Decrease'),
                                                  ('no_effect', 'No Effect'), ], )

    delay_per_day = fields.Integer()
    default_urgent = fields.Boolean()
    urgent = fields.Boolean(compute='_compute_urgent')

    def _compute_urgent(self):
        for rec in self:
            need_manpower = self.env['ab_hr_manpower_need'].search([
                ('workplace', '=', rec.workplace_id.id),
                ('job_title', '=', rec.job_title_id.id),
                ('territory', '=', rec.territory),
            ])
            need = need_manpower.need_manpower
            if need < 0:
                limit = need * -1
                history = self.env['ab_hr_history_report'].search([
                    ('workplace_id', '=', rec.workplace_id.id),
                    ('job_title_id', '=', rec.job_title_id.id),
                    ('territory', '=', rec.territory),
                    ('default_urgent', '=', True),
                ], order='action_date desc', limit=limit)

                if rec.id in history.ids and history.filtered(lambda r: r.delay_per_day > 0 and r.id == rec.id):
                    rec.urgent = True
                else:
                    rec.urgent = False
            else:
                rec.urgent = False

    active = fields.Boolean()

    def init(self):
        self.env.cr.execute("""
        drop view if exists %(view_name)s;
    -----------------------------------------------------
    -----------------------------------------------------
    CREATE OR REPLACE VIEW %(view_name)s
     AS
    SELECT
    row_number()
    OVER(ORDER BY subq.id2,subq.id1) as id,* FROM (
        SELECT
            row_number() OVER(ORDER BY hi.id) as id1,
            hi.id as id2,
            hi.employee_id,
            hi.job_id,
            hi.action_date,
            hi.action_type,
            hi.notes,
            hi.old_workplace as workplace_id,
            hi.old_job_title as job_title_id,
            hi.territory as territory,
            hi.payroll_action_month,
            hi.alt_job_id,
            hi.start_fir_date,
            hi.is_applied,
            CASE WHEN  hact.allowed_delay > 0
                    AND (hi.job_id is Null 
                        or job.issue_date IS NOT NULL 
                        or job.termination_date IS NOT NULL 
                        or hact.manpower_effect_type='double_effect')
                THEN CURRENT_DATE - (hi.action_date + hact.allowed_delay)
            ELSE 0
            END as delay_per_day,
            hi.active,
            CASE
                WHEN hact.manpower_effect_type='double_effect' THEN 'decrease'
                ELSE  hact.manpower_effect_type
            END as manpower_effect,
            CASE 
                WHEN hact.manpower_effect_type in ('decrease','increase') 
                    AND job.id IS NOT NULL
                    AND job.issue_date IS NULL 
                    AND job.termination_date IS NULL 
                THEN FALSE
                WHEN hact.manpower_effect_type in ('decrease','double_effect')
                THEN TRUE
                ELSE FALSE
            END as default_urgent
            
        FROM ab_hr_emp_history hi
        LEFT JOIN ab_hr_history_action_type hact on hact.id = hi.action_type
        LEFT JOIN ab_hr_job_occupied job on job.id = hi.job_id
            UNION ALL
        SELECT
            row_number() OVER(ORDER BY hi.id)*2 as id1,
            hi.id as id2,
            hi.employee_id,
            hi.job_id,
            hi.action_date,
            hi.action_type,
            hi.notes,
            COALESCE(hi.new_workplace, hi.old_workplace) as workplace_id,
            COALESCE(hi.new_job_title, hi.old_job_title) as job_title_id,
            COALESCE(hi.new_territory, hi.territory) as territory,
            hi.payroll_action_month,
            hi.alt_job_id,
            hi.start_fir_date,
            hi.is_applied,
            0 as delay_per_day,
            hi.active,
            'increase' as manpower_effect,
            FALSE as default_urgent  
        FROM ab_hr_emp_history hi
        LEFT JOIN ab_hr_history_action_type hact on hact.id = hi.action_type
        WHERE hact.manpower_effect_type = 'double_effect'
        ) as subq  """ % {'view_name': self._table})
