from odoo import api, fields, models
from odoo.addons.project.models.project_task import CLOSED_STATES


class ProjectProject(models.Model):
    _inherit = 'project.project'

    ab_project_type_id = fields.Many2one('ab.project.type', string='Project Type', tracking=True)
    ab_technical_lead_id = fields.Many2one(
        'res.users',
        string='Technical Lead',
        tracking=True,
        domain="[('share', '=', False), ('active', '=', True)]",
    )
    ab_health = fields.Selection(
        [
            ('healthy', 'Healthy'),
            ('at_risk', 'At Risk'),
            ('critical', 'Critical'),
        ],
        string='Project Health',
        default='healthy',
        required=True,
        tracking=True,
    )
    ab_health_note = fields.Text(string='Health Note', translate=True)
    ab_repository_url = fields.Char(string='Repository URL', tracking=True)
    ab_documentation_url = fields.Char(string='Documentation URL', tracking=True)
    ab_staging_url = fields.Char(string='Staging URL', tracking=True)
    ab_production_url = fields.Char(string='Production URL', tracking=True)
    ab_sprint_ids = fields.One2many('ab.project.sprint', 'project_id', string='Sprints', export_string_translation=False)
    ab_release_ids = fields.One2many('ab.project.release', 'project_id', string='Releases', export_string_translation=False)

    ab_total_task_count = fields.Integer(compute='_compute_ab_dashboard_metrics', string='Total Tasks')
    ab_completed_task_count = fields.Integer(compute='_compute_ab_dashboard_metrics', string='Completed Tasks')
    ab_overdue_task_count = fields.Integer(compute='_compute_ab_dashboard_metrics', string='Overdue Tasks')
    ab_blocked_task_count = fields.Integer(compute='_compute_ab_dashboard_metrics', string='Blocked Tasks')
    ab_planned_hours = fields.Float(compute='_compute_ab_dashboard_metrics', string='Estimated Hours')
    ab_logged_hours = fields.Float(compute='_compute_ab_dashboard_metrics', string='Logged Hours')
    ab_story_points = fields.Float(compute='_compute_ab_dashboard_metrics', string='Story Points')
    ab_progress = fields.Float(compute='_compute_ab_dashboard_metrics', string='Progress')
    ab_current_sprint_id = fields.Many2one('ab.project.sprint', compute='_compute_ab_current_sprint', string='Current Sprint')
    ab_sprint_count = fields.Integer(compute='_compute_ab_workflow_counts', string='Sprint Count')
    ab_release_count = fields.Integer(compute='_compute_ab_workflow_counts', string='Release Count')
    ab_team_member_ids = fields.Many2many('res.users', compute='_compute_ab_team_member_ids', string='Team Members')
    ab_team_member_count = fields.Integer(compute='_compute_ab_team_member_ids', string='Team Size')

    @api.depends('tasks.state', 'tasks.date_deadline', 'tasks.ab_is_blocked', 'tasks.allocated_hours', 'tasks.total_hours_spent', 'tasks.ab_story_points')
    def _compute_ab_dashboard_metrics(self):
        today = fields.Datetime.now()
        for project in self:
            tasks = project.tasks.filtered(lambda task: not task.is_template)
            completed = tasks.filtered(lambda task: task.state in CLOSED_STATES)
            overdue = tasks.filtered(lambda task: task.date_deadline and task.date_deadline < today and task.state not in CLOSED_STATES)
            project.ab_total_task_count = len(tasks)
            project.ab_completed_task_count = len(completed)
            project.ab_overdue_task_count = len(overdue)
            project.ab_blocked_task_count = len(tasks.filtered('ab_is_blocked'))
            project.ab_planned_hours = sum(tasks.mapped('allocated_hours'))
            project.ab_logged_hours = sum(tasks.mapped('total_hours_spent'))
            project.ab_story_points = sum(tasks.mapped('ab_story_points'))
            project.ab_progress = len(tasks) and len(completed) / len(tasks) or 0.0

    @api.depends('ab_sprint_ids.status', 'ab_sprint_ids.date_start', 'ab_sprint_ids.date_end')
    def _compute_ab_current_sprint(self):
        today = fields.Date.context_today(self)
        for project in self:
            active_sprint = project.ab_sprint_ids.filtered(lambda sprint: sprint.status == 'active')[:1]
            if not active_sprint:
                active_sprint = project.ab_sprint_ids.filtered(
                    lambda sprint: sprint.date_start <= today <= sprint.date_end and sprint.status != 'completed'
                )[:1]
            project.ab_current_sprint_id = active_sprint

    @api.depends('ab_sprint_ids', 'ab_release_ids')
    def _compute_ab_workflow_counts(self):
        for project in self:
            project.ab_sprint_count = len(project.ab_sprint_ids)
            project.ab_release_count = len(project.ab_release_ids)

    @api.depends('tasks.user_ids', 'user_id', 'ab_technical_lead_id')
    def _compute_ab_team_member_ids(self):
        for project in self:
            users = project.tasks.user_ids | project.user_id | project.ab_technical_lead_id
            project.ab_team_member_ids = users
            project.ab_team_member_count = len(users)

    def _ab_task_action(self, name, domain):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('project.action_view_all_task')
        action.update({
            'display_name': name,
            'domain': [('project_id', '=', self.id), ('is_template', '=', False)] + domain,
            'context': {'default_project_id': self.id},
        })
        return action

    def action_ab_open_all_tasks(self):
        return self._ab_task_action(self.env._('%s Tasks', self.name), [])

    def action_ab_open_completed_tasks(self):
        return self._ab_task_action(self.env._('%s Completed Tasks', self.name), [('state', 'in', list(CLOSED_STATES))])

    def action_ab_open_overdue_tasks(self):
        return self._ab_task_action(
            self.env._('%s Overdue Tasks', self.name),
            [('date_deadline', '<', fields.Datetime.now()), ('state', 'not in', list(CLOSED_STATES))],
        )

    def action_ab_open_blocked_tasks(self):
        return self._ab_task_action(self.env._('%s Blocked Tasks', self.name), [('ab_is_blocked', '=', True)])

    def action_ab_open_sprints(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('%s Sprints', self.name),
            'res_model': 'ab.project.sprint',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }

    def action_ab_open_releases(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('%s Releases', self.name),
            'res_model': 'ab.project.release',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }
