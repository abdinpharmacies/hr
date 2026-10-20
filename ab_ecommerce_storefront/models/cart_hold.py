import secrets
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.http import request
from odoo.tools import float_compare

_CONFIRMATION_TOKEN = object()


class StorefrontCartHold(models.Model):
    _name = "ab_storefront_cart_hold"
    _description = "Storefront Cart Hold"

    order_id = fields.Many2one("sale.order", required=True, index=True, ondelete="restrict")
    product_id = fields.Many2one("product.product", required=True, index=True, ondelete="restrict")
    company_id = fields.Many2one("res.company", required=True, index=True)
    warehouse_id = fields.Many2one("stock.warehouse", required=True, index=True)
    quantity = fields.Float(required=True)
    expires_at = fields.Datetime(required=True, index=True)

    _order_product_unique = models.Constraint(
        "UNIQUE(order_id, product_id)", "A cart can only hold a product once."
    )
    _quantity_positive = models.Constraint("CHECK(quantity >= 0)", "Held quantity cannot be negative.")

    @api.model
    def _quantities(self, products, company, warehouse, exclude_order=None):
        if not products or not warehouse or warehouse.company_id != company:
            return {}
        domain = (
            fields.Domain("product_id", "in", products.ids)
            & fields.Domain("company_id", "=", company.id)
            & fields.Domain("warehouse_id", "=", warehouse.id)
            & fields.Domain("expires_at", ">", fields.Datetime.now())
            & fields.Domain("order_id.state", "in", ("draft", "sent"))
        )
        if exclude_order:
            domain &= fields.Domain("order_id", "!=", exclude_order.id)
        return {
            product.id: quantity
            for product, quantity in self.sudo()._read_group(domain, ["product_id"], ["quantity:sum"])
        }


class ProductProduct(models.Model):
    _inherit = "product.product"

    ab_cart_hold_revision = fields.Char(string="Cart Hold Revision", copy=False, groups="base.group_system")

    def _ab_lock_cart_stock(self):
        products = self.exists().sorted("id")
        if not products:
            return
        products.flush_recordset()
        self.env.cr.execute(
            "SELECT id FROM product_product WHERE id IN %s ORDER BY id FOR UPDATE",
            (tuple(products.ids),),
        )
        products.sudo().write({"ab_cart_hold_revision": secrets.token_hex(16)})
        products.flush_recordset(["ab_cart_hold_revision"])

    def _ab_cart_held_quantity(self, website, warehouse, exclude_order=None):
        self.ensure_one()
        if not exclude_order and request:
            cart = request.cart
            if cart and cart.website_id == website and cart.company_id == website.company_id:
                exclude_order = cart
        return self.env["ab_storefront_cart_hold"]._quantities(
            self, website.company_id, warehouse, exclude_order,
        ).get(self.id, 0.0)

    def _get_ab_website_available_qty(self):
        quantity = super()._get_ab_website_available_qty()
        if quantity is None:
            return quantity
        website = self.env["website"].get_current_website()
        warehouse = self.env["stock.warehouse"].sudo().browse(
            self.env.context.get("warehouse_id") or website._ab_storefront_stock_warehouse_id()
        ).exists()
        excluded = self.env["sale.order"].browse(self.env.context.get("ab_cart_hold_order_id"))
        return max(quantity - self._ab_cart_held_quantity(website, warehouse, excluded), 0.0)


