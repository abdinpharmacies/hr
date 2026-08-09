from odoo import api, fields, models


class ProjectTask(models.Model):
    _inherit = 'project.task'

    ab_task_type = fields.Selection(
        [
            ('task', 'Task'),
            ('bug', 'Bug'),
            ('feature', 'Feature'),
            ('improvement', 'Improvement'),
            ('technical_debt', 'Technical Debt'),
        ],
        string='Task Type',
        default='task',
        required=True,
        tracking=True,
        index=True,
    )
    ab_story_points = fields.Float(string='Story Points', tracking=True)
    ab_reviewer_id = fields.Many2one(
        'res.users',
        string='Reviewer',
        tracking=True,
        domain="[('share', '=', False), ('active', '=', True)]",
    )
    ab_qa_user_id = fields.Many2one(
        'res.users',
        string='QA Responsible',
        tracking=True,
        domain="[('share', '=', False), ('active', '=', True)]",
    )
    ab_sprint_id = fields.Many2one(
        'ab.project.sprint',
        string='Sprint',
        tracking=True,
        index=True,
        domain="[('project_id', '=', project_id)]",
    )
    ab_release_id = fields.Many2one(
        'ab.project.release',
        string='Release',
        tracking=True,
        index=True,
        domain="[('project_id', '=', project_id)]",
    )
    ab_branch_url = fields.Char(string='Branch URL')
    ab_pull_request_url = fields.Char(string='Pull Request URL')
    ab_technical_notes = fields.Html(string='Technical Notes', sanitize_attributes=False, translate=True)
    ab_is_blocked = fields.Boolean(string='Blocked', tracking=True, index=True)
    ab_blocked_reason = fields.Text(string='Blocked Reason', tracking=True, translate=True)
    ab_bug_severity = fields.Selection(
        [
            ('low', 'Low'),
            ('medium', 'Medium'),
            ('high', 'High'),
            ('critical', 'Critical'),
        ],
        string='Severity',
        default='medium',
        tracking=True,
    )
    ab_bug_environment = fields.Selection(
        [
            ('local', 'Local'),
            ('staging', 'Staging'),
            ('production', 'Production'),
            ('customer', 'Customer Environment'),
            ('other', 'Other'),
        ],
        string='Environment',
        tracking=True,
    )
    ab_reproduction_steps = fields.Html(string='Reproduction Steps', sanitize_attributes=False, translate=True)
    ab_expected_result = fields.Html(string='Expected Result', sanitize_attributes=False, translate=True)
    ab_actual_result = fields.Html(string='Actual Result', sanitize_attributes=False, translate=True)

    @api.onchange('project_id')
    def _onchange_ab_project_id_reset_workflow_links(self):
        for task in self:
            if task.ab_sprint_id and task.ab_sprint_id.project_id != task.project_id:
                task.ab_sprint_id = False
            if task.ab_release_id and task.ab_release_id.project_id != task.project_id:
                task.ab_release_id = False

    def action_ab_toggle_blocked(self):
        for task in self:
            task.ab_is_blocked = not task.ab_is_blocked
        return True
