import re

from odoo import _, api, fields, models, tools
from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
from odoo.exceptions import AccessError, ValidationError
from odoo.tools import SQL, config, str2bool


OVERRIDE_MODEL_NAME = 'ab_odoo_replication_override'
MODEL_NAME_PATTERN = re.compile(r'^[a-z_][a-z0-9_.]*$')


class AbOdooReplicationOverride(models.Model):
    _name = OVERRIDE_MODEL_NAME
    _description = 'Odoo Replication Model Override'
    _rec_name = 'model_name'
    _order = 'model_name'

    active = fields.Boolean(default=True)
    model_name = fields.Char(required=True, index=True)
    model_available = fields.Boolean(compute='_compute_model_available')
    disable_write = fields.Boolean(default=True)
    disable_create = fields.Boolean(default=True)
    disable_unlink = fields.Boolean(default=True)
    ignore_write_date = fields.Boolean(
        default=True,
        help='Preserve the existing write date for trusted replication writes.',
    )
    control_server_bypass = fields.Boolean(
        default=False,
        help='Allow normal create, write, and delete operations on a control server.',
    )
    allow_replication_create = fields.Boolean(
        default=False,
        help='Allow trusted replication code to create records.',
    )
    allow_replication_unlink = fields.Boolean(
        default=False,
        help='Allow trusted replication code to delete records.',
    )
    allowed_write_group_ids = fields.Many2many(
        comodel_name='res.groups',
        relation='ab_rep_override_write_group_rel',
        column1='override_id',
        column2='group_id',
        string='Groups Allowed to Write',
    )
    allowed_create_group_ids = fields.Many2many(
        comodel_name='res.groups',
        relation='ab_rep_override_create_group_rel',
        column1='override_id',
        column2='group_id',
        string='Groups Allowed to Create',
    )

    _model_name_uniq = models.Constraint(
        'UNIQUE(model_name)',
        'Only one replication override is allowed per model.',
    )

    @api.depends('model_name')
    def _compute_model_available(self):
        available_models = self.env.registry.models
        for override in self:
            override.model_available = override.model_name in available_models

    @api.constrains('model_name')
    def _check_model_name(self):
        for override in self:
            model_name = (override.model_name or '').strip()
            if model_name == OVERRIDE_MODEL_NAME:
                raise ValidationError(_(
                    'The replication override configuration model cannot protect itself.'
                ))
            if not MODEL_NAME_PATTERN.fullmatch(model_name):
                raise ValidationError(_(
                    '%(model_name)s is not a valid Odoo technical model name.',
                    model_name=model_name,
                ))

    def _clear_override_cache(self):
        self.env.registry.clear_cache()

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [
            {
                **vals,
                **(
                    {'model_name': vals['model_name'].strip()}
                    if isinstance(vals.get('model_name'), str)
                    else {}
                ),
            }
            for vals in vals_list
        ]
        overrides = super().create(vals_list)
        overrides._clear_override_cache()
        return overrides

    def write(self, vals):
        if isinstance(vals.get('model_name'), str):
            vals = {**vals, 'model_name': vals['model_name'].strip()}
        result = super().write(vals)
        self._clear_override_cache()
        return result

    def unlink(self):
        result = super().unlink()
        self._clear_override_cache()
        return result


class Base(models.AbstractModel):
    _inherit = 'base'

    def _replication_override_lifecycle_bypass(self):
        return (
            self._name == OVERRIDE_MODEL_NAME
            or self.env.context.get('install_mode')
            or self.env.context.get(MODULE_UNINSTALL_FLAG)
        )

    @tools.ormcache()
    def _get_replication_override_policy(self):
        domain = (
            fields.Domain('model_name', '=', self._name)
            & fields.Domain('active', '=', True)
        )
        override = self.env[OVERRIDE_MODEL_NAME].sudo().search(domain, limit=1)
        if not override:
            return None
        return {
            'disable_write': override.disable_write,
            'disable_create': override.disable_create,
            'disable_unlink': override.disable_unlink,
            'ignore_write_date': override.ignore_write_date,
            'control_server_bypass': override.control_server_bypass,
            'allow_replication_create': override.allow_replication_create,
            'allow_replication_unlink': override.allow_replication_unlink,
            'allowed_write_group_ids': frozenset(override.allowed_write_group_ids.ids),
            'allowed_create_group_ids': frozenset(override.allowed_create_group_ids.ids),
        }

    def _get_active_replication_override_policy(self):
        if self._replication_override_lifecycle_bypass():
            return None
        return self._get_replication_override_policy()

    def _is_trusted_replication_operation(self):
        return bool(self.env.context.get('replication') and self.env.su)

    def _is_control_server(self):
        value = config.get('is_control_server', False)
        return str2bool(value, False) if isinstance(value, str) else bool(value)

    def _user_has_any_replication_override_group(self, group_ids):
        return bool(group_ids.intersection(self.env.user._get_group_ids()))

    def _raise_replication_override_access_error(self, operation):
        raise AccessError(_(
            "This is a replication database. The %(operation)s operation is not allowed on %(model)s.",
            operation=operation,
            model=self._description,
        ))

    def _write_preserving_replication_write_date(self, values):
        if not self or not self._log_access or 'write_date' not in self._fields:
            return super().write(values)

        original_dates = {
            row['id']: row['write_date']
            for row in self.sudo().read(['write_date'])
        }
        result = super().write(values)
        self.flush_recordset(['write_date'])

        rows = SQL(', ').join(
            SQL('(%s, %s)', record_id, write_date)
            for record_id, write_date in original_dates.items()
        )
        if rows:
            self.env.cr.execute(SQL(
                '''
                UPDATE %s AS target
                   SET write_date = snapshot.write_date
                  FROM (VALUES %s) AS snapshot(id, write_date)
                 WHERE target.id = snapshot.id
                ''',
                SQL.identifier(self._table),
                rows,
            ))
            self.invalidate_recordset(['write_date'])
        return result

    @api.model_create_multi
    def create(self, vals_list):
        policy = self._get_active_replication_override_policy()
        if not policy:
            return super().create(vals_list)

        if self._is_trusted_replication_operation() and policy['allow_replication_create']:
            return super().create(vals_list)
        if policy['control_server_bypass'] and self._is_control_server():
            return super().create(vals_list)
        if not policy['disable_create'] or self._user_has_any_replication_override_group(
            policy['allowed_create_group_ids']
        ):
            return super().create(vals_list)
        self._raise_replication_override_access_error(_('create'))

    def write(self, values):
        policy = self._get_active_replication_override_policy()
        if not policy:
            return super().write(values)

        if self._is_trusted_replication_operation():
            if policy['ignore_write_date']:
                return self._write_preserving_replication_write_date(values)
            return super().write(values)
        if policy['control_server_bypass'] and self._is_control_server():
            return super().write(values)
        if not policy['disable_write'] or self._user_has_any_replication_override_group(
            policy['allowed_write_group_ids']
        ):
            return super().write(values)
        self._raise_replication_override_access_error(_('write'))

    def unlink(self):
        policy = self._get_active_replication_override_policy()
        if not policy:
            return super().unlink()

        if self._is_trusted_replication_operation() and policy['allow_replication_unlink']:
            return super().unlink()
        if policy['control_server_bypass'] and self._is_control_server():
            return super().unlink()
        if not policy['disable_unlink']:
            return super().unlink()
        self._raise_replication_override_access_error(_('delete'))
