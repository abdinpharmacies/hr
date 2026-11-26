from .timing import message_correlation, trace
from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError


class Conversation(models.Model):
    _inherit = 'ab_crm_conversation'

    def _invalidate_workspace(self, category='messages', actor=None, branches=None):
        pending = self.env.cr.precommit.data.get('ab_chatter_invalidations')
        if pending is None:
            pending = self.env.cr.precommit.data['ab_chatter_invalidations'] = {}
            self.env.cr.precommit.add(self._send_workspace_invalidations)
        if branches:
            self.env.cr.precommit.data.setdefault('ab_chatter_directory_branches', set()).update(branches.ids)
        actors = self.env.cr.precommit.data.setdefault('ab_chatter_invalidation_actors', {})
        for conversation in self:
            if actor is None:
                actors[conversation.id] = None
            elif conversation.id not in actors:
                actors[conversation.id] = {actor}
            elif actors[conversation.id] is not None:
                actors[conversation.id].add(actor)
            pending.setdefault(conversation.id, set()).add(category)

    def _send_workspace_invalidations(self):
        pending = self.env.cr.precommit.data.pop('ab_chatter_invalidations', {})
        actors = self.env.cr.precommit.data.pop('ab_chatter_invalidation_actors', {})
        trace_ids = self.env.cr.precommit.data.pop('ab_chatter_trace_ids', {})
        conversations = self.sudo().browse(list(pending)).exists()
        directory_branches = self.env['ab_crm_branch'].sudo().browse(
            list(self.env.cr.precommit.data.pop('ab_chatter_directory_branches', set()))).exists()
        sessions = self.env['ab_crm_chatter_session'].sudo().search([
            ('company_id', 'in', (conversations.company_id | directory_branches.company_id).ids), ('state', '=', 'active'),
            ('expires_at', '>', fields.Datetime.now())])
        sent = set()
        for session in sessions:
            recipient = (session.user_id.id, session.employee_id.id, session.company_id.id)
            if recipient in sent:
                continue
            if session.company_id not in session.user_id.company_ids:
                continue
            candidates = conversations.filtered(lambda row: row.company_id == session.company_id
                and (actors.get(row.id) is None or recipient[:2] in actors[row.id]))
            directory_candidates = directory_branches.filtered(lambda branch: branch.company_id == session.company_id)
            if not candidates and not directory_candidates:
                continue
            chatter = self.env['ab_crm_chatter_api'].with_user(session.user_id).with_context(
                allowed_company_ids=[session.company_id.id]).with_company(session.company_id)
            try:
                chatter._require_staff()
                if not chatter._eligible(session.profile_id):
                    continue
                allowed = chatter._directory_branches(session)
                authorized = candidates.filtered(lambda row: row.branch_id in allowed).with_user(
                    session.user_id).with_context(allowed_company_ids=[session.company_id.id]).with_company(session.company_id)
                authorized = authorized.filtered(lambda row: row.has_access('read'))
            except (AccessError, UserError):
                continue
            directory_changed = bool(directory_candidates & allowed)
            if not authorized and not directory_changed:
                continue
            notification_ids = []
            for conversation in authorized:
                canonical = chatter._notification_conversation(conversation)
                if (canonical.company_id == session.company_id and canonical.branch_id in allowed
                        and canonical.has_access('read') and canonical.id not in notification_ids):
                    notification_ids.append(canonical.id)
            if not notification_ids and not directory_changed:
                continue
            sent.add(recipient)
            categories = set().union(*(pending[cid] for cid in authorized.ids))
            if directory_changed:
                categories.add('contacts')
            categories = sorted(categories)
            self.env['bus.bus']._sendone(session.user_id.partner_id, 'ab_chatter.invalidate', {
                'company_id': session.company_id.id, 'employee_id': session.employee_id.id,
                'conversation_ids': notification_ids[:50], 'categories': categories,
                'overflow': len(notification_ids) > 50,
                'correlation_ids': list(dict.fromkeys(cid for record_id in authorized.ids
                    for cid in trace_ids.get(record_id, [])))[:50]})


class Message(models.Model):
    _inherit = 'ab_crm_message'

    @api.model_create_multi
    def create(self, values_list):
        messages = super().create(values_list)
        messages._trace_workspace()
        messages.conversation_id._invalidate_workspace()
        return messages

    def _trace_workspace(self):
        correlations = tuple(message_correlation(message) for message in self)
        trace_ids = self.env.cr.precommit.data.setdefault('ab_chatter_trace_ids', {})
        for message, correlation in zip(self, correlations):
            ids = trace_ids.setdefault(message.conversation_id.id, [])
            if len(ids) < 50:
                ids.append(correlation)
        trace('odoo_write', correlations)
        self.env.cr.postcommit.add(lambda: trace('odoo_commit', correlations))

    def write(self, values):
        result = super().write(values)
        if values:
            self._trace_workspace()
            self.conversation_id._invalidate_workspace()
        return result


class ReadPosition(models.Model):
    _inherit = 'ab_crm_workspace_read'

    @api.model_create_multi
    def create(self, values_list):
        positions = super().create(values_list)
        for position in positions:
            position.conversation_id._invalidate_workspace('unread', (position.user_id.id, position.employee_id.id))
        return positions

    def write(self, values):
        result = super().write(values)
        for position in self:
            position.conversation_id._invalidate_workspace('unread', (position.user_id.id, position.employee_id.id))
        return result


class AlertPosition(models.Model):
    _inherit = 'ab_crm_workspace_alert'

    def write(self, values):
        result = super().write(values)
        for position in self:
            position.conversation_id._invalidate_workspace('unread', (position.user_id.id, position.employee_id.id))
        return result


class Operation(models.Model):
    _inherit = 'ab_crm_messaging_operation'

    def write(self, values):
        result = super().write(values)
        if {'state', 'attempt', 'error_code', 'retryable', 'provider_reference'} & values.keys():
            self.message_id._trace_workspace()
            self.message_id.conversation_id._invalidate_workspace('status')
        return result


class Customer(models.Model):
    _inherit = 'ab_crm_customer'

    @api.model_create_multi
    def create(self, values_list):
        customers = super().create(values_list)
        self.env['ab_crm_conversation']._invalidate_workspace('contacts', branches=customers.branch_id)
        return customers

    def write(self, values):
        result = super().write(values)
        if {'name', 'chatter_name', 'phone', 'chatter_phone', 'address', 'chatter_address', 'active'} & values.keys():
            self.env['ab_crm_conversation']._invalidate_workspace('contacts', branches=self.branch_id)
        return result
