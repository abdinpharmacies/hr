from odoo import models


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
