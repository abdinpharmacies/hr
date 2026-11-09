import base64
import csv
import io
import json
import re
from contextvars import ContextVar
from hashlib import sha256
from uuid import UUID, uuid5

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.addons.ab_crm_core.models.core import _INTERNAL
from odoo.addons.ab_crm_messaging.models.messaging import _MUTATION
from odoo.addons.ab_crm_messaging.models.location import validate_location

_REVIEW = ContextVar('ab_branch_review', default=False)
PROTECTED = {'revision', 'reviewed_by', 'reviewed_at', 'history'}
CONTENT = {
    'name',
    'name_ar',
    'address',
    'address_ar',
    'region',
    'latitude',
    'longitude',
    'public_phones',
    'phones_verified',
    'hotline',
    'source',
    'review_note',
}


def require_manager(env):
    user = env.user
    if (
        user.share
        or user.has_group('ab_crm_messaging.group_service')
        or not (
            user.has_group('base.group_system')
            or user.has_group('ab_crm_core.group_manager')
        )
    ):
        raise AccessError(env._('Branch configuration requires a manager.'))


class BranchLocation(models.Model):
    _name = 'ab_crm_branch_location'
    _description = 'Public Branch Location'
    _order = 'region, name, id'

    directory_key = fields.Char(required=True, index=True)
    company_id = fields.Many2one(
        'res.company',
        required=True,
        default=lambda self: self.env.company,
        ondelete='restrict',
    )
    store_id = fields.Many2one('ab_store', required=True, ondelete='restrict')
    name = fields.Char(required=True, size=256, string='English Name')
    name_ar = fields.Char(size=256, string='Arabic Name')
    address = fields.Text(required=True, string='English Address')
    address_ar = fields.Text(string='Arabic Address')
    region = fields.Char(required=True)
    latitude = fields.Float(required=True, digits=(12, 8))
    longitude = fields.Float(required=True, digits=(12, 8))
    public_phones = fields.Char(string='Verified Public Phones')
    phones_verified = fields.Boolean(string='Public Phones Verified')
    hotline = fields.Char(string='Shared Hotline')
    source = fields.Char(required=True)
    review_note = fields.Text()
    active = fields.Boolean(default=False)
    revision = fields.Integer(default=1, readonly=True, copy=False)
    reviewed_by = fields.Many2one('res.users', readonly=True, copy=False)
    reviewed_at = fields.Datetime(readonly=True, copy=False)
    history = fields.Json(readonly=True, copy=False)

    _store_unique = models.Constraint(
        'UNIQUE(company_id, store_id)',
        'Only one branch profile per company and store is allowed.',
    )
    _key_unique = models.Constraint(
        'UNIQUE(company_id, directory_key)',
        'The directory key must be unique per company.',
    )

    def _audit_values(self):
        self.ensure_one()
        return {key: self[key] for key in sorted(CONTENT | {'active'})}

    @api.model_create_multi
    def create(self, values_list):
        require_manager(self.env)
        prepared = []
        for values in values_list:
            if PROTECTED & values.keys() or values.get('active'):
                raise AccessError(_('Review the branch profile before activation.'))
            if 'latitude' not in values or 'longitude' not in values:
                raise ValidationError(_('Coordinates are required.'))
            validate_location({key: values[key] for key in ('latitude', 'longitude')})
            prepared.append(
                dict(
                    values,
                    active=False,
                    revision=1,
                    reviewed_by=False,
                    reviewed_at=False,
                    history=[],
                )
            )
        records = super().create(prepared)
        for record in records:
            super(BranchLocation, record).write(
                {
                    'history': [
                        {
                            'actor': self.env.uid,
                            'at': fields.Datetime.to_string(fields.Datetime.now()),
                            'action': 'created',
                            'new': record._audit_values(),
                        }
                    ]
                }
            )
        return records

    def write(self, values):
        require_manager(self.env)
        self.check_access('write')
        if not _REVIEW.get() and (PROTECTED & values.keys() or values.get('active')):
            raise AccessError(_('Review the branch profile before activation.'))
        if set(values) & {'directory_key', 'store_id', 'company_id'}:
            raise UserError(
                _('Branch mapping is immutable. Archive the profile instead.')
            )
        for record in self:
            record.lock_for_update()
            record.invalidate_recordset()
            validate_location(
                {key: values.get(key, record[key]) for key in ('latitude', 'longitude')}
            )
            old = record._audit_values()
            update = dict(values, revision=record.revision + 1)
            if CONTENT & values.keys():
                update.update(active=False, reviewed_by=False, reviewed_at=False)
            super(BranchLocation, record).write(update)
            super(BranchLocation, record).write(
                {
                    'history': (record.history or [])
                    + [
                        {
                            'actor': self.env.uid,
                            'at': fields.Datetime.to_string(fields.Datetime.now()),
                            'action': 'reviewed' if _REVIEW.get() else 'changed',
                            'old': old,
                            'new': record._audit_values(),
                            'revision': record.revision,
                        }
                    ]
                }
            )
        return True

    def unlink(self):
        raise UserError(_('Archive branch profiles instead of deleting them.'))

    @api.constrains(
        'latitude',
        'longitude',
        'name',
        'address',
        'name_ar',
        'address_ar',
        'company_id',
        'store_id',
        'public_phones',
        'hotline',
        'active',
        'phones_verified',
        'reviewed_by',
        'reviewed_at',
        'directory_key',
        'source',
        'region',
    )
    def _validate_profile(self):
        for record in self:
            validate_location(
                {
                    'latitude': record.latitude,
                    'longitude': record.longitude,
                    'name': record.name or '',
                    'address': record.address or '',
                }
            )
            if (
                not all(
                    (record[key] or '').strip()
                    for key in ('directory_key', 'name', 'address', 'region', 'source')
                )
                or len(record.name_ar or '') > 256
                or len(record.address_ar or '') > 1024
                or record.company_id not in self.env.companies
            ):
                raise ValidationError(_('Invalid branch profile or company.'))
            if record.public_phones and any(
                not re.fullmatch(r'\+?[0-9][0-9 ()-]{5,24}', phone.strip())
                for phone in record.public_phones.split(';')
            ):
                raise ValidationError(
                    _(
                        'Use semicolon-separated public phone numbers; keep the hotline separate.'
                    )
                )
            if record.hotline and not re.fullmatch(r'[0-9 +()-]{3,25}', record.hotline):
                raise ValidationError(_('Invalid shared hotline.'))
            if record.active and (
                not record.reviewed_by
                or not record.reviewed_at
                or not record.store_id.active
                or (record.public_phones and not record.phones_verified)
            ):
                raise ValidationError(
                    _(
                        'Review the branch profile and verify its public phones before activation.'
                    )
                )

    def action_review(self):
        require_manager(self.env)
        token = _REVIEW.set(True)
        try:
            self.write(
                {
                    'active': True,
                    'reviewed_by': self.env.uid,
                    'reviewed_at': fields.Datetime.now(),
                }
            )
        finally:
            _REVIEW.reset(token)
        return True

    def _preview(self, language):
        self.ensure_one()
        if language not in ('en_US', 'ar', 'ar_001'):
            raise ValidationError(_('Choose Arabic or English.'))
        arabic = language.startswith('ar')
        name = (self.name_ar if arabic else self.name) or self.name or self.name_ar
        address = (
            (self.address_ar if arabic else self.address)
            or self.address
            or self.address_ar
        )
        phones = self.public_phones if self.phones_verified else ''
        label_language = (
            language if self.env['res.lang']._lang_get(language) else 'en_US'
        )
        hotline_label = self.with_context(lang=label_language).env._('Shared hotline')
        return {
            'id': self.id,
            'revision': self.revision,
            'language': language,
            'name': name,
            'address': address,
            'region': self.region,
            'store_id': self.store_id.id,
            'store_code': self.store_id.code,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'public_phones': phones or '',
            'hotline': self.hotline or '',
            'fallback': bool(
                arabic
                and (
                    not self.name_ar
                    or not self.address_ar
                    or (self.hotline and label_language == 'en_US')
                )
            ),
            'details': '\n'.join(
                filter(
                    None,
                    [
                        name,
                        address,
                        phones,
                        f'{hotline_label}: {self.hotline}' if self.hotline else '',
                    ],
                )
            ),
        }


