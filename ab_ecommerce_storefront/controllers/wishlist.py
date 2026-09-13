from odoo.http import Controller, request, route


class AbStorefrontWishlist(Controller):
    @route(
        "/ab/storefront/wishlist/remove_product",
        type="jsonrpc",
        auth="public",
        website=True,
    )
    def remove_product_from_wishlist(self, product_id, **kwargs):
        product_id = int(product_id or 0)
        if not product_id:
            return {"removed": False, "product_ids": []}

        wishes = request.env["product.wishlist"].current().filtered(
            lambda item: item.product_id.id == product_id
        )
        if wishes:
            if request.website.is_public_user():
                wishlist_ids = request.session.get("wishlist_ids") or []
                request.session["wishlist_ids"] = [
                    wish_id for wish_id in wishlist_ids if wish_id not in wishes.ids
                ]
                if len(request.session["wishlist_ids"]) != len(wishlist_ids):
                    request.session.touch()
                wishes.sudo().unlink()
            else:
                wishes.unlink()

        product_ids = request.env["product.wishlist"].current().product_id.ids
        return {
            "removed": bool(wishes),
            "product_ids": product_ids,
        }
