from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import html_escape


class AbProductGroup(models.Model):
    _inherit = "ab_product_group"

    website_public_category_id = fields.Many2one(
        "product.public.category",
        string="Website Category",
        copy=False,
        readonly=True,
        groups="base.group_user",
    )

    def _get_or_create_website_categories(self):
        categories = self.env["product.public.category"].sudo()
        for group in self:
            categories |= group._get_or_create_website_category()
        return categories

    def _get_or_create_website_category(self):
        self.ensure_one()
        Category = self.env["product.public.category"].sudo()
        category = self.website_public_category_id.sudo()
        parent = self.parent_id._get_or_create_website_category() if self.parent_id else Category
        name = self.name or self.code or _("Unnamed Category")
        vals = {
            "name": name,
            "parent_id": parent.id if parent else False,
        }

        if category:
            category.write(vals)
        else:
            category = Category.create(vals)
            self.sudo().website_public_category_id = category.id
        return category


class AbProductTag(models.Model):
    _inherit = "ab_product_tag"

    website_product_tag_id = fields.Many2one(
        "product.tag",
        string="Website Product Tag",
        copy=False,
        readonly=True,
        groups="base.group_user",
    )

    def _get_or_create_website_product_tags(self):
        product_tags = self.env["product.tag"].sudo()
        ProductTag = self.env["product.tag"].sudo()
        for tag in self:
            name = tag.name or _("Unnamed Tag")
            product_tag = tag.website_product_tag_id.sudo()
            if not product_tag:
                product_tag = ProductTag.search([("name", "=", name)], limit=1)
            vals = {
                "name": name,
                "sequence": tag.priority or 10,
                "visible_to_customers": True,
            }
            if product_tag:
                product_tag.write(vals)
            else:
                product_tag = ProductTag.create(vals)
            tag.sudo().website_product_tag_id = product_tag.id
            product_tags |= product_tag
        return product_tags