class BranchImport(models.TransientModel):
    _name = 'ab_crm_branch_location_import'
    _description = 'Review Branch CSV Import'

    file = fields.Binary(required=True, attachment=False)
    report = fields.Text(readonly=True)
    preview_digest = fields.Char(readonly=True)

    def _rows(self):
        self.ensure_one()
        require_manager(self.env)
        try:
            raw = base64.b64decode(self.file, validate=True)
            if len(raw) > 1024 * 1024:
                raise ValueError()
            reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
            required = {
                'company',
                'store_code',
                'directory_key',
                'name',
                'address',
                'region',
                'latitude',
                'longitude',
                'source',
            }
            if not required <= set(reader.fieldnames or []) or len(
                set(reader.fieldnames)
            ) != len(reader.fieldnames):
                raise ValueError()
            rows = list(reader)
            if not 1 <= len(rows) <= 500:
                raise ValueError()
        except (ValueError, UnicodeError, csv.Error):
            raise ValidationError(
                _('Invalid CSV. Use the branch import template, with at most 500 rows.')
            ) from None
        result, errors, keys, stores_seen, points = [], [], set(), set(), set()
        profiles = self.env['ab_crm_branch_location'].with_context(active_test=False)
        for number, row in enumerate(rows, 2):
            try:
                if (
                    any(not (row.get(key) or '').strip() for key in required)
                    or None in row
                ):
                    raise ValidationError(_('Missing required fields.'))
                companies = self.env['res.company'].search(
                    [
                        ('name', '=', row['company']),
                        ('id', 'in', self.env.companies.ids),
                    ]
                )
                stores = (
                    self.env['ab_store']
                    .with_context(active_test=False)
                    .search([('code', '=', row['store_code'])])
                )
                if len(companies) != 1 or len(stores) != 1:
                    raise ValidationError(
                        _('Company or store code is missing or ambiguous.')
                    )
                key, mapping = (companies.id, row['directory_key']), (
                    companies.id,
                    stores.id,
                )
                point = (companies.id, float(row['latitude']), float(row['longitude']))
                if key in keys or mapping in stores_seen or point in points:
                    raise ValidationError(
                        _('Duplicate directory key, store mapping or coordinates.')
                    )
                keys.add(key)
                stores_seen.add(mapping)
                points.add(point)
                existing = profiles.search(
                    [
                        ('company_id', '=', companies.id),
                        '|',
                        ('directory_key', '=', row['directory_key']),
                        ('store_id', '=', stores.id),
                    ]
                )
                if existing and (
                    len(existing) != 1
                    or existing.directory_key != row['directory_key']
                    or existing.store_id != stores
                ):
                    raise ValidationError(_('Conflicting existing branch mapping.'))
                if profiles.search_count(
                    [
                        ('company_id', '=', companies.id),
                        ('latitude', '=', point[1]),
                        ('longitude', '=', point[2]),
                        ('id', 'not in', existing.ids),
                    ]
                ):
                    raise ValidationError(
                        _('Duplicate directory key, store mapping or coordinates.')
                    )
                values = {
                    key: row.get(key, '').strip()
                    for key in CONTENT - {'latitude', 'longitude', 'phones_verified'}
                }
                values.update(
                    latitude=point[1], longitude=point[2], phones_verified=False
                )
                draft = profiles.new(
                    dict(
                        values,
                        company_id=companies.id,
                        store_id=stores.id,
                        directory_key=row['directory_key'],
                        active=False,
                    )
                )
                draft._validate_profile()
                result.append(
                    {
                        'id': existing.id,
                        'revision': existing.revision if existing else 0,
                        'values': dict(
                            values,
                            company_id=companies.id,
                            store_id=stores.id,
                            directory_key=row['directory_key'],
                        ),
                    }
                )
            except (ValidationError, ValueError) as error:
                errors.append(_('Row %(row)s: %(error)s', row=number, error=str(error)))
        return result, errors

    def action_preview(self):
        rows, errors = self._rows()
        self.write(
            {
                'report': (
                    '\n'.join(errors)
                    if errors
                    else _(
                        'Validated %(count)s rows. Import creates inactive profiles requiring review.',
                        count=len(rows),
                    )
                ),
                'preview_digest': (
                    False
                    if errors
                    else sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()
                ),
            }
        )
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_apply(self):
        rows, errors = self._rows()
        digest = sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()
        if errors or not self.preview_digest or digest != self.preview_digest:
            raise ValidationError(_('Validate the CSV again before importing.'))
        with self.env.cr.savepoint():
            for row in rows:
                values = row['values']
                if row['id']:
                    self.env['ab_crm_branch_location'].browse(row['id']).write(
                        {key: value for key, value in values.items() if key in CONTENT}
                    )
                else:
                    self.env['ab_crm_branch_location'].create(values)
        self.preview_digest = False
        return {'type': 'ir.actions.act_window_close'}


