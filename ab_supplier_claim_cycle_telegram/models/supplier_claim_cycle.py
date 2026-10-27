import logging
from html import escape
from urllib.error import URLError

from odoo import api, fields, models
from odoo.addons.queue_job.exception import RetryableJobError

_logger = logging.getLogger(__name__)

CHANNEL = 'root.supplier_claim_cycle_telegram'
PARAMETER = 'supplier_claim_cycle.telegram_notifications_enabled'
STAGE_ROLES = {
    'inventory': 'inventory',
    'purchasing': 'purchasing',
    'supplier_accounts': 'supplier_accounts',
    'bank_accounts': 'bank_accounts',
    'returned_secretarial': 'user',
    'ready_to_close': 'user',
}


class SupplierClaimCycle(models.Model):
    _inherit = 'ab_supplier_claim_cycle'

    @api.model
    def _cycle_telegram_enabled(self):
        value = self.env['ir.config_parameter'].sudo().get_param(PARAMETER, 'True')
        return str(value).strip().lower() not in ('false', '0', 'no', 'off', '')

    def _cycle_telegram_chat_ids(self):
        self.ensure_one()
        if self.state == 'closed':
            users = self.user_id
        else:
            role = STAGE_ROLES.get(self.state)
            if not role:
                return []
            group = self.env.ref('ab_supplier_claim_cycle.supplier_claim_group_' + role)
            users = self.env['res.users'].sudo().search(
                fields.Domain('group_ids', 'in', group.ids)
                & fields.Domain('active', '=', True)
                & fields.Domain('share', '=', False)
            )
        employees = self.env['ab_hr_employee'].sudo().search(
            fields.Domain('user_id', 'in', users.filtered('active').ids)
            & fields.Domain('costcenter_id', '!=', False)
        )
        accounts = self.env['ab_partner_bot'].sudo()
        chat_ids = set()
        for costcenter in employees.mapped('costcenter_id'):
            account = accounts._get_latest_active_account_for_costcenter(costcenter)
            chat_id = str(account.chat_id or '').strip() if account else ''
            if chat_id:
                chat_ids.add(chat_id)
        return sorted(chat_ids)

    def _cycle_telegram_message(self):
        self.ensure_one()
        claim = self.sudo()
        stage = dict(claim._fields['state']._description_selection(claim.env))[claim.state]
        base_url = claim.get_base_url().rstrip('/')
        url = f'{base_url}/odoo/ab_supplier_claim_cycle/{claim.id}'
        lines = [
            '<b>Supplier Claim</b>',
            'Claim ID: ' + escape(claim.claim_reference or str(claim.id)),
            'Supplier: ' + escape(claim.supplier_id.display_name),
            'Amount: ' + escape(claim.amount_of_check or ''),
            'Current stage: ' + escape(stage),
        ]
        if claim.state == 'returned_secretarial' and claim.rejection_reason:
            lines.append('Rejection reason: ' + escape(claim.rejection_reason[:2000]))
        lines.append(f'<a href="{escape(url, quote=True)}">Open claim</a>')
        return '\n'.join(lines)

    def _queue_cycle_telegram_notifications(self, previous_states):
        if not self._cycle_telegram_enabled():
            return
        for claim in self:
            if previous_states[claim.id] == claim.state:
                continue
            chat_ids = claim._cycle_telegram_chat_ids()
            if not chat_ids:
                continue
            message = claim._cycle_telegram_message()
            for chat_id in chat_ids:
                claim.sudo().with_delay(
                    channel=CHANNEL,
                    max_retries=0,
                    description=f'Supplier claim {claim.id}: {claim.state}',
                )._deliver_cycle_telegram_notification(chat_id, message)

    def action_submit(self):
        result = super().action_submit()
        self._queue_cycle_telegram_notifications(dict.fromkeys(self.ids, 'returned_secretarial'))
        return result

    def action_decide(self, department, decision, reason=None, followup_date=None):
        result = super().action_decide(
            department, decision, reason=reason, followup_date=followup_date)
        self._queue_cycle_telegram_notifications(dict.fromkeys(self.ids, department))
        return result

    def action_close(self):
        result = super().action_close()
        self._queue_cycle_telegram_notifications(dict.fromkeys(self.ids, 'ready_to_close'))
        return result

    def _deliver_cycle_telegram_notification(self, chat_id, message):
        self.ensure_one()
        if not self.exists() or not self._cycle_telegram_enabled():
            return
        try:
            result = self.env['ab_telegram_bot'].sudo().send_message(
                chat_id, message, disable_web_page_preview=True)
        except (OSError, URLError) as exc:
            _logger.warning('Supplier claim Telegram delivery failed; scheduling retry.')
            raise RetryableJobError('Telegram communication failed.') from exc
        if not isinstance(result, dict) or not result.get('sent'):
            raise RetryableJobError('Telegram did not confirm message delivery.')