class Website(models.Model):
    _inherit = "website"

    def _get_product_available_qty(self, product, **kwargs):
        quantity = super()._get_product_available_qty(product, **kwargs)
        if product._ab_website_uses_eplus_stock() or not product.is_storable:
            return quantity
        warehouse = self.env["stock.warehouse"].sudo().browse(
            self._ab_storefront_stock_warehouse_id()
        ).exists()
        if not warehouse or warehouse.company_id != self.company_id:
            return 0.0
        quantity = product.sudo().with_company(self.company_id).with_context(
            warehouse_id=warehouse.id,
        ).free_qty
        return max(quantity - product._ab_cart_held_quantity(self, warehouse), 0.0)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    ab_cart_hold_expires_at = fields.Datetime(string="Website Hold Expires At", copy=False, readonly=True)
    ab_cart_operation_revision = fields.Char(string="Cart Operation Revision", copy=False, groups="base.group_system")

    def _ab_lock_cart(self):
        self.check_access("write")
        self.flush_recordset()
        self.env.cr.execute(
            "SELECT id FROM sale_order WHERE id IN %s ORDER BY id FOR UPDATE",
            (tuple(self.ids),),
        )
        self.sudo().write({"ab_cart_operation_revision": secrets.token_hex(16)})
        self.flush_recordset(["ab_cart_operation_revision"])
        self.invalidate_recordset()

    def _ab_cart_stock_products(self):
        return self.order_line.filtered(
            lambda line: not line.display_type and not line.is_delivery
            and line.product_id.is_storable
        ).product_id

    def _ab_prepare_cart_hold(self, extra_products=None):
        self.ensure_one()
        self._ab_lock_cart()
        if self.state != "draft":
            raise UserError(self.env._("This cart can no longer be changed."))
        if self.transaction_ids.filtered(lambda tx: tx.state in ("draft", "pending", "authorized", "done")):
            raise UserError(self.env._("This order is already being processed."))
        products = self._ab_cart_stock_products() | (extra_products or self.env["product.product"])
        products._ab_lock_cart_stock()
        return products

    def _ab_sync_cart_hold(self):
        self.ensure_one()
        warehouse = self.warehouse_id
        if not warehouse or warehouse.company_id != self.company_id:
            raise ValidationError(self.env._("The cart warehouse does not belong to this company."))
        now = fields.Datetime.now()
        deadline = self.ab_cart_hold_expires_at
        if not deadline or deadline <= now:
            deadline = now + timedelta(minutes=15)
        products = self._ab_cart_stock_products()
        products._ab_lock_cart_stock()
        quantities = {product.id: self._get_cart_qty(product.id) for product in products}
        for product in products:
            if float_compare(
                quantities[product.id], self._get_free_qty(product),
                precision_rounding=product.uom_id.rounding,
            ) > 0:
                raise UserError(self.env._("Some items are no longer available. Please review your cart."))
        holds = self.env["ab_storefront_cart_hold"].sudo()
        existing = holds.search(fields.Domain("order_id", "=", self.id))
        by_product = {hold.product_id.id: hold for hold in existing}
        values_to_create = []
        for product in products:
            values = {
                "order_id": self.id, "product_id": product.id, "company_id": self.company_id.id,
                "warehouse_id": warehouse.id, "quantity": quantities[product.id],
                "expires_at": deadline,
            }
            if product.id in by_product:
                by_product[product.id].write(values)
            else:
                values_to_create.append(values)
        if values_to_create:
            holds.create(values_to_create)
        existing.filtered(lambda hold: hold.product_id not in products).write({"quantity": 0})
        self.sudo().write({"ab_cart_hold_expires_at": deadline if products else False})

    def _get_free_qty(self, product):
        if not self.website_id or not product.is_storable:
            return super()._get_free_qty(product)
        scoped_product = product.with_context(ab_cart_hold_order_id=self.id)
        quantity = super()._get_free_qty(scoped_product)
        if product._ab_website_uses_eplus_stock():
            return quantity
        quantity = product.sudo().with_company(self.company_id).with_context(
            warehouse_id=self.warehouse_id.id,
        ).free_qty
        return max(quantity - product._ab_cart_held_quantity(
            self.website_id, self.warehouse_id, self,
        ), 0.0)

    def _cart_add(self, product_id, quantity=1.0, *, uom_id=None, **kwargs):
        if self.website_id:
            self._ab_prepare_cart_hold(self.env["product.product"].browse(product_id).exists())
        result = super()._cart_add(product_id, quantity=quantity, uom_id=uom_id, **kwargs)
        if self.website_id:
            self._ab_sync_cart_hold()
        return result

    def _cart_update_line_quantity(self, line_id, quantity, **kwargs):
        if self.website_id:
            self._ab_prepare_cart_hold()
        result = super()._cart_update_line_quantity(line_id, quantity, **kwargs)
        if self.website_id:
            self._ab_sync_cart_hold()
        return result

    def _ab_require_authoritative_reservation(self):
        self.ensure_one()
        if self.order_line.product_id.filtered(lambda product: product._ab_website_uses_eplus_stock()):
            raise UserError(self.env._(
                "Stock reservation is temporarily unavailable. Your order has not been confirmed. Please try again later."
            ))

    def write(self, vals):
        if vals.get("state") == "sale":
            for order in self.filtered(lambda current: current.website_id and current.state != "sale"):
                order.check_access("write")
                if self.env.context.get("ab_confirmation_token") is not _CONFIRMATION_TOKEN:
                    raise UserError(self.env._("Use Confirm to reserve all items before confirming this order."))
                order._ab_require_authoritative_reservation()
        return super().write(vals)

    @api.constrains("state")
    def _check_website_confirmation(self):
        if self.env.context.get("ab_confirmation_token") is not _CONFIRMATION_TOKEN:
            if self.filtered(lambda order: order.website_id and order.state == "sale"):
                raise ValidationError(self.env._("Use Confirm to reserve all items before confirming this order."))

    def _check_cart_is_ready_to_be_paid(self):
        if self.website_id:
            self._ab_lock_cart()
            self._ab_cart_stock_products()._ab_lock_cart_stock()
            self._ab_require_authoritative_reservation()
            self._ab_sync_cart_hold()
        return super()._check_cart_is_ready_to_be_paid()

    def action_confirm(self):
        website_orders = self.filtered(lambda order: order.website_id and order.state in ("draft", "sent"))
        for order in website_orders.sorted("id"):
            order._ab_lock_cart()
            order._ab_cart_stock_products()._ab_lock_cart_stock()
            order._ab_require_authoritative_reservation()
            order._ab_sync_cart_hold()
        result = super(SaleOrder, self.with_context(ab_confirmation_token=_CONFIRMATION_TOKEN)).action_confirm()
        for order in website_orders:
            moves = order.picking_ids.move_ids.filtered(
                lambda move: move.product_id.is_storable and move.state not in ("done", "cancel")
            )
            moves._action_assign()
            if any(move.state != "assigned" for move in moves):
                raise UserError(self.env._("All items must be reserved before this order can be confirmed."))
        return result
