from odoo import api, fields, models


class ClsCostCenters(models.Model):
    _name = 'ab_costcenter'
    _description = 'Abdin Cost Centers'

    name = fields.Char(required=True, index=True)
    code = fields.Char(size=16, required=True, index=True)
    costcenter_space_sep = fields.Char(
        compute='_compute_costcenter_space_sep',
        search='_search_costcenter_space_sep',
    )
    work_email = fields.Char('Work Email')
    active = fields.Boolean(default=True)

    def _compute_costcenter_space_sep(self):
        for rec in self:
            rec.costcenter_space_sep = str(rec.id)

    def _search_costcenter_space_sep(self, operator, value):
        if operator in ('in', 'ilike', 'not in', 'not ilike'):
            value = value.split() if isinstance(value, str) else value
            operator = 'in' if operator in ('in', 'ilike') else 'not in'
        return fields.Domain('code', operator, value)

    @api.model
    def _search_display_name(self, operator, value):
        code_ids = self._search(fields.Domain('code', '=', value))
        if code_ids:
            return fields.Domain('id', 'in', code_ids)
        return fields.Domain('name', operator, value)
