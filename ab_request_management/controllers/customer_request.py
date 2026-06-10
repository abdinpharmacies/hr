from odoo import http
from odoo.exceptions import ValidationError
from odoo.http import request


class AbRequestCustomerController(http.Controller):
    @http.route("/requests/customer-form", type="http", auth="public", website=True, sitemap=False)
    def customer_form(self, **kwargs):
        request_types = request.env["ab_request_type"].sudo().search([], order="name")
        categories = request.env["ab_request_category"].sudo().search([], order="name")
        return request.render(
            "ab_request_management.customer_request_form",
            {
                "categories": categories,
                "request_types": request_types,
                "post": kwargs,
            },
        )

    @http.route("/requests/customer-submit", type="http", auth="public", methods=["POST"], website=True, csrf=True, sitemap=False)
    def customer_submit(self, **post):
        vals = {
            "customer_name": post.get("customer_name"),
            "customer_phone": post.get("customer_phone"),
            "customer_email": post.get("customer_email"),
            "request_category_id": int(post["request_category_id"]) if post.get("request_category_id") else False,
            "request_type_id": int(post["request_type_id"]) if post.get("request_type_id") else False,
            "subject": post.get("subject"),
            "description": post.get("description"),
            "source": "embed",
        }
        try:
            website_request = request.env["ab_request_website"].sudo().create(vals)
        except (ValueError, ValidationError) as error:
            request_types = request.env["ab_request_type"].sudo().search([], order="name")
            categories = request.env["ab_request_category"].sudo().search([], order="name")
            return request.render(
                "ab_request_management.customer_request_form",
                {
                    "categories": categories,
                    "request_types": request_types,
                    "post": post,
                    "error": str(error),
                },
            )
        return request.render("ab_request_management.customer_request_thanks", {"website_request": website_request})