class Account(models.Model):
    _inherit = 'ab_crm_messaging_account'

    branch_location_enabled = fields.Boolean(
        default=False, string='Telegram Branch Locations Enabled'
    )

    def write(self, values):
        if 'branch_location_enabled' in values:
            require_manager(self.env)
        return super().write(values)


class Message(models.Model):
    _inherit = 'ab_crm_message'

    branch_share_snapshot = fields.Json(readonly=True, copy=False)
    branch_share_token = fields.Char(readonly=True, copy=False, index=True)
    _share_unique = models.Constraint(
        'UNIQUE(conversation_id, branch_share_token)',
        'This branch share was already queued.',
    )

    @api.model_create_multi
    def create(self, values_list):
        if not _MUTATION.get() and (
            any(
                {'branch_share_snapshot', 'branch_share_token'} & values.keys()
                for values in values_list
            )
            or any(
                'default_' + key in self.env.context
                for key in ('branch_share_snapshot', 'branch_share_token')
            )
        ):
            raise AccessError(_('Branch sharing evidence is immutable.'))
        return super().create(values_list)

    def write(self, values):
        if {'branch_share_snapshot', 'branch_share_token'} & values.keys() or (
            any(self.mapped('branch_share_snapshot'))
            and set(values)
            & {
                'body',
                'conversation_id',
                'branch_id',
                'company_id',
                'direction',
                'reply_reference',
                'reaction',
                'media_ids',
            }
        ):
            raise AccessError(_('Branch sharing evidence is immutable.'))
        return super().write(values)


