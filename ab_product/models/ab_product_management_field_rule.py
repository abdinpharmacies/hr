from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.translate import _


class AbProductManagementFieldRule(models.Model):
    _name = 'ab_product_management_field_rule'
    _description = 'AB Product Management Field Rule'

    EXCLUDED_FIELD_NAMES = frozenset({
        'id',
        'create_uid',
        'create_date',
        'write_uid',
        'write_date',
    })
    ACCESS_NAME_PREFIX = 'AB Product Field Rule Write:'

    group_id = fields.Many2one('res.groups', required=True, index=True, ondelete='cascade')
    field_ids = fields.Many2many(
        'ir.model.fields',
        'ab_product_management_field_rule_field_rel',
        'rule_id',
        'field_id',
        string='Writable Fields',
        domain=[
            ('model', '=', 'ab_product'),
            ('store', '=', True),
            ('name', 'not in', list(EXCLUDED_FIELD_NAMES)),
        ],
        required=True,
    )
    editable_fields = fields.Char(compute='_compute_editable_fields')

    _uniq_group_id = models.Constraint(
        'UNIQUE(group_id)',
        'A product field rule already exists for this group.',
    )

    @api.depends('field_ids')
    def _compute_editable_fields(self):
        for rec in self:
            rec.editable_fields = ', '.join(rec.field_ids.sorted('name').mapped('name'))

    @api.constrains('field_ids')
    def _check_field_ids(self):
        for rec in self:
            if not rec.field_ids:
                raise ValidationError(_('At least one writable field is required.'))
            invalid_fields = rec.field_ids.filtered(lambda field: not rec._is_allowed_product_field(field))
            if invalid_fields:
                raise ValidationError(
                    _('Only stored ab_product fields can be selected. Excluded field(s): %s')
                    % ', '.join(invalid_fields.mapped('name'))
                )

    def _is_allowed_product_field(self, field):
        self.ensure_one()
        return (
            field.model == 'ab_product'
            and bool(field.store)
            and field.name not in self.EXCLUDED_FIELD_NAMES
        )

    @api.model
    def _allowed_field_names_for_user(self, user=None):
        user = (user or self.env.user).sudo()
        group_ids = user.group_ids.ids
        if not group_ids:
            return set()
        rules = self.sudo().search([('group_id', 'in', group_ids)])
        return set(rules.field_ids.mapped('name'))

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_product_write_acl_for_groups(records.mapped('group_id').ids)
        return records

    def write(self, vals):
        group_ids = set(self.mapped('group_id').ids)
        result = super().write(vals)
        group_ids.update(self.mapped('group_id').ids)
        self._sync_product_write_acl_for_groups(group_ids)
        return result

    def unlink(self):
        group_ids = set(self.mapped('group_id').ids)
        result = super().unlink()
        self._sync_product_write_acl_for_groups(group_ids)
        return result

    @api.model
    def _managed_access_name(self, group_id):
        return f'{self.ACCESS_NAME_PREFIX}{group_id}'

    @api.model
    def _managed_access_domain(self, group_id, product_model):
        return [
            ('name', '=', self._managed_access_name(group_id)),
            ('model_id', '=', product_model.id),
            ('group_id', '=', group_id),
        ]

    @api.model
    def _product_model(self):
        return self.env['ir.model'].sudo().search([('model', '=', 'ab_product')], limit=1)

    @api.model
    def _delete_product_write_acl_for_groups(self, group_ids):
        group_ids = set(group_ids or [])
        if not group_ids:
            return

        product_model = self._product_model()
        if not product_model:
            return

        Access = self.env['ir.model.access'].sudo()
        for group_id in group_ids:
            Access.search(self._managed_access_domain(group_id, product_model)).unlink()

    @api.model
    def _sync_product_write_acl_for_groups(self, group_ids):
        group_ids = set(group_ids or [])
        if not group_ids:
            return

        product_model = self._product_model()
        if not product_model:
            return

        Access = self.env['ir.model.access'].sudo()
        Group = self.env['res.groups'].sudo()
        configured_group_ids = set(
            self.sudo().search([('group_id', 'in', list(group_ids))]).mapped('group_id').ids
        )

        for group in Group.browse(list(group_ids)).exists():
            access = Access.search(self._managed_access_domain(group.id, product_model), limit=1)
            if group.id in configured_group_ids:
                vals = {
                    'name': self._managed_access_name(group.id),
                    'model_id': product_model.id,
                    'group_id': group.id,
                    'perm_read': True,
                    'perm_write': True,
                    'perm_create': False,
                    'perm_unlink': False,
                }
                if access:
                    access.write(vals)
                else:
                    Access.create(vals)
            elif access:
                access.unlink()


class ResGroups(models.Model):
    _inherit = 'res.groups'

    def unlink(self):
        self.env['ab_product_management_field_rule'].sudo()._delete_product_write_acl_for_groups(self.ids)
        return super().unlink()
