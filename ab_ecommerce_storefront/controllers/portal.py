import secrets
import time

from odoo import fields
from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.exceptions import AccessError
from odoo.http import request, route

from .auth import is_valid_egyptian_mobile, normalize_egyptian_phone


class AbStorefrontCustomerPortal(CustomerPortal):
    def _ab_storefront_verify_order(self, order_reference, phone):
        normalized_phone = normalize_egyptian_phone(phone)
        reference = (order_reference or "").strip()
        if not reference or len(reference) > 128 or not normalized_phone.isascii() or not is_valid_egyptian_mobile(normalized_phone):
            return request.env["sale.order"].sudo().browse()

        domain = (
            fields.Domain("website_id", "=", request.website.id)
            & fields.Domain("company_id", "=", request.website.company_id.id)
            & (fields.Domain("name", "=", reference) | fields.Domain("client_order_ref", "=", reference))
        )
        orders = request.env["sale.order"].sudo().search(domain, limit=2)
        if len(orders) != 1:
            return request.env["sale.order"].browse()
        order = orders

        partners = order.partner_id | order.partner_invoice_id | order.partner_shipping_id
        partner_phones = set()
        for partner in partners:
            for field_name in ("phone", "mobile"):
                if field_name in partner._fields:
                    partner_phones.add(normalize_egyptian_phone(partner[field_name]))
        return order if any(
            secrets.compare_digest(normalized_phone, phone) for phone in partner_phones if phone
        ) else request.env["sale.order"].browse()

    def _ab_storefront_verify_prescription(self, reference, phone):
        normalized = normalize_egyptian_phone(phone)
        if not normalized.isascii() or not is_valid_egyptian_mobile(normalized):
            return request.env["ab.prescription.order"].browse()
        prescriptions = request.env["ab.prescription.order"].sudo().search(
            fields.Domain("name", "=", (reference or "").strip())
            & fields.Domain("website_id", "=", request.website.id)
            & fields.Domain("company_id", "=", request.website.company_id.id),
            limit=2,
        )
        if len(prescriptions) == 1 and secrets.compare_digest(
            normalized, normalize_egyptian_phone(prescriptions.partner_id.phone)
        ):
            return prescriptions
        return request.env["ab.prescription.order"].browse()

    @route(["/my", "/my/home"], type="http", auth="user", website=True)
    def home(self, **kw):
        values = self._prepare_portal_layout_values()
        values.update(self._prepare_home_portal_values([]))
        return request.render("portal.portal_my_home", values)

    @route("/track-order", type="http", auth="public", website=True, methods=["GET", "POST"], sitemap=True)
    def ab_storefront_track_order(self, **post):
        values = {
            "error_code": False,
            "order_reference": post.get("order_reference", ""),
            "phone": post.get("phone", ""),
        }
        if request.httprequest.method == "POST":
            attempts, started = request.session.get("ab_tracking_attempts", (0, 0))
            now = time.time()
            if now - started > 900:
                attempts, started = 0, now
            request.session["ab_tracking_attempts"] = (attempts + 1, started)
            if attempts < 10:
                order = self._ab_storefront_verify_order(post.get("order_reference"), post.get("phone"))
                if not order:
                    order = self._ab_storefront_verify_prescription(post.get("order_reference"), post.get("phone"))
                if order:
                    response = request.redirect(order.get_portal_url())
                    response.headers["Cache-Control"] = "private, no-store"
                    response.headers["Referrer-Policy"] = "no-referrer"
                    return response
            values["error_code"] = "not_found"
        response = request.render("ab_ecommerce_storefront.guest_order_tracking", values)
        response.headers["Cache-Control"] = "private, no-store"
        return response

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        user = request.env.user
        partner = user.partner_id
        partner_mobile = partner.mobile if "mobile" in partner._fields else False
        account_phone = partner.phone or partner_mobile or user.login
        account_avatar = partner.ab_storefront_avatar or "avatar_none"
        avatar_complete = partner.ab_storefront_avatar_completed or account_avatar != "avatar_none"
        has_address = bool(partner.street or partner.city or partner.country_id)
        profile_completion = (
            (25 if partner.name else 0)
            + (25 if account_phone else 0)
            + (25 if avatar_complete else 0)
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

        recent_prescriptions = request.env["ab.prescription.order"]
        prescription_count = 0
        try:
            PrescriptionOrder = request.env["ab.prescription.order"]
            prescription_domain = [("partner_id", "child_of", [partner.commercial_partner_id.id])]
            prescription_count = PrescriptionOrder.search_count(prescription_domain)
            recent_prescriptions = PrescriptionOrder.search(
                prescription_domain,
                order="create_date desc, id desc",
                limit=3,
            )
        except AccessError:
            recent_prescriptions = request.env["ab.prescription.order"]
            prescription_count = 0

        values.update({
            "account_user": user,
            "account_partner": partner,
            "account_phone": account_phone,
            "account_avatar": account_avatar,
            "avatar_complete": avatar_complete,
            "has_address": has_address,
            "profile_completion": profile_completion,
            "profile_completion_style": f"--ab-profile-completion: {profile_completion}%",
            "recent_orders": recent_orders,
            "recent_prescriptions": recent_prescriptions,
            "prescription_count": prescription_count,
            "saved_addresses": saved_addresses,
            "wishlist_count": wishlist_count,
        })
        return values
