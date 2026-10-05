from odoo import api, fields, models
from odoo.exceptions import AccessError


SHOP_NEEDS = (
    ('acne_treatment', 'Acne treatment'),
    ('skin_brightening', 'Skin brightening and tone correction'),
    ('dry_skin_hydration', 'Dry skin hydration'),
    ('hair_loss_treatment', 'Hair loss treatment'),
    ('dandruff_control', 'Dandruff control'),
    ('sun_protection', 'Sun protection'),
    ('anti_aging', 'Anti-aging and wrinkle care'),
    ('immune_support', 'Immune support'),
    ('energy_vitality', 'Energy and vitality'),
    ('sensitive_skin', 'Sensitive skin care'),
)


class ProductTag(models.Model):
    _inherit = 'product.tag'

    ab_shop_need_key = fields.Selection(SHOP_NEEDS, string='Shop Need', copy=False, index=True)

    _shop_need_key_unique = models.UniqueIndex(
        '(ab_shop_need_key) WHERE ab_shop_need_key IS NOT NULL',
        'Each shop need must have a unique key.',
    )

    @api.model_create_multi
    def create(self, vals_list):
        if any(vals.get('ab_shop_need_key') for vals in vals_list):
            self._check_shop_need_manager()
        return super().create(vals_list)

    def write(self, vals):
        if 'ab_shop_need_key' in vals or any(self.mapped('ab_shop_need_key')):
            self._check_shop_need_manager()
        return super().write(vals)

    def unlink(self):
        if any(self.mapped('ab_shop_need_key')):
            raise AccessError(self.env._('Shop needs must be retained.'))
        return super().unlink()

    def _check_shop_need_manager(self):
        if not self.env.user.has_group('base.group_system'):
            raise AccessError(self.env._('Only administrators can configure shop needs.'))

    def _ab_shop_category_ids(self, website):
        needs = self.filtered('ab_shop_need_key')
        nodes = self.env['ab_product_classification_taxonomy'].sudo().search(
            fields.Domain('need_ids', 'in', needs.ids)
        ) if needs else self.env['ab_product_classification_taxonomy']
        return nodes.filtered('ready').category_id.filtered(
            lambda category: not category.website_id or category.website_id == website
        ).ids


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    ab_shop_need_ids = fields.Many2many('product.tag', compute='_compute_ab_shop_need_ids', string='Shop by Need')

    @api.depends('public_categ_ids', 'public_categ_ids.parent_id')
    def _compute_ab_shop_need_ids(self):
        categories = self.public_categ_ids.parents_and_self
        nodes = self.env['ab_product_classification_taxonomy'].sudo().search(
            fields.Domain('category_id', 'in', categories.ids)
        ) if categories else self.env['ab_product_classification_taxonomy']
        by_category = {node.category_id.id: node.need_ids for node in nodes.filtered('ready')}
        for product in self:
            needs = self.env['product.tag']
            for category in product.public_categ_ids.parents_and_self:
                needs |= by_category.get(category.id, self.env['product.tag'])
            product.ab_shop_need_ids = needs

    @api.model
    def _search_get_detail(self, website, order, options):
        result = super()._search_get_detail(website, order, options)
        need_key = options.get('ab_shop_need_key')
        if need_key:
            need = self.env['product.tag'].search(fields.Domain('ab_shop_need_key', '=', need_key))
            category_ids = need._ab_shop_category_ids(website)
            result['base_domain'].append(list(fields.Domain('public_categ_ids', 'child_of', category_ids)))
        return result


class AbProduct(models.Model):
    _inherit = 'ab_product'

    ab_shop_need_ids = fields.Many2many(related='website_product_tmpl_id.ab_shop_need_ids', string='Shop by Need')
