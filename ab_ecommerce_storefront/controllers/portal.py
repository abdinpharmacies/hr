from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.exceptions import AccessError
from odoo.http import request, route


class AbStorefrontCustomerPortal(CustomerPortal):
    @route(["/my", "/my/home"], type="http", auth="user", website=True)
    def home(self, **kw):
        values = self._prepare_portal_layout_values()
        values.update(self._prepare_home_portal_values([]))
        return request.render("portal.portal_my_home", values)

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        user = request.env.user
        partner = user.partner_id
        partner_mobile = partner.mobile if "mobile" in partner._fields else False
        account_phone = partner.phone or partner_mobile or user.login
        account_avatar = partner.ab_storefront_avatar or "avatar_none"
        has_address = bool(partner.street or partner.city or partner.country_id)
        profile_completion = (
            (25 if partner.name else 0)
            + (25 if account_phone else 0)
            + (25 if account_avatar != "avatar_none" else 0)
            + (25 if has_address else 0)
        )

        recent_orders = request.env["sale.order"]
        try:
            SaleOrder = request.env["sale.order"]
            if SaleOrder.has_access("read"):
                recent_orders = SaleOrder.search([
                    ("partner_id", "child_of", [partner.commercial_partner_id.id]),
                    ("state", "=", "sale"),
                ], order="date_order desc", limit=3)
        except AccessError:
            recent_orders = request.env["sale.order"]

        saved_addresses = partner.child_ids.filtered(lambda address: address.type in ("delivery", "other"))[:2]

        wishlist_count = 0
        try:
            wishlist_count = len(request.env["product.wishlist"].current())
        except AccessError:
            wishlist_count = 0

        values.update({
            "account_user": user,
            "account_partner": partner,
            "account_phone": account_phone,
            "account_avatar": account_avatar,
            "has_address": has_address,
            "profile_completion": profile_completion,
            "profile_completion_style": f"--ab-profile-completion: {profile_completion}%",
            "recent_orders": recent_orders,
            "saved_addresses": saved_addresses,
            "wishlist_count": wishlist_count,
        })
        return values
