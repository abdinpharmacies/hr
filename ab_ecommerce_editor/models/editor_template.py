from odoo import api, fields, models, _
from odoo.exceptions import AccessError

from .editor_document import validate_blocks, validate_style, validate_website


class EditorTemplate(models.Model):
    _name = 'ab_ecommerce_editor_template'
    _description = 'eCommerce Editor Reusable Block'
    _order = 'name, id'

    name = fields.Char(required=True)
    website_id = fields.Many2one('website', required=True, default=lambda self: self.env['website'].search(fields.Domain('company_id', 'in', self.env.companies.ids), limit=1))
    company_id = fields.Many2one(related='website_id.company_id', store=True)
    scope = fields.Selection([('global', 'All content'), ('page', 'Pages'), ('blog', 'Blog posts')], default='global', required=True)
    blocks = fields.Json(default=list)
    design_tokens = fields.Json(default=dict)
    active = fields.Boolean(default=True)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for website in records.website_id:
            validate_website(website)
        return records

    def write(self, values):
        if 'website_id' in values:
            validate_website(self.env['website'].browse(values['website_id']))
        return super().write(values)

    @api.constrains('blocks', 'design_tokens')
    def _check_blocks(self):
        for template in self:
            validate_blocks(template.blocks or [])
            validate_style(template.design_tokens or {})

    def unlink(self):
        raise AccessError(_('Archive reusable blocks instead of deleting them.'))
