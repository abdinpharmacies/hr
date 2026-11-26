from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError


class Conversation(models.Model):
    _inherit = 'ab_crm_conversation'

    def _invalidate_workspace(self):
        companies = self.company_id
        branches = set(self.branch_id.ids)
        sessions = self.env['ab_crm_chatter_session'].sudo().search([
            ('company_id', 'in', companies.ids), ('state', '=', 'active'),
            ('expires_at', '>', fields.Datetime.now())])
        sent = self.env.cr.precommit.data.setdefault('ab_chatter_invalidations', set())
        for session in sessions:
            key = (session.user_id.id, session.company_id.id)
            if key in sent or session.company_id not in session.user_id.company_ids:
                continue
            chatter = self.env['ab_crm_chatter_api'].with_user(session.user_id).with_company(session.company_id)
            try:
                chatter._require_staff()
                if not chatter._eligible(session.profile_id):
                    continue
                allowed = chatter._directory_branches(session)
            except (AccessError, UserError):
                continue
            if not branches.intersection(allowed.ids):
                continue
            self.env['bus.bus']._sendone(session.user_id.partner_id, 'ab_chatter.invalidate', {
                'company_id': session.company_id.id})
            sent.add(key)


class Message(models.Model):
    _inherit = 'ab_crm_message'

    @api.model_create_multi
    def create(self, values_list):
        messages = super().create(values_list)
        messages.conversation_id._invalidate_workspace()
        return messages

    def write(self, values):
        result = super().write(values)
        if values:
            self.conversation_id._invalidate_workspace()
        return result


class ReadPosition(models.Model):
    _inherit = 'ab_crm_workspace_read'

    @api.model_create_multi
    def create(self, values_list):
        positions = super().create(values_list)
        positions.conversation_id._invalidate_workspace()
        return positions

    def write(self, values):
        result = super().write(values)
        self.conversation_id._invalidate_workspace()
        return result


class AlertPosition(models.Model):
    _inherit = 'ab_crm_workspace_alert'

    def write(self, values):
        result = super().write(values)
        self.conversation_id._invalidate_workspace()
        return result
