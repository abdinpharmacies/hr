import base64
import hashlib
import secrets

from lxml import html

from odoo import fields, http
from odoo.exceptions import AccessDenied
from odoo.http import request
from odoo.tools import email_normalize
from odoo.addons.ab_ecommerce_storefront.controllers.auth import validate_storefront_password
from odoo.addons.ab_ecommerce_storefront.controllers.checkout_submission import StorefrontPaymentPortal, checkout_submission
from odoo.addons.ab_ecommerce_storefront.controllers.prescription_order import AbPrescriptionOrderPortal
from odoo.addons.ab_ecommerce_storefront.controllers.submission_security import submission_owner

from .common import ApiError, body, endpoint, respond, schema


ID = schema("integer", minimum=1)
TEXT = schema(maxLength=256)
SECRET = schema(minLength=1, maxLength=256)
PAGE = {"page": schema("integer", minimum=1, maximum=1000, default=1),
        "limit": schema("integer", minimum=1, maximum=50, default=20)}
ADDRESS = body({"name": TEXT, "phone": TEXT, "street": TEXT, "street2": TEXT,
                "city": TEXT, "zip": TEXT, "country_id": ID, "state_id": ID},
               ("name", "phone", "street", "city", "country_id", "state_id"))


class EcommerceApi(http.Controller):
    def _service(self):
        return request.env["ab_storefront_auth_service"]

    def _tokens(self, user, device=""):
        session, tokens = request.env["ab_ecommerce_api_session"]._issue(user, request.website, device)
        tokens["user"] = {"id": user.id, "name": user.name}
        return tokens

    def _session_data(self, sessions):
        current = request.ab_api_session
        return [{
            "id": session._public_id(),
            "device_name": session.device_name or "",
            "current": session == current,
            "created_at": session.create_date.isoformat() + "Z",
            "last_used_at": session.last_used_at.isoformat() + "Z" if session.last_used_at else None,
            "last_refreshed_at": session.last_refreshed_at.isoformat() + "Z" if session.last_refreshed_at else None,
            "refresh_expires_at": session.refresh_expires_at.isoformat() + "Z",
        } for session in sessions]

    @endpoint("/auth/browser/start", "POST", tag="Authentication", summary="Start browser sign-in with PKCE for Google or MFA", authenticated=False,
              payload=body({"code_challenge": schema(minLength=43, maxLength=43)}, ("code_challenge",)))
    def browser_start(self):
        token = request.env["ab_ecommerce_api_browser_grant"]._start(request.ab_api_data["code_challenge"], request.website)
        return {"flow_token": token, "authorization_url": f"/api/v1/auth/browser/authorize/{token}",
                "expires_in": 300, "poll_interval": 10}

    @endpoint("/auth/browser/token", "POST", tag="Authentication", summary="Exchange an approved browser flow using the PKCE verifier", authenticated=False,
              payload=body({"flow_token": SECRET, "code_verifier": schema(minLength=43, maxLength=128)}, ("flow_token", "code_verifier")))
    def browser_token(self):
        data = request.ab_api_data
        return request.env["ab_ecommerce_api_browser_grant"]._exchange(data["flow_token"], data["code_verifier"], request.website)

    def _page(self, model, domain, serialize, order="id desc"):
        query = request.ab_api_query
        limit, page = query.get("limit", 20), query.get("page", 1)
        records = model.search(domain, limit=limit + 1, offset=(page - 1) * limit, order=order)
        return {"items": serialize(records[:limit]), "page": page,
                "limit": limit, "has_more": len(records) > limit}

    def _product_domain(self):
        return (request.website.sale_product_domain()
                & fields.Domain("active", "=", True)
                & fields.Domain("company_id", "in", [False, request.website.company_id.id]))

    def _product(self, product_id):
        product = request.env["product.template"].search(
            self._product_domain() & fields.Domain("id", "=", product_id), limit=1)
        if not product:
            raise ApiError("not_found", 404)
        return product

    def _variant(self, product_id):
        product = request.env["product.product"].search([
            ("id", "=", product_id), ("active", "=", True)], limit=1)
        if not product:
            raise ApiError("not_found", 404)
        self._product(product.product_tmpl_id.id)
        if not product.product_tmpl_id._is_combination_possible(product.product_template_attribute_value_ids):
            raise ApiError("invalid_input")
        return product

    def _products(self, products):
        prices = products._get_sales_prices(request.website)
        return [{"id": product.id, "name": product.name,
                 "description": product.description_sale or "",
                 "price": prices[product.id]["price_reduce"],
                 "original_price": prices[product.id].get("base_price"),
                 "currency": request.pricelist.currency_id.name,
                 "image_url": f"/api/v1/products/{product.id}/image",
                 "variant_ids": product.product_variant_ids.ids,
                 "category_ids": product.public_categ_ids.ids}
                for product in products]

    def _owner_domain(self):
        owner = request.env.user.partner_id
        return ((fields.Domain("partner_id", "=", owner.id)
                 | fields.Domain("partner_id.parent_id", "=", owner.id))
                & fields.Domain("website_id", "=", request.website.id)
                & fields.Domain("company_id", "=", request.website.company_id.id))

    def _order(self, order_id):
        order = request.env["sale.order"].sudo().search(
            self._owner_domain() & fields.Domain("id", "=", order_id), limit=1)
        if not order:
            raise ApiError("not_found", 404)
        return order

    def _cart(self, create=False, mutable=False):
        session = request.ab_api_session
        if create or mutable:
            session = session.try_lock_for_update(allow_referencing=True)
            if not session:
                raise ApiError("conflict", 409)
            session.invalidate_recordset()
        cart = session.cart_id
        if cart:
            cart = self._order(cart.id)
            if cart.state != "draft":
                if mutable and not create:
                    raise ApiError("conflict", 409)
                cart = request.env["sale.order"]
        if not cart and create:
            cart = request.website._create_cart()
            session.write({"cart_id": cart.id})
        request.cart = cart
        if cart:
            request.session["sale_order_id"] = cart.id
            request.pricelist = cart.pricelist_id
            request.fiscal_position = cart.fiscal_position_id
            if mutable:
                cart._ab_prepare_cart_hold()
        return cart

    def _order_data(self, order):
        if not order:
            return {"id": None, "lines": [], "total": 0}
        return {"id": order.id, "reference": order.ab_public_reference or order.name,
                "state": order.state, "currency": order.currency_id.name,
                "untaxed": order.amount_untaxed, "tax": order.amount_tax,
                "total": order.amount_total, "shipping_address_id": order.partner_shipping_id.id,
                "delivery_method_id": order.carrier_id.id or None,
                "hold_expires_at": order.ab_cart_hold_expires_at.isoformat() + "Z" if order.ab_cart_hold_expires_at else None,
                "lines": [{"id": line.id, "product_id": line.product_id.id,
                           "name": line.name, "quantity": line.product_uom_qty,
                           "unit_price": line.price_unit, "discount": line.discount,
                           "subtotal": line.price_subtotal, "total": line.price_total,
                           "is_delivery": line.is_delivery, "is_reward": line.is_reward_line}
                          for line in order.order_line if not line.display_type]}

    def _address(self, address_id):
        partner = request.env.user.partner_id
        address = request.env["res.partner"].sudo().search([
            ("id", "=", address_id), ("active", "=", True),
            ("company_id", "in", [False, request.website.company_id.id]),
            "|", ("id", "=", partner.id),
            "&", ("parent_id", "=", partner.id), ("type", "in", ["delivery", "invoice", "other"]),
        ], limit=1)
        if not address:
            raise ApiError("not_found", 404)
        return address

    def _address_data(self, addresses):
        return [{"id": address.id, "name": address.name, "phone": address.phone or "",
                 "street": address.street or "", "street2": address.street2 or "",
                 "city": address.city or "", "zip": address.zip or "",
                 "country_id": address.country_id.id or None,
                 "state_id": address.state_id.id or None} for address in addresses]

    def _address_values(self):
        values = dict(request.ab_api_data)
        country = request.env["res.country"].browse(values["country_id"]).exists()
        state = request.env["res.country.state"].browse(values["state_id"]).exists()
        if not country or not state or state.country_id != country:
            raise ApiError("invalid_input")
        if any(not values[name].strip() for name in ("name", "phone", "street", "city")):
            raise ApiError("invalid_input")
        return values

    @endpoint("/auth/login", "POST", tag="Authentication", summary="Sign in with email or verified phone", authenticated=False,
              payload=body({"login": SECRET, "password": SECRET, "device_name": TEXT}, ("login", "password")))
    def login(self):
        data = request.ab_api_data
        info = request.env["res.users"].authenticate(
            {"type": "password", "login": data["login"], "password": data["password"]},
            {"interactive": True, "REMOTE_ADDR": request.httprequest.remote_addr})
        user = request.env["res.users"].sudo().browse(info["uid"])
        request.env["ab_ecommerce_api_session"]._assert_customer(user, request.website)
        if user._mfa_url():
            if user._mfa_url() != "/ab_storefront/auth/device":
                raise ApiError("mfa_required", 403)
            token = request.session.get("ab_device_token")
            browser = request.session.get("ab_device_browser")
            if not token:
                browser = secrets.token_urlsafe(32)
                token = self._service()._new_device_login(user, browser, request.httprequest.remote_addr, data.get("device_name", "Mobile"))
            return {"verification_required": True, "challenge_token": token, "browser_token": browser}
        return self._tokens(user, data.get("device_name", ""))

    @endpoint("/auth/verify-device", "POST", tag="Authentication", summary="Complete Telegram device approval", authenticated=False,
              payload=body({"challenge_token": SECRET, "browser_token": SECRET, "recovery_code": SECRET}, ("challenge_token", "browser_token")))
    def verify_device(self):
        data = request.ab_api_data
        challenge = self._service()._find(data["challenge_token"], ["device_login"], data["browser_token"])
        if not challenge:
            raise AccessDenied()
        user = challenge.user_id
        if not self._service()._complete_device_login(user, data["challenge_token"], data["browser_token"], data.get("recovery_code")):
            return {"verification_required": True}
        return self._tokens(user)

    @endpoint("/auth/refresh", "POST", tag="Authentication", summary="Rotate access and refresh tokens", authenticated=False,
              payload=body({"refresh_token": SECRET}, ("refresh_token",)))
    def refresh(self):
        tokens = request.env["ab_ecommerce_api_session"]._rotate(
            request.ab_api_data["refresh_token"], request.website,
        )
        if not tokens:
            return respond(code="unauthorized", status=401)
        return tokens

    @endpoint("/auth/logout", "POST", tag="Authentication", summary="Revoke this device session", payload=body({}))
    def logout(self):
        request.ab_api_session._revoke("logout")
        return {"revoked": True}

    @endpoint("/auth/sessions", tag="Authentication", summary="List signed-in device sessions")
    def sessions(self):
        sessions = request.env["ab_ecommerce_api_session"].sudo().search([
            ("user_id", "=", request.env.uid),
            ("website_id", "=", request.website.id),
            ("company_id", "=", request.website.company_id.id),
            ("revoked", "=", False),
            ("refresh_expires_at", ">", fields.Datetime.now()),
        ], order="create_date desc")
        return self._session_data(sessions)

    @endpoint("/auth/sessions/<string:session_id>", "DELETE", tag="Authentication",
              summary="Revoke an owned device session")
    def revoke_session(self, session_id):
        session = request.env["ab_ecommerce_api_session"]._from_public_id(session_id)
        if (not session or session.user_id.id != request.env.uid
                or session.website_id != request.website
                or session.company_id != request.website.company_id or session.revoked):
            raise ApiError("not_found", 404)
        session._revoke("device_revoked")
        return {"revoked": True}

    @endpoint("/auth/logout-all", "POST", tag="Authentication",
              summary="Revoke all device sessions", payload=body({}))
    def logout_all(self):
        sessions = request.env["ab_ecommerce_api_session"].sudo().search([
            ("user_id", "=", request.env.uid),
            ("website_id", "=", request.website.id),
            ("company_id", "=", request.website.company_id.id),
            ("revoked", "=", False),
        ])
        count = len(sessions)
        sessions._revoke("logout_all")
        return {"revoked": count}

    @endpoint("/auth/register", "POST", tag="Authentication", summary="Register an email customer account", authenticated=False,
              payload=body({"name": TEXT, "email": TEXT, "password": SECRET}, ("name", "email", "password")), status=201)
    def register(self):
        data = request.ab_api_data
        email = email_normalize(data["email"])
        if not email or not data["name"].strip() or not validate_storefront_password(data["password"]):
            raise ApiError("invalid_input")
        users = request.env["res.users"]
        if users._get_signup_invitation_scope() != "b2c":
            raise ApiError("forbidden", 403)
        login, password = users.sudo().signup({"login": email, "email": email,
                                             "name": data["name"], "password": data["password"]})
        user = users.sudo().search([("login", "=", login)], limit=1)
        request.env["ab_ecommerce_api_session"]._assert_customer(user, request.website)
        self._service()._request_email_verification(user, email, "", request.httprequest.remote_addr)
        return self._tokens(user)

    @endpoint("/auth/phone/start", "POST", tag="Authentication", summary="Start verified phone registration", authenticated=False,
              payload=body({"phone": TEXT}, ("phone",)))
    def phone_start(self):
        browser = secrets.token_urlsafe(32)
        token, url = self._service()._request_link(None, request.ab_api_data["phone"], browser, request.httprequest.remote_addr)
        return {"challenge_token": token, "browser_token": browser, "verification_url": url}

    @endpoint("/auth/phone/complete", "POST", tag="Authentication", summary="Complete verified phone registration", authenticated=False,
              payload=body({"challenge_token": SECRET, "browser_token": SECRET, "name": TEXT, "password": SECRET},
                           ("challenge_token", "browser_token", "name", "password")), status=201)
    def phone_complete(self):
        data = request.ab_api_data
        if not data["name"].strip() or not validate_storefront_password(data["password"]):
            raise ApiError("invalid_input")
        user = self._service()._finish_phone_signup(data["challenge_token"], data["browser_token"],
                                                   {"name": data["name"], "password": data["password"]})
        return self._tokens(user)

    @endpoint("/auth/recovery", "POST", tag="Authentication", summary="Request account recovery without revealing account existence", authenticated=False,
              payload=body({"channel": schema(enum=["email", "telegram"]), "identifier": TEXT}, ("channel", "identifier")))
    def recovery(self):
        data = request.ab_api_data
        browser = secrets.token_urlsafe(32)
        token = self._service()._request_recovery(data["channel"], data["identifier"], browser, request.httprequest.remote_addr)
        return {"accepted": True, "challenge_token": token or secrets.token_urlsafe(32), "browser_token": browser}

    @endpoint("/auth/recovery/verify", "POST", tag="Authentication", summary="Verify a recovery code or emailed token", authenticated=False,
              payload=body({"challenge_token": SECRET, "browser_token": SECRET, "code": TEXT}, ("challenge_token", "browser_token")))
    def recovery_verify(self):
        data = request.ab_api_data
        grant = self._service()._verify_recovery(data["challenge_token"], data["browser_token"], data.get("code"))
        return {"verified": bool(grant), "grant_token": grant or None}

    @endpoint("/auth/recovery/reset", "POST", tag="Authentication", summary="Reset password and invalidate existing API sessions", authenticated=False,
              payload=body({"grant_token": SECRET, "browser_token": SECRET, "password": SECRET}, ("grant_token", "browser_token", "password")))
    def recovery_reset(self):
        data = request.ab_api_data
        if not validate_storefront_password(data["password"]):
            raise ApiError("invalid_input")
        if not self._service()._reset_password(data["grant_token"], data["browser_token"], data["password"]):
            raise AccessDenied()
        return {"reset": True}

    @endpoint("/auth/email/confirm", "POST", tag="Authentication", summary="Confirm an emailed verification token", authenticated=False,
              payload=body({"token": SECRET}, ("token",)))
    def email_confirm(self):
        if not self._service()._confirm_email(request.ab_api_data["token"]):
            raise AccessDenied()
        return {"verified": True}

    @endpoint("/config", tag="Catalog", summary="Store settings and API capabilities", authenticated=False)
    def config(self):
        return {"name": request.website.name, "currency": request.pricelist.currency_id.name,
                "languages": [code for code, name in request.env["res.lang"].get_installed()],
                "version": "1", "authentication": "Bearer", "guest_browsing": True,
                "checkout_requires_login": True, "signup_url": "/web/signup",
                "account_security_url": "/my/authentication", "google_login_url": "/web/login"}

    @endpoint("/products", tag="Catalog", summary="Search published products", authenticated=False,
              query=dict(PAGE, search=schema(maxLength=100), category_id=ID, brand_id=ID,
                         sort=schema(enum=["name", "newest"], default="name")))
    def products(self):
        query = request.ab_api_query
        domain = self._product_domain()
        if query.get("search"):
            domain &= fields.Domain("name", "ilike", query["search"])
        if query.get("category_id"):
            domain &= fields.Domain("public_categ_ids", "child_of", query["category_id"])
        if query.get("brand_id"):
            domain &= fields.Domain("ab_storefront_brand_id", "=", query["brand_id"])
        return self._page(request.env["product.template"], domain, self._products,
                          "name, id" if query["sort"] == "name" else "id desc")

    @endpoint("/products/<int:product_id>", tag="Catalog", summary="Product details, variants and availability", authenticated=False)
    def product(self, product_id):
        product = self._product(product_id)
        result = self._products(product)[0]
        result["description_html"] = str(product.description_ecommerce or "")
        result["variants"] = []
        for variant in product.product_variant_ids:
            combination = variant.product_template_attribute_value_ids
            if not product._is_combination_possible(combination):
                continue
            info = product._get_combination_info(combination=combination, product_id=variant.id, add_qty=1)
            result["variants"].append({"id": variant.id, "name": variant.display_name,
                                       "price": info["price"],
                                       "available_quantity": request.website.sudo()._get_product_available_qty(variant.sudo()) if variant.is_storable else None,
                                       "attributes": combination.mapped("name")})
        return result

    @endpoint("/products/<int:product_id>/image", tag="Catalog", summary="Published product image", authenticated=False)
    def product_image(self, product_id):
        product = self._product(product_id)
        return request.env["ir.binary"]._get_stream_from(product, "image_512").get_response()

    @endpoint("/categories", tag="Catalog", summary="Public category tree", authenticated=False)
    def categories(self):
        categories = request.env["product.public.category"].search(
            request.website.website_domain(), order="sequence, id", limit=500)
        return [{"id": item.id, "name": item.name, "parent_id": item.parent_id.id or None} for item in categories]

    @endpoint("/offers", tag="Catalog", summary="Current storefront offers", authenticated=False, query=PAGE)
    def offers(self):
        page, limit = request.ab_api_query["page"], request.ab_api_query["limit"]
        products, prices, more = request.website._ab_storefront_offer_catalog(limit, (page - 1) * limit)
        return {"items": self._products(products), "page": page, "limit": limit, "has_more": more}

    @endpoint("/brands", tag="Catalog", summary="Brands of published store products", authenticated=False)
    def brands(self):
        groups = request.env["product.template"]._read_group(
            self._product_domain() & fields.Domain("ab_storefront_brand_id", "!=", False),
            ["ab_storefront_brand_id"], ["__count"])
        return [{"id": brand.id, "name": brand.sudo().name, "product_count": count} for brand, count in groups]

    @endpoint("/home", tag="Catalog", summary="Homepage products, offers and banners", authenticated=False)
    def home(self):
        catalog = request.website._ab_storefront_home_catalog()
        slides = request.env["ab_website_carousel_slide"].sudo().search(
            request.website.website_domain() & fields.Domain("active", "=", True), limit=20)
        return {"best_sellers": self._products(catalog["best_sellers"]),
                "offers": self._products(catalog["offers"]),
                "categories": [{"id": c.id, "name": c.name} for c in catalog["categories"]],
                "banners": [{"id": s.id, "title": s.title or "", "subtitle": s.subtitle or "",
                             "image_url": f"/api/v1/banners/{s.id}/image",
                             "link": s.cta_url or "", "button_text": s.cta_text or ""} for s in slides]}

    @endpoint("/banners/<int:banner_id>/image", tag="Catalog", summary="Published homepage banner image", authenticated=False)
    def banner_image(self, banner_id):
        slide = request.env["ab_website_carousel_slide"].sudo().search(
            request.website.website_domain() & fields.Domain("active", "=", True)
            & fields.Domain("id", "=", banner_id), limit=1)
        if not slide:
            raise ApiError("not_found", 404)
        return request.env["ir.binary"]._get_stream_from(slide, "image_1920").get_response()

    @endpoint("/me", tag="Account", summary="Current customer profile")
    def me(self):
        partner = request.env.user.partner_id
        return {"id": request.env.uid, "name": partner.name, "email": partner.email or "",
                "phone": partner.phone or "", "avatar": partner.ab_storefront_avatar}

    @endpoint("/me", "PATCH", tag="Account", summary="Update customer name and avatar", payload=body({"name": TEXT,
              "avatar": schema(enum=["avatar_none"] + [f"avatar_{i:02d}" for i in range(1, 13)])}))
    def update_me(self):
        data = request.ab_api_data
        values = {}
        if "name" in data:
            if not data["name"].strip():
                raise ApiError("invalid_input")
            values["name"] = data["name"].strip()
        if "avatar" in data:
            values.update(ab_storefront_avatar=data["avatar"], ab_storefront_avatar_completed=True)
        request.env.user.partner_id.sudo().write(values)
        return {"updated": True}

    @endpoint("/addresses", tag="Account", summary="List customer delivery addresses")
    def addresses(self):
        partner = request.env.user.partner_id
        children = request.env["res.partner"].sudo().search([
            ("parent_id", "=", partner.id), ("type", "in", ["delivery", "invoice", "other"]),
            ("company_id", "in", [False, request.website.company_id.id])], limit=100)
        return self._address_data(partner | children)

    @endpoint("/addresses", "POST", tag="Account", summary="Create a customer delivery address", payload=ADDRESS, status=201)
    def add_address(self):
        values = self._address_values()
        values.update(parent_id=request.env.user.partner_id.id, type="delivery",
                      company_id=request.website.company_id.id)
        address = request.env["res.partner"].sudo().create(values)
        return self._address_data(address)[0]

    @endpoint("/addresses/<int:address_id>", "PUT", tag="Account", summary="Update an owned delivery address", payload=ADDRESS)
    def update_address(self, address_id):
        address = self._address(address_id)
        if address == request.env.user.partner_id:
            raise ApiError("forbidden", 403)
        address.write(self._address_values())
        return self._address_data(address)[0]

    @endpoint("/countries", tag="Account", summary="Countries for delivery addresses", authenticated=False)
    def countries(self):
        return [{"id": c.id, "name": c.name, "code": c.code} for c in request.env["res.country"].search([], order="name")]

    @endpoint("/countries/<int:country_id>/states", tag="Account", summary="States for a country", authenticated=False)
    def states(self, country_id):
        return [{"id": s.id, "name": s.name} for s in request.env["res.country.state"].search([("country_id", "=", country_id)], order="name")]

    @endpoint("/cart", tag="Cart", summary="Current device cart")
    def cart(self):
        return self._order_data(self._cart())

    @endpoint("/cart/items", "POST", tag="Cart", summary="Add a variant using server prices", payload=body({"product_id": ID,
              "quantity": schema("number", minimum=0.001, maximum=1000)}, ("product_id", "quantity")), idempotency=True)
    def add_cart_item(self):
        data = request.ab_api_data
        session = request.ab_api_session.try_lock_for_update(allow_referencing=True)
        if not session:
            raise ApiError("conflict", 409)
        session.invalidate_recordset()
        request.ab_api_session = session
        idempotency = request.env["ab_ecommerce_api_idempotency"]
        record, cached, conflict = idempotency._begin(
            request.ab_idempotency_key, "add_cart_item", session, data,
        )
        if conflict:
            raise ApiError("conflict", 409)
        if cached is not None:
            return cached
        product = self._variant(data["product_id"])
        cart = self._cart(create=True, mutable=True)
        cart._cart_add(product.id, data["quantity"])
        result = self._order_data(cart)
        record._complete(result)
        return result

    @endpoint("/cart/items/<int:line_id>", "PUT", tag="Cart", summary="Set an owned cart line quantity; zero removes it",
              payload=body({"quantity": schema("number", minimum=0, maximum=1000)}, ("quantity",)))
    def update_cart_item(self, line_id):
        cart = self._cart(mutable=True)
        line = cart.order_line.filtered(lambda item: item.id == line_id and not item.is_delivery and not item.is_reward_line)
        if not line:
            raise ApiError("not_found", 404)
        cart._cart_update_line_quantity(line.id, request.ab_api_data["quantity"])
        return self._order_data(cart)

    @endpoint("/cart/address", "PUT", tag="Checkout", summary="Choose an owned shipping address",
              payload=body({"address_id": ID}, ("address_id",)))
    def cart_address(self):
        address = self._address(request.ab_api_data["address_id"])
        cart = self._cart(create=True, mutable=True)
        cart._update_address(address.id, ["partner_shipping_id"])
        cart._recompute_cart()
        return self._order_data(cart)

    @endpoint("/cart/delivery-methods", tag="Checkout", summary="Available delivery methods and quoted rates")
    def delivery_methods(self):
        cart = self._cart()
        if not cart:
            raise ApiError("not_found", 404)
        result = []
        for carrier in cart._get_delivery_methods():
            rate = carrier.rate_shipment(cart)
            if rate.get("success"):
                result.append({"id": carrier.id, "name": carrier.name, "price": rate["price"], "currency": cart.currency_id.name})
        return result

    @endpoint("/cart/delivery-method", "PUT", tag="Checkout", summary="Select a compatible delivery method",
              payload=body({"delivery_method_id": ID}, ("delivery_method_id",)))
    def set_delivery(self):
        cart = self._cart(mutable=True)
        carrier = cart._get_delivery_methods().filtered(lambda item: item.id == request.ab_api_data["delivery_method_id"])
        if not carrier:
            raise ApiError("not_found", 404)
        rate = carrier.rate_shipment(cart)
        if not rate.get("success"):
            raise ApiError("business_rule", 422)
        cart._set_delivery_method(carrier, rate)
        return self._order_data(cart)

    @endpoint("/cart/coupon", "POST", tag="Cart", summary="Apply a coupon using Odoo promotion rules", payload=body({"code": TEXT}, ("code",)))
    def coupon(self):
        cart = self._cart(mutable=True)
        if not cart:
            raise ApiError("not_found", 404)
        result = cart._try_apply_code(request.ab_api_data["code"])
        if "error" in result:
            raise ApiError("business_rule", 422)
        if len(result) == 1:
            coupon, rewards = next(iter(result.items()))
            if len(rewards) == 1 and not rewards.multi_product:
                applied = cart._apply_program_reward(rewards, coupon)
                if "error" in applied:
                    raise ApiError("business_rule", 422)
        cart._update_programs_and_rewards()
        if cart.carrier_id:
            cart._set_delivery_method(cart.carrier_id)
        cart._ab_sync_cart_hold()
        return self._order_data(cart)

    @endpoint("/cart/rewards", tag="Cart", summary="List eligible rewards requiring a customer choice")
    def rewards(self):
        cart = self._cart()
        if not cart:
            return []
        return [{"coupon_id": coupon.id, "reward_id": reward.id, "description": reward.description,
                 "product_ids": reward.reward_product_ids.ids if reward.multi_product else []}
                for coupon, rewards in cart._get_claimable_and_showable_rewards().items() for reward in rewards]

    @endpoint("/cart/rewards", "POST", tag="Cart", summary="Claim a reward that is eligible for this cart",
              payload=body({"coupon_id": ID, "reward_id": ID, "product_id": ID}, ("coupon_id", "reward_id")))
    def claim_reward(self):
        cart = self._cart(mutable=True)
        if not cart:
            raise ApiError("not_found", 404)
        data = request.ab_api_data
        for coupon, rewards in cart._get_claimable_and_showable_rewards().items():
            reward = rewards.filtered(lambda item: item.id == data["reward_id"])
            if coupon.id != data["coupon_id"] or not reward:
                continue
            product = self._variant(data["product_id"]) if data.get("product_id") else None
            if reward.multi_product and (not product or product not in reward.reward_product_ids):
                raise ApiError("invalid_input")
            result = cart._apply_program_reward(reward, coupon, product=product)
            if "error" in result:
                raise ApiError("business_rule", 422)
            cart._update_programs_and_rewards()
            if cart.carrier_id:
                cart._set_delivery_method(cart.carrier_id)
            cart._ab_sync_cart_hold()
            return self._order_data(cart)
        raise ApiError("not_found", 404)

    @endpoint("/orders", tag="Orders", summary="Customer orders on this website", query=PAGE)
    def orders(self):
        return self._page(request.env["sale.order"].sudo(), self._owner_domain() & fields.Domain("state", "!=", "draft"),
                          lambda orders: [self._order_data(order) for order in orders])

    @endpoint("/orders/<int:order_id>", tag="Orders", summary="Owned order details and delivery progress")
    def order(self, order_id):
        order = self._order(order_id)
        result = self._order_data(order)
        result["tracking"] = order._ab_storefront_tracking_steps()
        result["payment_state"] = order.get_portal_last_transaction().state or None
        return result

    @endpoint("/wishlist", tag="Wishlist", summary="Published products in the customer wishlist", query=PAGE)
    def wishlist(self):
        wishes = request.env["product.wishlist"].current()
        return self._page(request.env["product.template"],
                          self._product_domain() & fields.Domain("id", "in", wishes.product_id.product_tmpl_id.ids), self._products)

    @endpoint("/wishlist/<int:product_id>", "PUT", tag="Wishlist", summary="Add a variant to the wishlist", payload=body({}))
    def add_wishlist(self, product_id):
        product = self._variant(product_id)
        model = request.env["product.wishlist"]
        existing = model.with_context(active_test=False).search([
            ("partner_id", "=", request.env.user.partner_id.id), ("product_id", "=", product.id)], limit=1)
        if existing:
            if existing.website_id != request.website:
                raise ApiError("conflict", 409)
            existing.write({"active": True})
        else:
            price = self._products(product.product_tmpl_id)[0]["price"]
            model._add_to_wishlist(request.pricelist.id, request.pricelist.currency_id.id,
                                   request.website.id, price, product.id, request.env.user.partner_id.id)
        return {"added": True}

    @endpoint("/wishlist/<int:product_id>", "DELETE", tag="Wishlist", summary="Remove a variant from the wishlist")
    def remove_wishlist(self, product_id):
        request.env["product.wishlist"].current().filtered(lambda item: item.product_id.id == product_id).write({"active": False})
        return {"removed": True}

    @endpoint("/history", tag="History", summary="Recently viewed published products")
    def history(self):
        model = request.env["ab.ecommerce.browsing.history"]
        ids = model._ab_partner_product_ids(model._ab_history_partner(request.env.user), request.website)
        products = request.env["product.template"].search(self._product_domain() & fields.Domain("id", "in", ids))
        return self._products(products.sorted(key=lambda item: ids.index(item.id)))

    @endpoint("/history/<int:product_id>", "PUT", tag="History", summary="Record a product view", payload=body({}))
    def record_history(self, product_id):
        product = self._product(product_id)
        model = request.env["ab.ecommerce.browsing.history"]
        model._ab_record_view(model._ab_history_partner(request.env.user), request.website, product)
        return {"recorded": True}

    @endpoint("/history", "DELETE", tag="History", summary="Clear customer browsing history")
    def clear_history(self):
        model = request.env["ab.ecommerce.browsing.history"]
        model._ab_clear_partner_history(model._ab_history_partner(request.env.user), request.website)
        return {"cleared": True}

    @endpoint("/contact", "POST", tag="Content", summary="Send a contact message", authenticated=False,
              payload=body({"name": TEXT, "phone": TEXT, "email_from": TEXT, "subject": TEXT,
                            "description": schema(maxLength=5000)}, ("name", "email_from", "subject", "description")), status=201)
    def contact(self):
        values = dict(request.ab_api_data, website_id=request.website.id, company_id=request.website.company_id.id)
        request.env["ab_contact_message"].sudo().create(values)
        return {"submitted": True}

    @endpoint("/branches", tag="Content", summary="Public branch directory", authenticated=False)
    def branches(self):
        markup = request.env["ir.ui.view"]._render_template("ab_ecommerce_storefront.branches_directory")
        document = html.fromstring(str(markup))
        result = []
        for element in document.xpath("//*[@data-branch-id]"):
            def text_value(name):
                nodes = element.xpath(f".//*[@data-branch-{name}]")
                return nodes[0].text_content().strip() if nodes else ""
            result.append({"id": element.get("data-branch-id"), "name": text_value("name"),
                           "address": text_value("address"), "region": text_value("region"),
                           "latitude": float(element.get("data-lat")), "longitude": float(element.get("data-lng"))})
        return result

    @endpoint("/pages", tag="Content", summary="Public policy and company page URLs", authenticated=False)
    def pages(self):
        return {"about": "/about-us", "terms": "/terms-and-conditions", "returns": "/return-policy",
                "partnerships": "/business-partnerships", "contact": "/contactus"}

    def _payment_options(self, cart):
        providers = request.env["payment.provider"].sudo()._get_compatible_providers(
            cart.company_id.id, cart.partner_invoice_id.id, cart.amount_total,
            currency_id=cart.currency_id.id, website_id=request.website.id)
        providers = providers.filtered(lambda item: item.is_published and (not item.website_id or item.website_id == request.website))
        methods = request.env["payment.method"].sudo()._get_compatible_payment_methods(
            providers.ids, cart.partner_invoice_id.id, currency_id=cart.currency_id.id)
        return providers, methods

    @endpoint("/cart/payment-methods", tag="Checkout", summary="Compatible payment providers and methods")
    def payment_methods(self):
        cart = self._cart()
        if not cart:
            raise ApiError("not_found", 404)
        providers, methods = self._payment_options(cart)
        return [{"provider_id": provider.id, "name": provider.name, "code": provider.code,
                 "test_mode": provider.state == "test",
                 "methods": [{"id": method.id, "name": method.name, "code": method.code}
                             for method in methods if method in provider.payment_method_ids]}
                for provider in providers]

    @endpoint("/cart/checkout", "POST", tag="Checkout", summary="Validate cart and obtain an idempotent payment key", payload=body({}))
    def prepare_checkout(self):
        cart = self._cart(mutable=True)
        if not cart or not cart.order_line:
            raise ApiError("invalid_input")
        address = self._address(cart.partner_shipping_id.id)
        if not all((address.street, address.city, address.country_id, address.phone)):
            raise ApiError("invalid_input")
        cart._recompute_cart()
        cart._check_cart_is_ready_to_be_paid()
        submission = checkout_submission(cart, renew_failed=True)
        return {"order": self._order_data(cart), "idempotency_key": submission.key}

    @endpoint("/orders/<int:order_id>/payment", "POST", tag="Checkout", summary="Start or retry the same payment safely",
              payload=body({"idempotency_key": SECRET, "provider_id": ID, "payment_method_id": ID},
                           ("idempotency_key", "provider_id", "payment_method_id")))
    def payment(self, order_id):
        data = request.ab_api_data
        order = self._order(order_id)
        providers, methods = self._payment_options(order)
        provider = providers.filtered(lambda item: item.id == data["provider_id"])
        method = methods.filtered(lambda item: item.id == data["payment_method_id"])
        if not provider or not method or method not in provider.payment_method_ids:
            raise ApiError("invalid_input")
        request.cart = order
        request.session["sale_order_id"] = order.id
        result = StorefrontPaymentPortal().shop_payment_transaction(
            order.id, order._portal_ensure_token(), idempotency_key=data["idempotency_key"],
            provider_id=provider.id, payment_method_id=method.id, token_id=None,
            amount=order.amount_total, flow="redirect", tokenization_requested=False,
            landing_route=f"/my/orders/{order.id}")
        return {"order_id": order.id, "processing": result}

    @endpoint("/orders/<int:order_id>/invoices", tag="Orders", summary="Posted customer invoices for an owned order")
    def invoices(self, order_id):
        invoices = self._order(order_id)._ab_storefront_customer_invoices()
        return [{"id": invoice.id, "number": invoice.name, "date": invoice.invoice_date,
                 "total": invoice.amount_total, "currency": invoice.currency_id.name,
                 "payment_state": invoice.payment_state,
                 "download_url": f"/api/v1/orders/{order_id}/invoices/{invoice.id}/pdf"}
                for invoice in invoices]

    @endpoint("/orders/<int:order_id>/invoices/<int:invoice_id>/pdf", tag="Orders", summary="Download an owned posted invoice")
    def invoice_pdf(self, order_id, invoice_id):
        invoices = self._order(order_id)._ab_storefront_customer_invoices()
        invoice = invoices.filtered(lambda item: item.id == invoice_id)
        if not invoice:
            raise ApiError("not_found", 404)
        pdf, kind = request.env["ir.actions.report"].sudo()._render_qweb_pdf("account.account_invoices", res_ids=invoice.ids)
        return request.make_response(pdf, headers={"Content-Type": "application/pdf", "Cache-Control": "no-store",
                                                  "Content-Disposition": 'attachment; filename="invoice.pdf"',
                                                  "X-Content-Type-Options": "nosniff"})

    def _prescription_domain(self):
        owner = request.env.user.partner_id
        return (fields.Domain("website_id", "=", request.website.id)
                & fields.Domain("company_id", "=", request.website.company_id.id)
                & (fields.Domain("partner_id", "=", owner.id)
                   | fields.Domain("partner_id.parent_id", "=", owner.id)))

    def _prescription(self, prescription_id):
        prescription = request.env["ab.prescription.order"].sudo().search(
            self._prescription_domain() & fields.Domain("id", "=", prescription_id), limit=1)
        if not prescription:
            raise ApiError("not_found", 404)
        return prescription

    def _prescription_data(self, prescriptions):
        return [{"id": record.id, "reference": record._ab_storefront_display_reference(),
                 "state": record.state, "state_label": record.state_label,
                 "customer_note": record.customer_note or "", "created_at": record.create_date.isoformat() + "Z",
                 "order_id": record.sale_order_id.id or None,
                 "image_url": f"/api/v1/prescriptions/{record.id}/image"} for record in prescriptions]

    @endpoint("/prescriptions/submission", "POST", tag="Prescriptions", summary="Issue a key for one prescription upload", payload=body({}))
    def prescription_submission(self):
        submission = request.env["ab_storefront_submission"]._issue("prescription", request.website, submission_owner())
        return {"idempotency_key": submission.key, "expires_at": submission.expires_at.isoformat() + "Z"}

    @endpoint("/prescriptions", "POST", tag="Prescriptions", summary="Upload a private prescription image for pharmacy review", upload=True, status=201)
    def upload_prescription(self):
        form = request.httprequest.form
        if set(form) - {"idempotency_key", "address_id", "customer_note"}:
            raise ApiError("invalid_input")
        note = form.get("customer_note", "")
        if len(note) > 2000:
            raise ApiError("invalid_input")
        address = self._address(int(form.get("address_id", "0")))
        if not all((address.street, address.city, address.state_id, address.country_id, address.phone)):
            raise ApiError("invalid_input")
        values = AbPrescriptionOrderPortal()._read_prescription_upload()
        payload = {"address_id": address.id, "customer_note": note,
                   "image": hashlib.sha256(values["prescription_image"]).hexdigest()}
        submission = request.env["ab_storefront_submission"]._claim(
            form.get("idempotency_key"), "prescription", request.website, submission_owner(), payload)
        if submission.prescription_id:
            return self._prescription_data(self._prescription(submission.prescription_id.id))[0]
        model = request.env["ab.prescription.order"].sudo()
        method = model._ab_storefront_cash_on_delivery_method(request.website.company_id)
        if not method:
            raise ApiError("business_rule", 422)
        values.update(partner_id=address.id, user_id=request.env.uid, customer_note=note,
                      company_id=request.website.company_id.id, website_id=request.website.id,
                      payment_method_id=method.id)
        prescription = model.create(values)
        prescription._ab_storefront_create_sale_order(allow_unreviewed=True)
        submission.write({"prescription_id": prescription.id, "order_id": prescription.sale_order_id.id,
                          "result_partner_id": address.id})
        return self._prescription_data(prescription)[0]

    @endpoint("/prescriptions", tag="Prescriptions", summary="Customer prescriptions", query=PAGE)
    def prescriptions(self):
        return self._page(request.env["ab.prescription.order"].sudo(), self._prescription_domain(), self._prescription_data)

    @endpoint("/prescriptions/<int:prescription_id>", tag="Prescriptions", summary="Owned prescription status")
    def prescription(self, prescription_id):
        return self._prescription_data(self._prescription(prescription_id))[0]

    @endpoint("/prescriptions/<int:prescription_id>/image", tag="Prescriptions", summary="Read an owned private prescription image")
    def prescription_image(self, prescription_id):
        record = self._prescription(prescription_id)
        return request.make_response(base64.b64decode(record.prescription_image), headers={
            "Content-Type": record.prescription_mimetype, "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer"})
