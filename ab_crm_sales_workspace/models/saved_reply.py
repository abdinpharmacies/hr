from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


def template_language(code):
    return (code or 'en_US').replace('-', '_').split('_', 1)[0].lower()


class SavedReply(models.Model):
    _name = 'ab_crm_saved_reply'
    _inherit = 'ab_crm_scoped'
    _description = 'Channel Saved Reply'

    name = fields.Char(required=True)
    body = fields.Text(required=True)
    active = fields.Boolean(default=True)
    language_code = fields.Char(string='Language', copy=True)

    def _template_language(self):
        self.ensure_one()
        prefix, separator, remainder = (self.name or '').partition('|')
        legacy_language = prefix.strip().lower() if separator and prefix.strip().lower() in ('en', 'ar') else False
        return template_language(self.language_code or legacy_language)

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
        prepared = []
        for values in values_list:
            values = dict(values)
            prefix, separator, remainder = (values.get('name') or '').partition('|')
            legacy_language = prefix.strip().lower() if separator and prefix.strip().lower() in ('en', 'ar') else False
            values['language_code'] = template_language(values.get('language_code') or legacy_language or self.env.user.lang)
            prepared.append(values)
        return super().create(prepared)

    def write(self, values):
        self._maintain()
        if 'language_code' in values:
            values = dict(values, language_code=template_language(values['language_code']) if values['language_code'] else False)
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
        language = template_language(self.env.user.lang)
        templates = self.env['ab_crm_saved_reply'].search([('branch_id', '=', self.branch_id.id)])
        return {
            'items': templates.filtered(lambda record: record._template_language() == language).read(['name', 'body']),
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
            template.write(dict(values, language_code=template._template_language()))
        else:
            template = self.env['ab_crm_saved_reply'].create(
                dict(values, branch_id=self.branch_id.id, company_id=self.company_id.id)
            )
        result = self.workspace_templates()
        return dict(result, selected_id=template.id if active and template.id in [row['id'] for row in result['items']] else False)
