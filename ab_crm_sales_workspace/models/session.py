import secrets
from datetime import timedelta
from hashlib import sha256

from psycopg2.errors import SerializationFailure

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError
from odoo.tools import SQL


class User(models.Model):
    _inherit = 'res.users'

    chatter_failed_attempts = fields.Integer(readonly=True, groups='base.group_system')
    chatter_blocked_until = fields.Datetime(readonly=True, groups='base.group_system')


class Session(models.Model):
    _name = 'ab_crm_chatter_session'
    _description = 'Sales Chatter Employee Session'

    token_hash = fields.Char(
        required=True, readonly=True, groups='base.group_system', index=True
    )
    user_id = fields.Many2one(
        'res.users', required=True, readonly=True, ondelete='restrict'
    )
    employee_id = fields.Many2one(
        'ab_hr_employee', required=True, readonly=True, ondelete='restrict'
    )
    profile_id = fields.Many2one(
        'ab_employee_access', required=True, readonly=True, ondelete='restrict'
    )
    company_id = fields.Many2one('res.company', required=True, readonly=True)
    state = fields.Selection(
        [('active', 'Active'), ('closed', 'Closed')],
        default='active',
        required=True,
        readonly=True,
    )
    login_at = fields.Datetime(
        default=fields.Datetime.now, required=True, readonly=True
    )
    expires_at = fields.Datetime(required=True, readonly=True)
    last_activity_at = fields.Datetime(default=fields.Datetime.now, readonly=True)
    device_uid = fields.Char(required=True, readonly=True)
    _token_unique = models.Constraint(
        'UNIQUE(token_hash)', 'Chatter session tokens must be unique.'
    )

    def _get_pos_profile(self):
        self.ensure_one()
        return self.profile_id

    def _try_lock_activity(self):
        self.ensure_one()
        self.flush_recordset()
        try:
            with self.env.cr.savepoint(flush=False):
                self.env.cr.execute(
                    SQL(
                        'SELECT id FROM %s WHERE id = %s '
                        'FOR NO KEY UPDATE SKIP LOCKED',
                        SQL.identifier(self._table),
                        self.id,
                    ),
                    log_exceptions=False,
                )
                return self if self.env.cr.fetchone() else self.browse()
        except SerializationFailure:
            session_fields = [
                'token_hash', 'user_id', 'employee_id', 'profile_id',
                'company_id', 'state', 'login_at', 'expires_at', 'device_uid',
            ]
            previous = self.read(session_fields, load=None)
            with self.env.registry.cursor() as cursor:
                current_env = api.Environment(
                    cursor, self.env.uid, self.env.context, su=self.env.su
                )
                current = current_env[self._name].browse(self.id).exists()
                if current.read(session_fields, load=None) != previous:
                    raise
            return self.browse()

    def unlink(self):
        raise UserError(_('Close chatter sessions instead of deleting them.'))


