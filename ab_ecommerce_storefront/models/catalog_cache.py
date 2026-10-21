from odoo import api, fields, models, tools


def _invalidate_catalog(env):
    env["product.public.category"].invalidate_model(["has_published_products"])
    env.registry.clear_cache()
    if not env.cr.cache.get("ab_storefront_catalog_dirty"):
        env.cr.cache["ab_storefront_catalog_dirty"] = True
        registry, cache = env.registry, env.cr.cache

        def reset():
            cache.pop("ab_storefront_catalog_dirty", None)
            registry.clear_cache()

        env.cr.postcommit.add(reset)
        env.cr.postrollback.add(reset)


class Website(models.Model):
    _inherit = "website"

    def _ab_storefront_navigation_category_ids(self):
        self.ensure_one()
        taxonomy = self.env["ab_product_classification_taxonomy"].sudo().search(
            fields.Domain("category_id", "!=", False)
        )
        if taxonomy:
            return set(taxonomy.category_id.ids)
        return {
            category.id
            for xmlid in (
                "category_medications", "category_vitamins", "category_personal_care",
                "category_first_aid", "category_health_devices", "category_beauty",
                "category_baby_care", "category_wellness",
            )
            if (category := self.env.ref(f"ab_ecommerce_storefront.{xmlid}", raise_if_not_found=False))
        }

    def _ab_storefront_category_rows(self):
        if self.env.cr.cache.get("ab_storefront_catalog_dirty"):
            return self._ab_storefront_category_rows_uncached()
        return self._ab_storefront_category_rows_cached()

    @tools.ormcache(
        "self.id", "self.env.uid", "self.env.su", "self.env.lang",
        "tuple(self.env.companies.ids)", cache="templates.cached_values",
    )
    def _ab_storefront_category_rows_cached(self):
        return self._ab_storefront_category_rows_uncached()

    def _ab_storefront_category_rows_uncached(self):
        self.ensure_one()
        categories = self.env["product.public.category"].with_context(
            website_id=self.id, bin_size=True,
        ).search_fetch(self.website_domain(), ["name", "parent_id", "sequence"])
        categories.with_context(lang=False).fetch(["name"])
        published = set(categories.filtered("has_published_products").ids)
        rows = []
        for category in categories:
            presentation = self._ab_storefront_category_presentation(category)
            rows.append((
                category.id, category.parent_id.id, category.id in published,
                self._ab_storefront_category_label(category),
                "/shop/category/%s" % self.env["ir.http"]._slug(category),
                presentation["icon"], presentation["tone"],
            ))
        return tuple(rows)

    def _ab_storefront_category_tree(self, root_ids):
        navigation_ids = self._ab_storefront_navigation_category_ids()
        nodes = {
            row[0]: dict(zip(("id", "parent", "published", "label", "href", "icon", "tone"), row), children=[])
            for row in self._ab_storefront_category_rows() if row[0] in navigation_ids and row[2]
        }
        for node in nodes.values():
            if node["parent"] in nodes and node["published"]:
                nodes[node["parent"]]["children"].append(node)
        return [nodes[root_id] for root_id in root_ids if root_id in nodes]

    def _ab_storefront_header_category_menu(self):
        navigation_ids = self._ab_storefront_navigation_category_ids()
        return [
            dict(zip(("label", "href", "icon", "tone"), row[3:]))
            for row in self._ab_storefront_category_rows()
            if row[0] in navigation_ids and not row[1] and row[2]
        ][:8]


class ProductPublicCategory(models.Model):
    _inherit = "product.public.category"

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        _invalidate_catalog(self.env)
        return records

    def write(self, vals):
        result = super().write(vals)
        if {"name", "sequence", "parent_id", "website_id", "product_tmpl_ids"}.intersection(vals):
            _invalidate_catalog(self.env)
        return result

    def _update_field_translations(self, field_name, translations, digest=None, source_lang=''):
        result = super()._update_field_translations(field_name, translations, digest, source_lang)
        if field_name == "name" and result:
            _invalidate_catalog(self.env)
        return result


class ProductTemplate(models.Model):
    _inherit = "product.template"

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        _invalidate_catalog(self.env)
        return records

    def write(self, vals):
        result = super().write(vals)
        if {
            "active", "sale_ok", "is_published", "website_published", "website_id",
            "company_id", "public_categ_ids", "service_tracking",
        }.intersection(vals):
            _invalidate_catalog(self.env)
        return result