class Conversation(models.Model):
    _inherit = 'ab_crm_conversation'

    def _branch_owner(self, session):
        if (
            not self.env.user.has_group('base.group_system')
            and not self.env.user.has_group('ab_crm_core.group_manager')
            and (
                (self.assigned_id and self.assigned_id != self.env.user)
                or (
                    self.assigned_employee_id
                    and self.assigned_employee_id != session.employee_id
                )
            )
        ):
            raise AccessError(_('This conversation is already assigned.'))

    def _branch_profiles(self):
        session, _stores = self._owned()
        self._branch_owner(session)
        code, reason = self._reply_eligibility()
        if code:
            raise UserError(reason)
        if self.channel_id.provider != 'telegram':
            raise AccessError(_('Branch sharing is available only in Telegram.'))
        return (
            self.env['ab_crm_branch_location']
            .sudo()
            .search(
                [
                    ('company_id', '=', session.company_id.id),
                    ('store_id.active', '=', True),
                    ('active', '=', True),
                    ('reviewed_by', '!=', False),
                    ('reviewed_at', '!=', False),
                ]
            )
        )

    def workspace_branch_directory(self, query='', language='en_US'):
        if not isinstance(query, str) or len(query) > 200:
            raise ValidationError(_('Invalid branch search.'))
        profiles = self._branch_profiles()
        needle = query.casefold().strip()
        profiles = profiles.filtered(
            lambda p: not needle
            or needle
            in ' '.join(
                filter(
                    None,
                    [
                        p.name,
                        p.name_ar,
                        p.address,
                        p.address_ar,
                        p.region,
                        p.store_id.code,
                    ],
                )
            ).casefold()
        )
        return [profile._preview(language) for profile in profiles[:100]]

    def workspace_branch_preview(self, profile_id, language='en_US'):
        profiles = self._branch_profiles().filtered(lambda p: p.id == profile_id)
        if len(profiles) != 1:
            raise AccessError(_('Select an authorized reviewed branch.'))
        return profiles._preview(language)

    def action_send_branch_location(self, profile_id, revision, language, token):
        return self._send_branch(profile_id, revision, language, token, 'location')

    def action_send_branch_details(self, profile_id, revision, language, token):
        return self._send_branch(profile_id, revision, language, token, 'details')

    def action_share_branch(self, profile_id, revision, language, token, include_details=False):
        if type(include_details) is not bool:
            raise ValidationError(_('Invalid branch preview.'))
        with self.env.cr.savepoint():
            location_id = self._send_branch(profile_id, revision, language, token, 'location', include_details)
            details_id = self._send_branch(
                profile_id, revision, language, str(uuid5(UUID(token), 'details')), 'details'
            ) if include_details else False
        return {'location_id': location_id, 'details_id': details_id}

    def _send_branch(self, profile_id, revision, language, token, kind, include_details=None):
        session, stores = self._owned()
        self._branch_owner(session)
        if (
            type(profile_id) is not int
            or type(revision) is not int
            or language not in ('en_US', 'ar', 'ar_001')
        ):
            raise ValidationError(_('Invalid branch preview.'))
        try:
            if not isinstance(token, str) or str(UUID(token)) != token:
                raise ValueError()
        except (ValueError, TypeError, AttributeError):
            raise ValidationError(_('Invalid branch send token.')) from None
        request = {
            'profile_id': profile_id,
            'revision': revision,
            'language': language,
            'kind': kind,
        }
        if include_details is not None:
            request['include_details'] = include_details
        existing = self.env['ab_crm_message'].search(
            [('conversation_id', '=', self.id), ('branch_share_token', '=', token)],
            limit=1,
        )
        if existing:
            if (
                existing.branch_share_snapshot['request'] != request
                or existing.branch_share_snapshot['employee_id']
                != session.employee_id.id
                or existing.branch_share_snapshot['actor'] != self.env.uid
            ):
                raise ValidationError(
                    _('A send token cannot be reused for different content.')
                )
            return existing.id
        profiles = self._branch_profiles().filtered(lambda p: p.id == profile_id)
        if len(profiles) != 1:
            raise AccessError(_('Select an authorized reviewed branch.'))
        profiles.lock_for_update()
        profiles.invalidate_recordset()
        if (
            profiles.revision != revision
            or not profiles.active
            or not profiles.reviewed_at
        ):
            raise ValidationError(_('This branch preview is stale. Preview it again.'))
        if kind == 'location' and not self.messaging_account_id.branch_location_enabled:
            raise UserError(_('Telegram branch location sending is not enabled.'))
        preview = profiles._preview(language)
        at = fields.Datetime.to_string(fields.Datetime.now())
        location = {
            key: preview[key] for key in ('latitude', 'longitude', 'name', 'address')
        }
        snapshot = dict(
            preview,
            request=request,
            actor=self.env.uid,
            employee_id=session.employee_id.id,
            at=at,
            directory_key=profiles.directory_key,
            source=profiles.source,
            reviewed_by=profiles.reviewed_by.id,
            reviewed_at=fields.Datetime.to_string(profiles.reviewed_at),
        )
        internal, mutation = _INTERNAL.set(True), _MUTATION.set(True)
        try:
            message = self.env['ab_crm_message'].create(
                {
                    'conversation_id': self.id,
                    'branch_id': self.branch_id.id,
                    'company_id': self.company_id.id,
                    'direction': 'out',
                    'body': (
                        preview['details']
                        if kind == 'details'
                        else '\n'.join(
                            [
                                preview['name'],
                                preview['address'],
                                f"{preview['latitude']}, {preview['longitude']}",
                            ]
                        )
                    ),
                    'location_snapshot': (
                        dict(location, timestamp=at, is_live_snapshot=False)
                        if kind == 'location'
                        else False
                    ),
                    'branch_share_token': token,
                    'branch_share_snapshot': snapshot,
                }
            )
        finally:
            _INTERNAL.reset(internal)
            _MUTATION.reset(mutation)
        message.action_approve()
        self._log_workspace_action('branch_' + kind, message_id=message.id)
        return message.id


class MessagingAPI(models.AbstractModel):
    _inherit = 'ab_crm_messaging_api'

    @api.model
    def authorize_send(self, account_code, provider_account, token, attempt, receipt):
        allowed = super().authorize_send(
            account_code, provider_account, token, attempt, receipt
        )
        if not allowed:
            return allowed
        account = self._account(account_code, provider_account)
        operation = self._operation(account, token, attempt)
        return bool(
            not (operation.content or {}).get('location')
            or (account.provider == 'telegram' and account.branch_location_enabled)
        )
