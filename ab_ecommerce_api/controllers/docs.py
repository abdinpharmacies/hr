import re

from odoo import http
from odoo.http import request
from werkzeug.exceptions import Forbidden

from .common import OPERATIONS, PREFIX, secure_transport
from .schemas import RESULTS, SCHEMAS


def openapi_document():
    paths = {}
    for item in OPERATIONS:
        path_parameters = re.findall(r"<(?:(\w+):)?(\w+)>", item["path"])
        path = re.sub(r"<(?:[^:]+:)?(\w+)>", r"{\1}", item["path"])
        parameters = [{"name": name, "in": "path", "required": True,
                       "schema": {"type": "integer", "minimum": 1} if converter == "int"
                       else {"type": "string", "minLength": 1, "maxLength": 128}}
                      for converter, name in path_parameters]
        parameters += [{"name": name, "in": "query", "schema": definition}
                       for name, definition in item["query"].items()]
        parameters.append({"name": "lang", "in": "query", "schema": {"type": "string", "enum": ["en", "ar"], "default": "en"}})
        if item["idempotency"]:
            parameters.append({"name": "Idempotency-Key", "in": "header", "required": True,
                               "description": "A unique 16-128 character key. Reusing it with the same body returns the first result.",
                               "schema": {"type": "string", "minLength": 16, "maxLength": 128}})
        operation = {"operationId": item["operation_id"], "summary": item["summary"],
                     "tags": [item["tag"]], "parameters": parameters,
                     "security": [{"customerToken": []}] if item["authenticated"] else [],
                     "responses": {str(item["status"]): {"description": "Success",
                         "content": {"application/json": {"schema": {"type": "object", "required": ["data"],
                            "properties": {"data": item["result"] or RESULTS.get(item["operation_id"], {})}}}}}}}
        if item["operation_id"] in ("product_image", "banner_image", "prescription_image", "invoice_pdf"):
            mime = "application/pdf" if item["operation_id"] == "invoice_pdf" else "image/*"
            operation["responses"]["200"]["content"] = {mime: {"schema": {"type": "string", "format": "binary"}}}
        for code in (400, 401, 403, 404, 409, 413, 415, 422, 429, 500):
            operation["responses"][str(code)] = {"description": "API error",
                "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}}}
        if item["payload"] is not None:
            operation["requestBody"] = {"required": True, "content": {
                "application/json": {"schema": item["payload"]}}}
        if item["upload"]:
            operation["requestBody"] = {"required": True, "content": {"multipart/form-data": {
                "schema": {"type": "object", "required": ["prescription_image", "address_id", "idempotency_key"],
                    "properties": {"prescription_image": {"type": "string", "format": "binary"},
                                   "address_id": {"type": "integer"}, "idempotency_key": {"type": "string"},
                                   "customer_note": {"type": "string", "maxLength": 2000}}}}}}
        paths.setdefault(path, {})[item["method"].lower()] = operation
    return {"openapi": "3.0.3", "info": {"title": "Abdin eCommerce API", "version": "1.0.0",
                "description": "Customer-only API. Sign in, copy data.access_token into Authorize, and try a protected request. "
                "Tokens expire after 15 minutes; rotate using the refresh endpoint. HTTPS is required outside loopback development. "
                "Cookie authentication is never accepted by customer endpoints. Prices, stock and payments are validated by Odoo. "
                "All JSON responses use data or error envelopes. Payment processing values may require a provider WebView or SDK; "
                "the app must poll the owned order for the verified payment state. Real delivery/payment adapters can have external effects."},
            "servers": [{"url": PREFIX}], "paths": paths,
            "components": {"securitySchemes": {"customerToken": {"type": "http", "scheme": "bearer",
                "description": "Customer access token returned by login; never use an administrator API key."}},
                "schemas": {**SCHEMAS, "Error": {"type": "object", "required": ["error"], "properties": {
                    "error": {"type": "object", "required": ["code", "message"],
                              "properties": {"code": {"type": "string"}, "message": {"type": "string"}}}}}}}}


class EcommerceApiDocs(http.Controller):
    def _check_docs(self):
        if not request.env.user.has_group("base.group_system"):
            raise Forbidden()

    @http.route("/api/v1/docs", type="http", auth="user", methods=["GET"], website=True, sitemap=False)
    def docs(self, **kwargs):
        self._check_docs()
        language = kwargs.get("lang")
        if language in ("en_US", "ar_001") and language in dict(request.env["res.lang"].get_installed()):
            request.update_context(lang=language)
        response = request.render("ab_ecommerce_api.docs_page", {"embedded": kwargs.get("embedded") == "1"})
        response.headers.update({"Cache-Control": "no-store", "Referrer-Policy": "no-referrer",
                                 "X-Frame-Options": "SAMEORIGIN", "X-Content-Type-Options": "nosniff"})
        return response

    @http.route("/api/v1/openapi.json", type="http", auth="user", methods=["GET"], sitemap=False)
    def spec(self, **kwargs):
        self._check_docs()
        return request.make_json_response(openapi_document(), headers={"Cache-Control": "no-store"})

    @http.route("/api/v1/auth/browser/authorize/<string:token>", type="http", auth="user", website=True,
                methods=["GET", "POST"], csrf=True, sitemap=False, multilang=False)
    def authorize_browser(self, token, **kwargs):
        secure_transport()
        grants = request.env["ab_ecommerce_api_browser_grant"]
        grants._find(token, request.website)
        request.env["ab_ecommerce_api_session"]._assert_customer(request.env.user, request.website)
        approved = request.httprequest.method == "POST"
        if approved:
            grants._approve(token, request.website, request.env.user)
        response = request.render("ab_ecommerce_api.browser_authorization", {"approved": approved})
        response.headers.update({"Cache-Control": "no-store", "Referrer-Policy": "no-referrer",
                                 "Content-Security-Policy": "frame-ancestors 'none'", "X-Frame-Options": "DENY"})
        return response
