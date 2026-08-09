from odoo import api, fields, models
from odoo.addons.project.models.project_task import CLOSED_STATES


class AbProjectSprint(models.Model):
    _name = 'ab.project.sprint'
    _description = 'Project Sprint'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_start desc, id desc'

    name = fields.Char(required=True, tracking=True, translate=True)
    project_id = fields.Many2one(
        'project.project',
        required=True,
        index=True,
        ondelete='cascade',
        tracking=True,
        domain="[('is_template', '=', False)]",
    )
    company_id = fields.Many2one(related='project_id.company_id', store=True, export_string_translation=False)
    goal = fields.Text(translate=True)
    date_start = fields.Date(string='Start Date', required=True, tracking=True)
    date_end = fields.Date(string='End Date', required=True, tracking=True)
    status = fields.Selection(
        [
            ('planning', 'Planning'),
            ('active', 'Active'),
            ('completed', 'Completed'),
        ],
        default='planning',
        required=True,
        tracking=True,
    )
    task_ids = fields.One2many('project.task', 'ab_sprint_id', string='Tasks', export_string_translation=False)
    planned_story_points = fields.Float(compute='_compute_metrics', string='Planned Story Points', store=True)
    completed_story_points = fields.Float(compute='_compute_metrics', string='Completed Story Points', store=True)
    task_count = fields.Integer(compute='_compute_metrics', string='Task Count', store=True)
    remaining_task_count = fields.Integer(compute='_compute_metrics', string='Remaining Tasks', store=True)
    completed_task_count = fields.Integer(compute='_compute_metrics', string='Completed Tasks', store=True)
    overdue_task_count = fields.Integer(compute='_compute_metrics', string='Overdue Tasks', store=True)
    blocked_task_count = fields.Integer(compute='_compute_metrics', string='Blocked Tasks', store=True)
    progress = fields.Float(compute='_compute_metrics', string='Progress', store=True)

    _date_order = models.Constraint(
        'CHECK(date_end >= date_start)',
        'Sprint end date must be on or after the start date.',
    )

    @api.depends('task_ids.ab_story_points', 'task_ids.state', 'task_ids.date_deadline', 'task_ids.ab_is_blocked')
    def _compute_metrics(self):
        today = fields.Datetime.now()
        for sprint in self:
            tasks = sprint.task_ids.filtered(lambda task: not task.is_template)
            completed = tasks.filtered(lambda task: task.state in CLOSED_STATES)
            overdue = tasks.filtered(lambda task: task.date_deadline and task.date_deadline < today and task.state not in CLOSED_STATES)
            sprint.task_count = len(tasks)
            sprint.completed_task_count = len(completed)
            sprint.remaining_task_count = len(tasks - completed)
            sprint.overdue_task_count = len(overdue)
            sprint.blocked_task_count = len(tasks.filtered('ab_is_blocked'))
            sprint.planned_story_points = sum(tasks.mapped('ab_story_points'))
            sprint.completed_story_points = sum(completed.mapped('ab_story_points'))
            sprint.progress = sprint.task_count and len(completed) / sprint.task_count or 0.0

    def action_view_tasks(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('project.action_view_all_task')
        action.update({
            'display_name': self.env._('%s Tasks', self.name),
            'domain': [('ab_sprint_id', '=', self.id)],
            'context': {
                'default_project_id': self.project_id.id,
                'default_ab_sprint_id': self.id,
                'search_default_open_tasks': 1,
            },
        })
        return action
