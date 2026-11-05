from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class SavedReply(models.Model):
    _name = 'ab_crm_saved_reply'
    _inherit = 'ab_crm_scoped'
    _description = 'Channel Saved Reply'

    name = fields.Char(required=True)
    body = fields.Text(required=True)
    active = fields.Boolean(default=True)

    def _maintain(self):
        self._staff_action()
        if not (
            self.env.user.has_group('ab_crm_core.group_manager')
            or self.env.user.has_group('base.group_system')
        ):
            raise AccessError(_('Only managers can maintain saved replies.'))

    @api.model_create_multi
    def create(self, values_list):
        self._maintain()
        return super().create(values_list)

    def write(self, values):
        self._maintain()
        return super().write(values)

    @api.constrains('body')
    def _check_body(self):
        if any(not r.body.strip() or len(r.body) > 4096 for r in self):
            raise ValidationError(
                _('Replies must contain between 1 and 4096 characters.')
            )


class Conversation(models.Model):
    _inherit = 'ab_crm_conversation'

    def workspace_templates(self):
        self._workspace_scope()
        return {
            'items': self.env['ab_crm_saved_reply'].search_read(
                [('branch_id', '=', self.branch_id.id)], ['name', 'body']
            ),
            'can_manage': self.env.user.has_group('ab_crm_core.group_manager')
            or self.env.user.has_group('base.group_system'),
        }

    def save_template(self, name, body, template_id=False, active=True):
        self._owned()
        values = {'name': name, 'body': body, 'active': active}
        if template_id:
            template = self.env['ab_crm_saved_reply'].browse(template_id).exists()
            template.check_access('write')
            if template.branch_id != self.branch_id:
                raise AccessError(_('The selected company or branch is not allowed.'))
            template.write(values)
        else:
            self.env['ab_crm_saved_reply'].create(
                dict(values, branch_id=self.branch_id.id, company_id=self.company_id.id)
            )
        return self.workspace_templates()
