import json

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ListColumnOrderPref(models.Model):
    _name = 'list.column.order.pref'
    _description = 'List Column Order Preference'

    user_id = fields.Many2one(
        'res.users',
        string='User',
        required=True,
        default=lambda self: self.env.user,
        ondelete='cascade',
        index=True,
    )
    model_name = fields.Char(required=True, index=True)
    view_id = fields.Many2one('ir.ui.view', string='View', ondelete='cascade', index=True)
    column_order = fields.Text(required=True, default='[]')

    _unique_user_model_view = models.UniqueIndex(
        '(user_id, model_name, COALESCE(view_id, 0))',
        'Only one list column order preference is allowed per user, model, and view.',
    )

    @api.constrains('column_order')
    def _check_column_order_json(self):
        for pref in self:
            try:
                order = json.loads(pref.column_order or '[]')
            except json.JSONDecodeError as exc:
                raise ValidationError('Column order must be valid JSON.') from exc
            if not isinstance(order, list) or not all(isinstance(name, str) for name in order):
                raise ValidationError('Column order must be a JSON list of field names.')

    @api.model
    def _preference_domain(self, model_name, view_id=False):
        domain = [
            ('user_id', '=', self.env.uid),
            ('model_name', '=', model_name),
        ]
        if view_id:
            domain.append(('view_id', '=', view_id))
        else:
            domain.append(('view_id', '=', False))
        return domain

    @api.model
    def get_order(self, model_name, view_id=False):
        pref = self.sudo().search(self._preference_domain(model_name, view_id), limit=1)
        if not pref:
            return []
        try:
            order = json.loads(pref.column_order or '[]')
        except json.JSONDecodeError:
            return []
        return order if isinstance(order, list) else []

    @api.model
    def set_order(self, model_name, view_id=False, column_order=None):
        clean_order = [name for name in (column_order or []) if isinstance(name, str)]
        values = {
            'user_id': self.env.uid,
            'model_name': model_name,
            'view_id': view_id or False,
            'column_order': json.dumps(clean_order),
        }
        pref = self.sudo().search(self._preference_domain(model_name, view_id), limit=1)
        if pref:
            pref.write({'column_order': values['column_order']})
        else:
            pref = self.sudo().create(values)
        return True

    @api.model
    def reset_order(self, model_name, view_id=False):
        self.sudo().search(self._preference_domain(model_name, view_id)).unlink()
        return True
