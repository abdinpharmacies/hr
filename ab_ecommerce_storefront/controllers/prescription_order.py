import base64
import binascii
import io

from PIL import Image, UnidentifiedImageError
import PIL.WebPImagePlugin  # noqa: F401 - register WebP support in Odoo workers.

from odoo import _
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from odoo.exceptions import AccessError, MissingError, UserError
from odoo.http import request, route
from werkzeug.utils import secure_filename

from .auth import is_valid_egyptian_mobile, normalize_egyptian_phone


class AbPrescriptionOrderPortal(CustomerPortal):
    _max_prescription_upload_size = 8 * 1024 * 1024
    _allowed_prescription_mimetypes = {
        "image/jpeg",
        "image/png",
        "image/webp",
    }

    def _prescription_domain(self):
        if request.env.user._is_public():
            return [("id", "=", 0)]
        partner = request.env.user.partner_id.commercial_partner_id
        return [("partner_id", "child_of", [partner.id])]

    def _read_prescription_upload(self):
        uploads = request.httprequest.files.getlist("prescription_image")
        upload = next((item for item in uploads if item and item.filename), None)
        if not upload:
            raise UserError("missing_image")

        mimetype = upload.mimetype or ""
        filename = secure_filename(upload.filename) or _("prescription")
        data = upload.read(self._max_prescription_upload_size + 1)
        if len(data) > self._max_prescription_upload_size:
            raise UserError("too_large")
        detected_mimetype = self._get_supported_image_mimetype(data)
        if not detected_mimetype:
            raise UserError("invalid_image")

        return {
            "prescription_image": base64.b64encode(data),
            "prescription_filename": filename,
            "prescription_mimetype": detected_mimetype,
        }

    def _get_supported_image_mimetype(self, data):
        try:
            with Image.open(io.BytesIO(data)) as image:
                if image.width * image.height > 25_000_000:
                    return False
                mimetype = Image.MIME.get(image.format)
                if mimetype not in self._allowed_prescription_mimetypes:
                    return False
                image.verify()
            return mimetype
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
            return False

    def _prescription_page_values(self, **values):
        PrescriptionOrder = request.env["ab.prescription.order"]
        country = request.website.company_id.country_id or request.env["res.country"].sudo().search(
            [("code", "=", "EG")], limit=1,
        )
        recent_prescriptions = PrescriptionOrder if request.env.user._is_public() else PrescriptionOrder.search(
            self._prescription_domain(),
            order="create_date desc, id desc",
            limit=3,
        )
        values.setdefault("error_code", False)
        values.setdefault("customer_note", "")
        values.setdefault("guest_city", "")
        values.setdefault("guest_state_id", "")
        country_states = (
            country.state_ids.sorted("name")
            if country
            else request.env["res.country.state"]
        )
        values.update({
            "prescription_country": country,
            "prescription_country_states": country_states,
            "recent_prescriptions": recent_prescriptions,
            "prescription_max_upload_mb": self._max_prescription_upload_size // (1024 * 1024),
        })
        return values

    def _prescription_partner_values(self, post):
        if not request.env.user._is_public():
            return {
                "partner_id": request.env.user.partner_id.id,
                "user_id": request.env.user.id,
            }
        name = (post.get("guest_name") or "").strip()
        phone = normalize_egyptian_phone(post.get("guest_phone"))
        address = (post.get("guest_address") or "").strip()
        city = (post.get("guest_city") or "").strip()
        state_value = (post.get("guest_state_id") or "").strip()
        if not name:
            raise UserError("missing_name")
        if not is_valid_egyptian_mobile(phone):
            raise UserError("missing_phone")
        if not state_value.isdigit():
            raise UserError("missing_state")
        if not city:
            raise UserError("missing_city")
        if not address:
            raise UserError("missing_address")
        country = request.website.company_id.country_id or request.env["res.country"].sudo().search(
            [("code", "=", "EG")], limit=1,
        )
        state = request.env["res.country.state"].sudo().browse(int(state_value)).exists()
        if not state or (country and state.country_id != country):
            raise UserError("missing_state")
        # A supplied phone number is not proof of ownership of an existing partner.
        partner = request.env["res.partner"].sudo().create({
            "name": name[:256],
            "phone": phone,
            "email": (post.get("guest_email") or "").strip()[:256] or False,
            "street": address[:512],
            "city": city[:256],
            "state_id": state.id,
            "country_id": (country or state.country_id).id,
            "lang": request.env.lang,
        })
        return {
            "partner_id": partner.id,
            "user_id": False,
        }

    @route("/prescription-order", type="http", auth="public", website=True, sitemap=True)
    def prescription_order_page(self, **kw):
        return request.render(
            "ab_ecommerce_storefront.prescription_order_page",
            self._prescription_page_values(
                customer_note=kw.get("customer_note", ""),
                guest_name=kw.get("guest_name", ""),
                guest_phone=kw.get("guest_phone", ""),
                guest_email=kw.get("guest_email", ""),
                guest_address=kw.get("guest_address", ""),
                guest_city=kw.get("guest_city", ""),
                guest_state_id=kw.get("guest_state_id", ""),
            ),
        )

    @route("/prescription-order/submit", type="http", auth="public", methods=["POST"], website=True)
    def prescription_order_submit(self, **post):
        try:
            vals = self._read_prescription_upload()
            PrescriptionOrder = request.env["ab.prescription.order"].sudo()
            payment_method = PrescriptionOrder._ab_storefront_cash_on_delivery_method(
                request.website.company_id
            )
            if not payment_method:
                raise UserError("payment_method_unavailable")
            vals.update(self._prescription_partner_values(post))
            vals["payment_method_id"] = payment_method.id
            vals["customer_note"] = (post.get("customer_note") or "").strip()[:2000]
            vals["company_id"] = request.website.company_id.id
            vals["website_id"] = request.website.id
            order = PrescriptionOrder.create(vals)
            order._ab_storefront_create_sale_order(allow_unreviewed=True)
        except UserError as error:
            return request.render(
                "ab_ecommerce_storefront.prescription_order_page",
                self._prescription_page_values(
                    error_code=error.args[0],
                    customer_note=post.get("customer_note", ""),
                    guest_name=post.get("guest_name", ""),
                    guest_phone=post.get("guest_phone", ""),
                    guest_email=post.get("guest_email", ""),
                    guest_address=post.get("guest_address", ""),
                    guest_city=post.get("guest_city", ""),
                    guest_state_id=post.get("guest_state_id", ""),
                ),
            )
        return request.redirect(order.get_portal_url(query_string="&submitted=1"))

    @route("/my/prescriptions", type="http", auth="user", website=True)
    def portal_my_prescriptions(self, page=1, **kw):
        PrescriptionOrder = request.env["ab.prescription.order"]
        domain = self._prescription_domain()
        order_count = PrescriptionOrder.search_count(domain)
        pager = portal_pager(
            url="/my/prescriptions",
            total=order_count,
            page=page,
            step=self._items_per_page,
        )
        prescriptions = PrescriptionOrder.search(
            domain,
            order="create_date desc, id desc",
            limit=self._items_per_page,
            offset=pager["offset"],
        )
        values = self._prepare_portal_layout_values()
        values.update({
            "prescriptions": prescriptions,
            "page_name": "prescriptions",
            "pager": pager,
        })
        return request.render("ab_ecommerce_storefront.portal_my_prescriptions", values)

    @route("/my/prescriptions/<int:order_id>", type="http", auth="public", website=True)
    def portal_my_prescription(self, order_id, access_token=None, submitted=None, **kw):
        try:
            order = self._document_check_access("ab.prescription.order", order_id, access_token=access_token)
        except (AccessError, MissingError):
            return request.not_found()

        if order.website_id and order.website_id != request.website:
            return request.not_found()

        values = self._prepare_portal_layout_values()
        values.update({
            "prescription": order,
            "submitted": bool(submitted),
            "page_name": "prescriptions",
        })
        response = request.render("ab_ecommerce_storefront.portal_my_prescription", values)
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @route("/my/prescriptions/<int:order_id>/image", type="http", auth="public", website=True)
    def portal_my_prescription_image(self, order_id, access_token=None, **kw):
        try:
            order = self._document_check_access("ab.prescription.order", order_id, access_token=access_token)
        except (AccessError, MissingError):
            return request.not_found()

        if order.website_id and order.website_id != request.website:
            return request.not_found()

        try:
            image = base64.b64decode(order.prescription_image or b"")
        except (binascii.Error, TypeError):
            return request.not_found()
        if not image:
            return request.not_found()

        headers = [
            ("Content-Type", order.prescription_mimetype or "image/jpeg"),
            ("Content-Length", str(len(image))),
            ("Cache-Control", "private, no-store"),
            ("X-Content-Type-Options", "nosniff"),
            (
                "Content-Disposition",
                f'inline; filename="{order.prescription_filename or "prescription"}"',
            ),
        ]
        return request.make_response(image, headers)
