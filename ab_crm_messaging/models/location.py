import math
from contextvars import ContextVar

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError

from .messaging import _EDIT, _MUTATION

_RECEIPT = ContextVar("ab_location_receipt", default=False)


def validate_location(value):
    if not isinstance(value, dict) or value.keys() - {
        'latitude', 'longitude', 'name', 'address', 'is_live_snapshot'
    }:
        raise ValidationError(_('Invalid location.'))
    for key, bound in (('latitude', 90), ('longitude', 180)):
        number = value.get(key)
        if type(number) not in (int, float) or abs(number) > bound or not math.isfinite(number):
            raise ValidationError(_('Invalid location.'))
    for key, limit in (('name', 256), ('address', 1024)):
        if not isinstance(value.get(key, ''), str) or len(value.get(key, '')) > limit:
            raise ValidationError(_('Invalid location.'))
    if type(value.get('is_live_snapshot', False)) is not bool:
        raise ValidationError(_('Invalid location.'))
    return dict(value, name=value.get('name', ''), address=value.get('address', ''),
                is_live_snapshot=value.get('is_live_snapshot', False))


class Message(models.Model):
    _inherit = 'ab_crm_message'

    location_snapshot = fields.Json(readonly=True, copy=False)

    @api.model_create_multi
    def create(self, values_list):
        if not _MUTATION.get() and (
            any('location_snapshot' in values for values in values_list)
            or 'default_location_snapshot' in self.env.context
        ):
            raise AccessError(_('Location evidence is managed by ingestion.'))
        return super().create(values_list)

    def write(self, values):
        if 'location_snapshot' in values or (
            not _EDIT.get() and any(self.mapped('location_snapshot')) and set(values) & {
                'body', 'direction', 'conversation_id', 'branch_id', 'company_id',
                'provider_event', 'token',
            }
        ):
            raise AccessError(_('Location evidence is immutable.'))
        if 'provider_reference' in values and any(self.mapped('location_snapshot')):
            if not _RECEIPT.get() or any(
                record.direction != 'out' or (
                    record.provider_reference and record.provider_reference != values['provider_reference']
                ) for record in self
            ):
                raise AccessError(_('Location evidence is immutable.'))
        return super().write(values)

    def _outgoing_extra(self):
        result = super()._outgoing_extra()
        if self.location_snapshot:
            if self.direction != 'out' or self.conversation_id.channel_id.provider != 'telegram' or any(
                result.get(key) for key in ('media', 'reaction', 'contact_button')
            ):
                raise ValidationError(_('Invalid location.'))
            result['location'] = {
                key: self.location_snapshot[key]
                for key in ('latitude', 'longitude', 'name', 'address')
            }
            validate_location(result['location'])
            if not result['location']['name'] or not result['location']['address']:
                raise ValidationError(_('Invalid location.'))
        return result

    def _location_data(self, original=False):
        self.ensure_one()
        self.check_access('read')
        location = self.location_snapshot
        if not original and self.provider_edit_content:
            location = self.provider_edit_content.get('location')
        if not location:
            return False
        return dict(location, message_id=self.id,
                    conversation_id=self.conversation_id.id,
                    provider=self.conversation_id.channel_id.provider,
                    provider_reference=self.provider_reference,
                    provider_event=self.provider_event)


class Operation(models.Model):
    _inherit = 'ab_crm_messaging_operation'

    @api.model_create_multi
    def create(self, values_list):
        for values in values_list:
            content = values.get('content') or {}
            if 'location' in content:
                location = validate_location(content['location'])
                account = self.env['ab_crm_messaging_account'].browse(values.get('account_id'))
                if account.provider != 'telegram' or not location['name'] or not location['address'] or any(
                    content.get(key) for key in ('media', 'reaction', 'template', 'contact_button')
                ):
                    raise ValidationError(_('Invalid location.'))
        return super().create(values_list)

    def write(self, values):
        if set(values) & {'content', 'body', 'destination', 'message_id', 'account_id'}:
            raise AccessError(_('Location evidence is immutable.'))
        return super().write(values)


class MessagingAPI(models.AbstractModel):
    _inherit = 'ab_crm_messaging_api'

    def _apply_status(self, account, operation, status, reference, error):
        token = _RECEIPT.set(True)
        try:
            return super()._apply_status(account, operation, status, reference, error)
        finally:
            _RECEIPT.reset(token)
