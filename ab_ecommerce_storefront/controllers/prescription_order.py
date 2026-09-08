import base64
import binascii

from odoo import _
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from odoo.exceptions import AccessError, MissingError, UserError
from odoo.http import request, route
from werkzeug.utils import secure_filename


class AbPrescriptionOrderPortal(CustomerPortal):
    _max_prescription_upload_size = 8 * 1024 * 1024
    _allowed_prescription_mimetypes = {
        "image/jpeg",
        "image/png",
        "image/webp",
    }

    _prescription_steps = [
        (
            "new",
            "Prescription received",
            "We received the prescription image successfully.",
        ),
        (
            "under_review",
            "Under review",
            "Our team is reviewing the prescription and preparing the next steps.",
        ),
        (
            "waiting_call_center",
            "Waiting for Call Center confirmation",
            "Our Call Center team will contact you to confirm the order details.",
        ),
        (
            "confirmed",
            "Confirmed",
            "Your prescription request is confirmed and will move to preparation.",
        ),
        (
            "preparing",
            "Preparing",
            "We are preparing your request now.",
        ),
        (
            "out_for_delivery",
            "Out for delivery",
            "Your order is on its way to you.",
        ),
        (
            "delivered",
            "Delivered",
            "Your request was delivered successfully.",
        ),
    ]

    def _prescription_domain(self):
        partner = request.env.user.partner_id.commercial_partner_id
        return [("partner_id", "child_of", [partner.id])]

    def _get_prescription_steps(self):
        return [
            (key, request.env._(label), request.env._(description))
            for key, label, description in self._prescription_steps
        ]

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
        if mimetype not in self._allowed_prescription_mimetypes:
            raise UserError("bad_type")
        if not self._is_supported_image(data, mimetype):
            raise UserError("invalid_image")

        return {
            "prescription_image": base64.b64encode(data),
            "prescription_filename": filename,
            "prescription_mimetype": mimetype,
        }

    def _is_supported_image(self, data, mimetype):
        if mimetype == "image/jpeg":
            return data.startswith(b"\xff\xd8\xff")
        if mimetype == "image/png":
            return data.startswith(b"\x89PNG\r\n\x1a\n")
        if mimetype == "image/webp":
            return len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"
        return False

    def _prescription_page_values(self, **values):
        PrescriptionOrder = request.env["ab.prescription.order"]
        recent_prescriptions = PrescriptionOrder.search(
            self._prescription_domain(),
            order="create_date desc, id desc",
            limit=3,
        )
        values.setdefault("error_code", False)
        values.setdefault("customer_note", "")
        values.update({
            "recent_prescriptions": recent_prescriptions,
            "prescription_max_upload_mb": self._max_prescription_upload_size // (1024 * 1024),
        })
        return values

    @route("/prescription-order", type="http", auth="user", website=True, sitemap=True)
    def prescription_order_page(self, **kw):
        return request.render(
            "ab_ecommerce_storefront.prescription_order_page",
            self._prescription_page_values(customer_note=kw.get("customer_note", "")),
        )

    @route("/prescription-order/submit", type="http", auth="user", methods=["POST"], website=True)
    def prescription_order_submit(self, **post):
        try:
            vals = self._read_prescription_upload()
            vals.update({
                "partner_id": request.env.user.partner_id.id,
                "user_id": request.env.user.id,
                "customer_note": (post.get("customer_note") or "").strip()[:2000],
            })
            order = request.env["ab.prescription.order"].create(vals)
        except UserError as error:
            return request.render(
                "ab_ecommerce_storefront.prescription_order_page",
                self._prescription_page_values(
                    error_code=error.args[0],
                    customer_note=post.get("customer_note", ""),
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

    @route("/my/prescriptions/<int:order_id>", type="http", auth="user", website=True)
    def portal_my_prescription(self, order_id, access_token=None, submitted=None, **kw):
        try:
            order = self._document_check_access("ab.prescription.order", order_id, access_token=access_token)
        except (AccessError, MissingError):
            return request.redirect("/my")

        values = self._prepare_portal_layout_values()
        values.update({
            "prescription": order,
            "prescription_steps": self._get_prescription_steps(),
            "prescription_state_keys": [step[0] for step in self._prescription_steps],
            "submitted": bool(submitted),
            "page_name": "prescriptions",
        })
        return request.render("ab_ecommerce_storefront.portal_my_prescription", values)

    @route("/my/prescriptions/<int:order_id>/image", type="http", auth="user", website=True)
    def portal_my_prescription_image(self, order_id, access_token=None, **kw):
        try:
            order = self._document_check_access("ab.prescription.order", order_id, access_token=access_token)
        except (AccessError, MissingError):
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
            (
                "Content-Disposition",
                f'inline; filename="{order.prescription_filename or "prescription"}"',
            ),
        ]
        return request.make_response(image, headers)