class AbProduct(models.Model):
    _inherit = "ab_product"

    website_sale_available = fields.Boolean(
        string="Available on Website",
        default=True,
        help="When enabled, sync publishes the linked eCommerce product if this product is active and allowed for sale.",
    )
    website_product_tmpl_id = fields.Many2one(
        "product.template",
        string="eCommerce Product",
        compute="_compute_website_product_tmpl_id",
        search="_search_website_product_tmpl_id",
        compute_sudo=True,
        groups="base.group_user",
    )
    website_product_synced = fields.Boolean(
        string="Synced to eCommerce",
        compute="_compute_website_product_synced",
        search="_search_website_product_synced",
        compute_sudo=True,
        groups="base.group_user",
    )
    website_product_is_published = fields.Boolean(
        string="Published on Website",
        compute="_compute_website_product_is_published",
        search="_search_website_product_is_published",
        compute_sudo=True,
        groups="base.group_user",
    )

    def _compute_website_product_tmpl_id(self):
        templates = self.env["product.template"].sudo().with_context(active_test=False).search([
            ("ab_product_id", "in", self.ids),
        ])
        template_by_product_id = {}
        for template in templates:
            template_by_product_id.setdefault(template.ab_product_id.id, template)
        for product in self:
            product.website_product_tmpl_id = template_by_product_id.get(product.id)

    def _compute_website_product_synced(self):
        for product in self:
            product.website_product_synced = bool(product.website_product_tmpl_id)

    def _compute_website_product_is_published(self):
        for product in self:
            template = product.website_product_tmpl_id
            product.website_product_is_published = bool(
                template and template.active and template.sale_ok and template.is_published
            )

    @api.model
    def _search_website_product_tmpl_id(self, operator, value):
        if operator in ("=", "!=") and not value:
            synced = operator == "!="
            return self._website_product_synced_domain(synced)
        if operator in ("=", "!=") and value:
            templates = self.env["product.template"].sudo().with_context(active_test=False).search([
                ("id", operator, value),
                ("ab_product_id", "!=", False),
            ])
            return [("id", "in", templates.mapped("ab_product_id").ids)]
        return NotImplemented

    @api.model
    def _search_website_product_synced(self, operator, value):
        if operator not in ("=", "!="):
            return NotImplemented
        synced = bool(value)
        if operator == "!=":
            synced = not synced
        return self._website_product_synced_domain(synced)

    @api.model
    def _search_website_product_is_published(self, operator, value):
        if operator not in ("=", "!="):
            return NotImplemented
        published = bool(value)
        if operator == "!=":
            published = not published
        return self._website_product_published_domain(published)

    @api.model
    def _website_product_synced_domain(self, synced):
        product_ids = self._website_linked_ab_product_ids()
        return [("id", "in" if synced else "not in", product_ids)]

    @api.model
    def _website_product_published_domain(self, published):
        product_ids = self._website_linked_ab_product_ids([
            ("active", "=", True),
            ("sale_ok", "=", True),
            ("is_published", "=", True),
        ])
        return [("id", "in" if published else "not in", product_ids)]

    @api.model
    def _website_linked_ab_product_ids(self, extra_domain=None):
        domain = [("ab_product_id", "!=", False)]
        if extra_domain:
            domain += extra_domain
        return self.env["product.template"].sudo().with_context(active_test=False).search(domain).mapped("ab_product_id").ids

    @api.model
    def _ab_text_to_html(self, text):
        if not text:
            return False
        lines = str(html_escape(text)).splitlines() or [""]
        return "<p>%s</p>" % "<br/>".join(lines)

    def _prepare_website_product_template_vals(self):
        self.ensure_one()
        ProductTemplate = self.env["product.template"]
        public_categories = self.groups_ids._get_or_create_website_categories()
        product_tags = self.tag_ids._get_or_create_website_product_tags()
        name = self.name or self.product_card_name or self.code or _("Unnamed Product")
        description = self.description or False
        sale_ok = bool(self.active and self.allow_sale)
        is_published = bool(sale_ok and self.website_sale_available)

        vals = {
            "ab_product_id": self.id,
            "name": name,
            "default_code": self.code or False,
            "list_price": self.default_price or 0.0,
            "standard_price": self.default_cost or 0.0,
            "type": "service" if self.is_service else "consu",
            "sale_ok": sale_ok,
            "purchase_ok": bool(self.active and self.allow_purchase),
            "active": bool(self.active),
            "description_sale": description,
            "description": self._ab_text_to_html(description),
            "description_ecommerce": self._ab_text_to_html(description),
            "website_description": self._ab_text_to_html(description),
            "is_published": is_published,
            "public_categ_ids": [fields.Command.set(public_categories.ids)],
            "product_tag_ids": [fields.Command.set(product_tags.ids)],
        }
        if "invoice_policy" in ProductTemplate._fields:
            vals["invoice_policy"] = "order"
        if "service_tracking" in ProductTemplate._fields:
            vals["service_tracking"] = "no"
        return vals

    def _prepare_website_product_variant_vals(self):
        self.ensure_one()
        barcode = self.barcode_ids.filtered("name")[:1].name or False
        return {
            "default_code": self.code or False,
            "barcode": barcode,
        }

    def _sync_website_products(self):
        ProductTemplate = self.env["product.template"].sudo().with_context(active_test=False)
        synced_templates = ProductTemplate.browse()
        for product in self.sudo():
            template = ProductTemplate.search([("ab_product_id", "=", product.id)], limit=1)
            vals = product._prepare_website_product_template_vals()
            if template:
                template.write(vals)
            else:
                template = ProductTemplate.create(vals)

            variant = template.product_variant_id or template.with_context(active_test=False).product_variant_ids[:1]
            if variant:
                variant.sudo().write(product._prepare_website_product_variant_vals())
            synced_templates |= template
        return synced_templates

    def action_sync_website_product(self):
        templates = self._sync_website_products()
        if len(self) == 1 and templates:
            return {
                "type": "ir.actions.act_window",
                "name": _("eCommerce Product"),
                "res_model": "product.template",
                "res_id": templates[0].id,
                "view_mode": "form",
                "target": "current",
            }
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("eCommerce Sync"),
                "message": _("%s products synced to the website shop.", len(templates)),
                "type": "success",
                "sticky": False,
            },
        }

    def action_open_website_product(self):
        self.ensure_one()
        template = self.website_product_tmpl_id
        if not template:
            template = self._sync_website_products()
        if not template:
            raise UserError(_("No eCommerce product could be found or created."))
        return {
            "type": "ir.actions.act_window",
            "name": _("eCommerce Product"),
            "res_model": "product.template",
            "res_id": template.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_open_website_product_page(self):
        self.ensure_one()
        template = self.website_product_tmpl_id
        if not template:
            template = self._sync_website_products()
        if not template.is_published:
            raise UserError(_("The linked eCommerce product is not published. Enable Website availability and sync again."))
        return template.open_website_url()

    @api.model
    def cron_sync_website_products(self, limit=1000):
        products = self.search([
            ("active", "=", True),
            ("allow_sale", "=", True),
            ("website_sale_available", "=", True),
        ], limit=limit)
        products._sync_website_products()
        return True
