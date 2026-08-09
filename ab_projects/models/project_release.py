from odoo import api, fields, models
from odoo.addons.project.models.project_task import CLOSED_STATES


class AbProjectRelease(models.Model):
    _name = 'ab.project.release'
    _description = 'Project Release'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'release_date desc, id desc'

    name = fields.Char(string='Name / Version', required=True, tracking=True, translate=True)
    project_id = fields.Many2one(
        'project.project',
        required=True,
        index=True,
        ondelete='cascade',
        tracking=True,
        domain="[('is_template', '=', False)]",
    )
    company_id = fields.Many2one(related='project_id.company_id', store=True, export_string_translation=False)
    release_date = fields.Date(tracking=True)
    status = fields.Selection(
        [
            ('planned', 'Planned'),
            ('development', 'In Development'),
            ('testing', 'Testing'),
            ('released', 'Released'),
        ],
        default='planned',
        required=True,
        tracking=True,
    )
    description = fields.Html(translate=True)
    task_ids = fields.One2many('project.task', 'ab_release_id', string='Tasks', export_string_translation=False)
    task_count = fields.Integer(compute='_compute_metrics', string='Task Count', store=True)
    completed_task_count = fields.Integer(compute='_compute_metrics', string='Completed Tasks', store=True)
    bug_count = fields.Integer(compute='_compute_metrics', string='Bugs', store=True)
    open_bug_count = fields.Integer(compute='_compute_metrics', string='Open Bugs', store=True)
    progress = fields.Float(compute='_compute_metrics', string='Progress', store=True)

    @api.depends('task_ids.state', 'task_ids.ab_task_type')
    def _compute_metrics(self):
        for release in self:
            tasks = release.task_ids.filtered(lambda task: not task.is_template)
            completed = tasks.filtered(lambda task: task.state in CLOSED_STATES)
            bugs = tasks.filtered(lambda task: task.ab_task_type == 'bug')
            release.task_count = len(tasks)
            release.completed_task_count = len(completed)
            release.bug_count = len(bugs)
            release.open_bug_count = len(bugs.filtered(lambda task: task.state not in CLOSED_STATES))
            release.progress = release.task_count and len(completed) / release.task_count or 0.0

    def action_view_tasks(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('project.action_view_all_task')
        action.update({
            'display_name': self.env._('%s Tasks', self.name),
            'domain': [('ab_release_id', '=', self.id)],
            'context': {
                'default_project_id': self.project_id.id,
                'default_ab_release_id': self.id,
                'search_default_open_tasks': 1,
            },
        })
        return action