class ChatterAPI(models.AbstractModel):
    _name = 'ab_crm_chatter_api'
    _description = 'Sales Chatter Login API'

    def _require_staff(self):
        user = self.env.user
        if (
            user.share
            or not user.active
            or user.has_group('ab_crm_messaging.group_service')
        ):
            raise AccessError(_('A staff Odoo login is required for Sales Chatter.'))
        if not user.has_group('ab_crm_sales_workspace.group_agent'):
            raise AccessError(_('Sales Operations access is required.'))
        if user.has_group('ab_crm_core.group_service') and not user.has_group(
            'base.group_system'
        ):
            raise AccessError(_('A staff Odoo login is required for Sales Chatter.'))

    def _eligible(self, profile):
        employee = profile.employee_id
        user = employee.user_id
        return bool(
            profile
            and employee
            and employee.active
            and user.active
            and user.has_group('ab_sales.group_call_center')
            and self.env.company in user.company_ids
            and profile.pos_allow_login
            and profile._effective_pos_permissions().get('allow_pos_screen')
        )

    def _session(self, token):
        self._require_staff()
        if not isinstance(token, str) or not 20 <= len(token) <= 256:
            raise AccessError(_('Sign in to Sales Chatter with your employee and PIN.'))
        session = (
            self.env['ab_crm_chatter_session']
            .sudo()
            .search(
                [
                    ('token_hash', '=', sha256(token.encode()).hexdigest()),
                    ('user_id', '=', self.env.uid),
                    ('company_id', '=', self.env.company.id),
                    ('state', '=', 'active'),
                    ('expires_at', '>', fields.Datetime.now()),
                ],
                limit=1,
            )
        )
        if not session or not self._eligible(session.profile_id):
            raise AccessError(_('Your chatter session expired. Sign in again.'))
        activity_cutoff = fields.Datetime.now() - timedelta(minutes=1)
        if session.last_activity_at < activity_cutoff:
            locked_session = session._try_lock_activity()
            if locked_session:
                locked_session.invalidate_recordset(['last_activity_at'])
                if locked_session.last_activity_at < activity_cutoff:
                    locked_session.write({'last_activity_at': fields.Datetime.now()})
        return session

    def _payload(self, session):
        return {
            'employee': session.employee_id.name,
            'employee_id': session.employee_id.id,
            'expires_at': fields.Datetime.to_string(session.expires_at),
        }

    @api.model
    def bootstrap(self, token=False):
        self._require_staff()
        profiles = (
            self.env['ab_employee_access']
            .sudo()
            .search(
                [('pos_allow_login', '=', True), ('employee_id.user_id', '!=', False)]
            )
        )
        employees = [
            {'id': p.id, 'name': p.employee_id.name}
            for p in profiles
            if self._eligible(p)
        ]
        session = False
        if token:
            try:
                session = self._payload(self._session(token))
            except AccessError:
                pass
        return {
            'employees': employees,
            'session': session,
        }

    @api.model
    def employee_login(self, profile_id, pin, device_uid):
        self._require_staff()
        if (
            type(profile_id) is not int
            or not isinstance(pin, str)
            or not isinstance(device_uid, str)
            or not 1 <= len(device_uid) <= 128
        ):
            raise AccessError(_('Invalid chatter login.'))
        user = self.env.user.sudo()
        user.lock_for_update()
        user.invalidate_recordset(['chatter_failed_attempts', 'chatter_blocked_until'])
        if (
            user.chatter_blocked_until
            and user.chatter_blocked_until > fields.Datetime.now()
        ):
            return {'error': _('Too many login attempts. Try again in five minutes.')}
        profile = self.env['ab_employee_access'].sudo().browse(profile_id).exists()
        if not self._eligible(profile) or not profile.check_pos_pin(pin):
            attempts = user.chatter_failed_attempts + 1
            user.write(
                {
                    'chatter_failed_attempts': attempts if attempts < 5 else 0,
                    'chatter_blocked_until': (
                        fields.Datetime.now() + timedelta(minutes=5)
                        if attempts >= 5
                        else False
                    ),
                }
            )
            return {
                'error': _(
                    'Select an authorized Call Center employee and enter the correct PIN.'
                )
            }
        user.write({'chatter_failed_attempts': 0, 'chatter_blocked_until': False})
        sessions = self.env['ab_crm_chatter_session'].sudo()
        sessions.search(
            [
                ('user_id', '=', self.env.uid),
                ('company_id', '=', self.env.company.id),
                ('device_uid', '=', device_uid),
                ('state', '=', 'active'),
            ]
        ).write({'state': 'closed'})
        token = secrets.token_urlsafe(32)
        session = sessions.create(
            {
                'user_id': self.env.uid,
                'employee_id': profile.employee_id.id,
                'profile_id': profile.id,
                'company_id': self.env.company.id,
                'device_uid': device_uid,
                'token_hash': sha256(token.encode()).hexdigest(),
                'expires_at': fields.Datetime.now() + timedelta(hours=8),
            }
        )
        return dict(self._payload(session), token=token)

    @api.model
    def logout(self, token):
        self._session(token).write({'state': 'closed'})
        return True

