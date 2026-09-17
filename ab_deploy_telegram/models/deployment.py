import base64
import logging
import re
import uuid

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError, UserError
from odoo.tools.translate import LazyTranslate
from odoo.addons.ab_telegram_bot.models.bot import chat_id

_logger = logging.getLogger(__name__)
_lt = LazyTranslate(__name__)


class DeploymentTelegram(models.Model):
    _inherit = 'ab_deploy_request'

    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    telegram_bot_id = fields.Many2one('ab_telegram_bot', string='Telegram Bot Override',
                                      domain="[('company_id', '=', company_id), ('active', '=', True)]")
    telegram_group_id = fields.Many2one('ab_telegram_bot_group', string='Telegram Group Override',
                                        domain="[('company_id', '=', company_id), ('active', '=', True)]")
    telegram_chat_id = fields.Char(string='Telegram Chat ID Override')
    telegram_topic_id = fields.Integer(string='Telegram Topic ID Override', help='Zero uses the subscription topic.')
    telegram_snapshot = fields.Json(readonly=True, copy=False)
    telegram_note = fields.Text(string='Telegram Notification Notes', readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        if any({'telegram_snapshot', 'telegram_note'} & set(vals) for vals in vals_list):
            raise AccessError(_('Telegram notification history cannot be changed manually.'))
        return super().create(vals_list)

    def write(self, vals):
        if {'telegram_snapshot', 'telegram_note'} & set(vals):
            raise AccessError(_('Telegram notification history cannot be changed manually.'))
        return super().write(vals)

    @api.constrains('company_id', 'telegram_bot_id', 'telegram_group_id', 'telegram_topic_id', 'telegram_chat_id')
    def _check_telegram_settings(self):
        for request in self:
            if request.company_id not in self.env.companies:
                raise ValidationError(_('Choose an allowed company.'))
            if request.telegram_bot_id and request.telegram_bot_id.company_id != request.company_id:
                raise ValidationError(_('The Telegram bot must belong to the deployment company.'))
            if request.telegram_group_id and request.telegram_group_id.company_id != request.company_id:
                raise ValidationError(_('The Telegram group must belong to the deployment company.'))
            if request.telegram_chat_id:
                chat_id(request.telegram_chat_id)
            if request.telegram_topic_id < 0:
                raise ValidationError(_('Topic ID cannot be negative.'))

    def _telegram_route(self):
        self.ensure_one()
        subscription = self.env['ab_telegram_bot_module_subscription'].search(
            fields.Domain('module_id.name', '=', 'ab_deploy') & fields.Domain('company_id', '=', self.company_id.id)
            & fields.Domain('enabled', '=', True), limit=1)
        if not subscription:
            raise ValidationError(_('Configure an enabled Telegram subscription for ab_deploy in this company first.'))
        bot = self.telegram_bot_id or subscription.bot_id
        group = self.telegram_group_id
        destination = self.telegram_chat_id or group.chat_id or subscription._destination()
        bot.check_access('read')
        if not bot.active or bot.company_id != self.company_id or not bot.sudo().token:
            raise ValidationError(_('Configure an active Telegram bot with a token in the deployment company.'))
        effective_group = group or (subscription.default_group_id if not self.telegram_chat_id else self.env['ab_telegram_bot_group'])
        if effective_group and (not effective_group.active or bot not in effective_group.bot_ids):
            raise ValidationError(_('The notification bot must be associated with the selected group.'))
        return {'bot_id': bot.id, 'chat_id': chat_id(destination),
                'topic_id': self.telegram_topic_id or subscription.topic_id or None,
                'language': subscription.language, 'company_id': self.company_id.id}

    def _telegram_prepare_destination(self):
        self.ensure_one()
        if self.telegram_snapshot:
            return True
        try:
            with self.env.cr.savepoint():
                route = self._telegram_route()
                self._transition({'telegram_snapshot': route, 'telegram_note': False})
            return True
        except ValidationError as exc:
            self._transition({'telegram_note': str(exc)})
        except Exception:
            _logger.warning('Telegram destination could not be resolved for deployment %s.', self.id)
            self._transition({'telegram_note': _('The Telegram destination could not be configured. Check the enabled ab_deploy subscription and bot access.')})
        return False

    def action_submit(self):
        result = super().action_submit()
        for request in self:
            request._telegram_prepare_destination()
        return result

    def action_send_deployment_report(self):
        self.ensure_one()
        self._require_role('executor')
        self._lock()
        with self.env.cr.savepoint():
            if not self._telegram_prepare_destination():
                raise UserError(self.telegram_note)
            self._telegram_enqueue_event('manual', self.run_ids.sorted('id', reverse=True)[:1])
            self._transition({'telegram_note': False})
        return {'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'title': _('Deployment Report'),
                           'message': _('Deployment report queued for Telegram.'),
                           'type': 'success', 'sticky': False}}

    def _telegram_notify(self, event, run=None):
        self.ensure_one()
        if event != 'finished' or not self._telegram_prepare_destination():
            return
        # Never let delivery construction failure roll back approval or execution progress.
        try:
            with self.env.cr.savepoint():
                self._telegram_enqueue_event(event, run)
                self._transition({'telegram_note': False})
        except Exception:
            _logger.warning('Telegram notification could not be queued for deployment %s (event %s).', self.id, event)
            self._transition({'telegram_note': _('A Telegram notification could not be queued. Check the notification configuration and message history.')})

    def _telegram_report_content(self, run):
        """Snapshot every target once, including executions from earlier batches."""
        self.ensure_one()
        rows = [(target.server_id.serial or '', target.server_id.name or '',
                 target.server_id.area or '', target.deployment_status)
                for target in self.target_ids]
        totals = {status: sum(row[3] == status for row in rows)
                  for status in ('succeeded', 'failed', 'cancelled', 'delayed', 'queued', 'running', 'unknown')}
        lines = [self.env._('Deployment request name: %s', self.name),
                 self.env._('Title: %s', self.title or ''), self.env._('Description:'),
                 self.description or self.env._('Not provided'), '',
                 self.env._('Executor: %s', run.requested_by_id.name if run else self.env._('Not started'))]
        for label, count in [(self.env._('Succeeded'), totals['succeeded']),
                             (self.env._('Failed'), totals['failed']),
                             (self.env._('Cancelled'), totals['cancelled']),
                             (self.env._('Unfinished'), sum(totals[key] for key in ('queued', 'running', 'unknown'))),
                             (self.env._('Still delayed'), totals['delayed'])]:
            lines.append('%s (%s)' % (label, count))
        # Explicit Arabic file labels use the shipped catalogs even if Arabic is
        # not activated as an Odoo UI language in this database.
        labels = {'succeeded': _lt('Succeeded'), 'failed': _lt('Failed'),
                  'delayed': _lt('Delayed'), 'cancelled': _lt('Cancelled'),
                  'queued': _lt('Queued'), 'running': _lt('Running'), 'unknown': _lt('Unknown')}
        headers = [_lt('Serial'), _lt('Server'), _lt('Area'), _lt('Status')]
        def cell(value):
            return ' '.join(str(value).splitlines()).replace('\\', '\\\\').replace('|', '\\|')
        table = ['| ' + ' | '.join(h._translate('ar_001') for h in headers) + ' |',
                 '| ---: | ---: | ---: | ---: |']
        ranks = {'succeeded': 0, 'failed': 1, 'delayed': 2, 'cancelled': 3,
                 'queued': 4, 'running': 4, 'unknown': 4}
        def sort_key(row):
            serial = row[0]
            return (ranks[row[3]], (0, int(serial)) if serial.isdecimal() else (1, serial.casefold()), row[1].casefold())
        for serial, name, area, status in sorted(rows, key=sort_key):
            table.append('| ' + ' | '.join(cell(value) for value in
                         (serial, name, area, labels[status]._translate('ar_001'))) + ' |')
        return '\n'.join(lines), '\n'.join(table) + '\n'

    def _telegram_enqueue_event(self, event, run):
        route = self.telegram_snapshot
        request = self.with_context(lang=route.get('language', 'en_US'))
        bot = self.env['ab_telegram_bot'].sudo().browse(route['bot_id']).exists()
        if not bot or not bot.active or bot.company_id.id != route['company_id'] or bot.company_id != self.company_id:
            raise ValidationError(_('The frozen Telegram destination is no longer available.'))
        event_key = 'run:%s:finished' % run.id if event == 'finished' else 'manual:%s' % uuid.uuid4().hex
        key = 'deployment:%s:%s' % (self.id, event_key)
        messages = self.env['ab_telegram_bot_message'].sudo()
        # A completed report is immutable; repeated completion callbacks do not
        # regenerate it from newer statuses or create extra text chunks.
        if messages.search_count(fields.Domain('dedupe_key', '=', key + ':document')
                                 & fields.Domain('company_id', '=', self.company_id.id)):
            return
        summary, table = request._telegram_report_content(run)
        options = {'message_thread_id': route.get('topic_id')} if route.get('topic_id') else {}
        common = {'order_key': 'deployment:%s' % self.id, 'source_model': self._name, 'source_id': self.id}
        messages._enqueue_text(bot, route['chat_id'], summary, options=options,
                               dedupe_key=key + ':summary', **common)
        filename = re.sub(r'[^A-Za-z0-9_-]', '_', self.name) + '-servers.md'
        messages._enqueue(bot, 'sendDocument', dict(options, chat_id=route['chat_id'], document='attach://document'),
                          uploads={'document': {'filename': filename,
                                   'data': base64.b64encode(table.encode('utf-8')).decode('ascii')}},
                          dedupe_key=key + ':document', **common)


class DeploymentRunTelegram(models.Model):
    _inherit = 'ab_deploy_run'

    def _update(self, vals):
        result = super()._update(vals)
        if vals.get('finished_at'):
            for run in self:
                run.request_id._telegram_notify('finished', run)
        return result
