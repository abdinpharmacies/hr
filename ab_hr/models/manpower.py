# -*- coding: utf-8 -*-
from odoo import models, api, fields
from odoo.tools.translate import _


class ManPower(models.Model):
    _name = 'ab_hr_manpower'
    _description = 'Workplace Man Power'

    workplace = fields.Many2one('ab_hr_department', required=True)
    workplace_region = fields.Many2one(related='workplace.workplace_region')
    job_title = fields.Many2one('ab_hr_job', required=True)
    territory = fields.Selection(selection=[('1', 'North'), ('2', 'South'), ('3', 'Both')], required=True)
    op_manpower = fields.Integer(required=True, string='Default Manpower')

    @api.depends('workplace.name', 'job_title.name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s/%s' % (
                rec.workplace.name or '',
                rec.job_title.name or '',
            )


class ManpowerNeed(models.Model):
    _name = 'ab_hr_manpower_need'
    _description = 'Manpower Need'
    _auto = False
    workplace = fields.Many2one('ab_hr_department')
    workplace_region = fields.Many2one(related='workplace.workplace_region')
    job_title = fields.Many2one('ab_hr_job')
    can_access_history = fields.Boolean(compute='_compute_can_access_history')
    territory = fields.Selection(selection=[('1', 'North'), ('2', 'South'), ('3', 'Both')])

    act_manpower = fields.Integer(string="Actual Manpower")
    op_manpower = fields.Integer(string='Default Manpower')
    need_manpower = fields.Integer(string='Required Manpower')
    urgent = fields.Char(compute='_compute_urgent', search='_search_urgent', string='Delay Per Days', compute_sudo=True)

    def _compute_can_access_history(self):
        for rec in self:
            is_coordinator = self.env.user.has_group('ab_hr.group_ab_hr_co')
            is_allowed_by_manager = (self.env.user.id in rec.job_title.access_history_user_ids.ids)
            rec.can_access_history = is_coordinator or is_allowed_by_manager

    def _compute_urgent(self):
        for rec in self:
            need = rec.need_manpower
            history = self.env['ab_hr_history_report'].sudo()
            if need < 0:
                limit = need * -1
                history = history.search([
                    ('workplace_id', '=', rec.workplace.id),
                    ('job_title_id', '=', rec.job_title.id),
                    ('territory', '=', rec.territory),
                    ('default_urgent', '=', True),
                ], order='action_date desc', limit=limit)

                rec.urgent = ', '.join(
                    ["%s days" % str(h.delay_per_day) for h in history if h.delay_per_day > 0])
            else:
                rec.urgent = ''

    def _search_urgent(self, operator, val):
        if operator == '!=':
            need_manpower = self.env['ab_hr_manpower_need'].search([('need_manpower', '<', 0)])
            manpower = []
            for rec in need_manpower:
                need = rec.need_manpower
                history = self.env['ab_hr_history_report'].sudo()
                if need < 0:
                    limit = need * -1
                    history = history.search([
                        ('workplace_id', '=', rec.workplace.id),
                        ('job_title_id', '=', rec.job_title.id),
                        ('territory', '=', rec.territory),
                        ('default_urgent', '=', True),
                    ], order='action_date desc', limit=limit)
                    if history and [h.delay_per_day for h in history if h.delay_per_day > 0]:
                        manpower.append(rec.id)
            if operator == '!=':
                return [('id', 'in', manpower)]
            return []

    def btn_history_detail(self):
        return {
            'name': _("History"),
            'type': 'ir.actions.act_window',
            'res_model': 'ab_hr_history_report',
            'view_mode': 'tree',
            'target': 'new',
            # @formatter:off
            'domain': [
                           ('workplace_id', '=', self.workplace.id),
                           ('job_title_id', '=', self.job_title.id),
                           ('territory', '=', self.territory),
                           ('manpower_effect', 'in', ['increase', 'decrease']),
                       ]
        }
    # @formatter:on

    def init(self):
        self.env.cr.execute("""
        drop view if exists %s;
    -----------------------------------------------------
    -----------------------------------------------------
    CREATE OR REPLACE VIEW %s
     AS    
            SELECT 
                man.id,
                man.workplace,
                man.job_title,
                man.territory,
                count(act.job_id) as act_manpower,
                man.op_manpower,
                (count(act.job_id) - coalesce(man.op_manpower,0)) as need_manpower
            FROM ab_hr_manpower man
            LEFT JOIN ab_hr_job_occupied act 
                ON act.workplace = man.workplace 
                    and act.job_id = man.job_title 
                    and act.territory = man.territory
                    and act.termination_date  is null 
                    and act.issue_date is null
            GROUP BY  man.id,man.job_title,man.workplace,man.territory,man.op_manpower

        """ % (self._table, self._table))
