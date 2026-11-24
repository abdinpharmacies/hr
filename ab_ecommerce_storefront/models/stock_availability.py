from odoo import _, models
from odoo.exceptions import ValidationError


class ProductProduct(models.Model):
    _inherit = "product.product"

    def _get_ab_website_available_qty(self):
        quantity = super()._get_ab_website_available_qty()
        if quantity is None:
            return quantity
        website = self.env["website"].get_current_website()
        warehouse_id = self.env.context.get("warehouse_id") or website._ab_storefront_stock_warehouse_id()
        warehouse = self.env["stock.warehouse"].sudo().browse(warehouse_id).exists()
        product = self.sudo()
        if (
            not warehouse
            or warehouse.company_id != website.company_id
            or (product.company_id and product.company_id != website.company_id)
            or not product.is_storable
        ):
            return 0.0
        free_quantity = product.with_company(website.company_id).with_context(
            warehouse_id=warehouse.id,
        ).free_qty
        return min(quantity, max(free_quantity, 0.0))


class Website(models.Model):
    _inherit = "website"

    def _ab_storefront_stock_warehouse_id(self):
        self.ensure_one()
        website = self.sudo().with_company(self.company_id)
        warehouse = website.warehouse_id
        if not warehouse:
            defaults = website.env["ir.default"]._get_model_defaults("sale.order")
            warehouse = (
                website.env["stock.warehouse"].browse(defaults["warehouse_id"]).exists()
                if defaults.get("warehouse_id")
                else website.env.user._get_default_warehouse_id()
            )
        return warehouse.id if warehouse.company_id == website.company_id else False

    def _ab_offer_available_quantities(self, products):
        self.ensure_one()
        products.check_access("read")
        if self.company_id != self.env.company or any(
            not p.active or not p.sale_ok or (p.company_id and p.company_id != self.company_id)
            or (p.website_id and p.website_id != self) for p in products
        ):
            raise ValidationError(_("Select active saleable products for this website and company."))
        warehouse = self.env["stock.warehouse"].sudo().browse(self._ab_storefront_stock_warehouse_id())
        if not warehouse or not products:
            return {}
        tracked = products.with_context(
            {}, warehouse_id=warehouse.id, allowed_company_ids=self.company_id.ids,
        ).sudo().filtered("is_storable")
        free = tracked._compute_quantities_dict(None, None, None) if tracked else {}
        held = self.env["ab_storefront_cart_hold"]._quantities(tracked, self.company_id, warehouse)
        sources = tracked.ab_product_id.filtered(lambda source: not source.is_service)
        snapshots = self.env["ab_eplus_stock_snapshot"].sudo()
        eplus = {
            source.id: snapshots._get_odoo_inventory_target_qty(source, quantity) or 0
            for source, quantity in snapshots._read_group(
                [("active", "=", True), ("product_id", "in", sources.ids)],
                ["product_id"], ["itm_qty:sum"],
            )
        } if sources else {}
        quantities = {}
        for product in tracked:
            quantity = free[product.id]["free_qty"]
            if product.ab_product_id and not product.ab_product_id.is_service:
                reported = eplus.get(product.ab_product_id.id, 0)
                shown = product.eplus_stock_shown_qty_value
                if product.eplus_stock_shown_qty_type == "percentage":
                    shown = reported * shown / 100
                quantity = min(quantity, reported, shown)
            quantities[product.id] = max(0, quantity - held.get(product.id, 0))
        return quantities

    def _ab_offer_stock_issue(self, products, quantities, group_qty):
        unavailable = products.filtered(lambda p: quantities.get(p.id, 0) < 1)
        if unavailable:
            return _("No available stock for: %s", ", ".join(unavailable.mapped("display_name")))
        if sum(int(quantities.get(p.id, 0)) for p in products) < group_qty:
            return _("Available stock is below the qualifying group size of %s.", group_qty)
        return ""

    def _ab_publish_offer_products(self, products):
        self.ensure_one()
        templates = products.product_tmpl_id.with_context({}, website_id=self.id, allowed_company_ids=self.company_id.ids)
        unpublished = templates.filtered(lambda template: not template.is_published)
        if not unpublished:
            return
        if self.company_id != self.env.company or any(
            not template.sale_ok or not template.active or (template.company_id and template.company_id != self.company_id)
            or (template.website_id and template.website_id != self) for template in unpublished
        ):
            raise ValidationError(_("Select active saleable products for this website and company."))
        unpublished.check_access("read")
        if self.env.user.has_group("sales_team.group_sale_manager"):
            unpublished = unpublished.sudo()
        shared = unpublished.filtered(lambda template: not template.website_id)
        if shared:
            shared.write({"website_id": self.id, "is_published": True})
        (unpublished - shared).write({"is_published": True})

    def _get_product_available_qty(self, product, **kwargs):
        self.ensure_one()
        return super()._get_product_available_qty(
            product.with_context(
                website_id=self.id, warehouse_id=self._ab_storefront_stock_warehouse_id(),
            ),
            **kwargs,
        )


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _get_free_qty(self, product):
        self.ensure_one()
        if self.website_id:
            product = product.with_context(
                website_id=self.website_id.id,
                warehouse_id=self._get_shop_warehouse_id() or self.warehouse_id.id,
            )
        return super()._get_free_qty(product)
