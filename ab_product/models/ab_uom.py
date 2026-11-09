from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AbdinUom(models.Model):
    _name = 'ab_uom'
    _description = 'Abdin Unit Of Measure'
    _order = 'unit_size'

    type_id = fields.Many2one('ab_uom_type', required=True)
    unit_no = fields.Integer(required=True)
    unit_size = fields.Selection(selection=[(
        'large', 'Large'), ('medium', 'Medium'), ('small', 'Small')], required=True)

    @api.constrains('unit_no')
    def validate_unit_of_measure(self):
        for record in self:
            if record.unit_no < 1:
                raise UserError(_("Unit number must be greater than 1."))

            uom_criteria = [('type_id', '=', record.type_id.id),
                            ('unit_size', '=', record.unit_size),
                            ('unit_no', '=', record.unit_no)]
            uom_records = self.sudo().search(uom_criteria)
            if len(uom_records) > 1:
                raise UserError(_("Duplicate unit of measure found."))

    def name_get(self):
        res = []
        for rec in self:
            if self.env.context.get('uom_only_type', False):
                unit_size_selection = {
                    'large': 'L', 'medium': 'M', 'small': 'S'}
                res.append(
                    (rec.id, f"{rec.type_id.name} ({unit_size_selection[rec.unit_size]})"))
            else:
                res.append((rec.id, f"{rec.unit_no} {rec.type_id.name}"))

        return res

    @api.depends('type_id', 'unit_no', 'unit_size')
    @api.depends_context('uom_only_type')
    def _compute_display_name(self):
        """Keep the existing label format on the Odoo 19 display-name API."""
        names = dict(self.name_get())
        for record in self:
            record.display_name = names.get(record.id, False)

    @api.model
    def _name_search(self, name='', args=None, operator='ilike', limit=100, name_get_uid=None):
        args = list(args or [])
        if name != '' or operator != 'ilike':
            name_parts = name.split(" ")
            for part in name_parts:
                args += ['|', ('type_id', operator, part),
                         ('unit_no', operator, part)]
        return (self.with_user(name_get_uid) if name_get_uid else self).search(args, limit=limit).ids

    @api.model
    def name_search(self, name="", domain=None, operator="ilike", limit=100):
        """Expose the existing search order through the Odoo 19 public API."""
        ids = self._name_search(name, args=domain, operator=operator, limit=limit)
        return [(record.id, record.display_name) for record in self.browse(ids)]

    @api.model
    def _search_display_name(self, operator, value):
        """Keep code/barcode/name matching in relational search domains too."""
        if operator in ('in', 'not in') and isinstance(value, (list, tuple)):
            domain = fields.Domain.OR(self._search_display_name('=', item) for item in value)
            return list(~domain if operator == 'not in' else domain)
        ids = self._name_search(value or '', operator=operator, limit=None)
        return [('id', 'in', ids)]


class AbdinUomType(models.Model):
    _name = 'ab_uom_type'
    _description = 'Abdin Uom Type'

    name = fields.Char(required=True)

    @api.constrains('name')
    def _constrains_uom_type(self):
        for rec in self:
            uom_type = self.search([('name', '=ilike', rec.name)])
            if len(uom_type) > 1:
                raise UserError(
                    _(f"The Uom name '{rec.name}' must be unique. Another record with the same name already exists."))
