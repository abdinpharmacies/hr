import functools
import ipaddress
import logging
import math
import re
import secrets

from psycopg2 import OperationalError
from werkzeug.exceptions import BadRequest, HTTPException

from odoo import http
from odoo.exceptions import AccessDenied, AccessError, MissingError, UserError, ValidationError
from odoo.http import request


_logger = logging.getLogger(__name__)
OPERATIONS = []
PREFIX = "/api/v1"


class ApiError(Exception):
    def __init__(self, code, status=400):
        self.code = code
        self.status = status


def schema(kind="string", **values):
    return dict(type=kind, **values)


def body(properties, required=()):
    return {"type": "object", "properties": properties,
            "required": list(required), "additionalProperties": False}


def validate(value, definition):
    kind = definition.get("type")
    valid = {"object": isinstance(value, dict), "array": isinstance(value, list),
             "string": isinstance(value, str), "boolean": isinstance(value, bool),
             "integer": type(value) is int,
             "number": type(value) in (int, float) and math.isfinite(value)}
    if kind and not valid.get(kind, False):
        raise ApiError("invalid_input")
    if "enum" in definition and value not in definition["enum"]:
        raise ApiError("invalid_input")
    if kind == "object":
        props = definition.get("properties", {})
        if set(definition.get("required", [])) - set(value) or set(value) - set(props):
            raise ApiError("invalid_input")
        for name, item in value.items():
            validate(item, props[name])
    if kind == "array":
        if len(value) > definition.get("maxItems", 100):
            raise ApiError("invalid_input")
        for item in value:
            validate(item, definition["items"])
    if kind == "string" and not definition.get("minLength", 0) <= len(value) <= definition.get("maxLength", 2000):
        raise ApiError("invalid_input")
    if kind in ("integer", "number") and not definition.get("minimum", -1e12) <= value <= definition.get("maximum", 1e12):
        raise ApiError("invalid_input")


def error_message(code):
    messages = {
        "invalid_input": request.env._("Check the request fields and try again."),
        "unauthorized": request.env._("Sign in again to continue."),
        "forbidden": request.env._("You cannot access this resource."),
        "not_found": request.env._("The requested resource was not found."),
        "rate_limited": request.env._("Too many requests. Please try again later."),
        "https_required": request.env._("Use HTTPS to access the API."),
        "conflict": request.env._("This operation conflicts with the current record state."),
        "business_rule": request.env._("The operation could not be completed. Review your details and availability."),
        "mfa_required": request.env._("Additional account verification is required."),
        "internal_error": request.env._("An unexpected error occurred. Please try again."),
        "unsupported_media_type": request.env._("Send the request as JSON."),
        "payload_too_large": request.env._("The uploaded data is too large."),
    }
    return messages.get(code, messages["business_rule"])


def respond(data=None, code=None, status=200):
    payload = {"error": {"code": code, "message": error_message(code)}} if code else {"data": data}
    headers = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
               "Referrer-Policy": "no-referrer", "X-Request-ID": secrets.token_hex(12)}
    if status == 429:
        headers["Retry-After"] = "60"
    if status == 401:
        headers["WWW-Authenticate"] = "Bearer"
    return request.make_json_response(payload, headers=headers, status=status)


def secure_transport():
    if request.httprequest.is_secure:
        return
    try:
        remote = ipaddress.ip_address(request.httprequest.remote_addr or "")
        host = request.httprequest.host.split(":")[0]
        local = host == "localhost" or ipaddress.ip_address(host).is_loopback
    except ValueError:
        local = False
    if not local or not remote.is_loopback:
        raise ApiError("https_required", 403)


def endpoint(path, method="GET", *, tag, summary, authenticated=True, payload=None,
             query=None, result=None, status=200, upload=False, idempotency=False):
    def decorate(func):
        OPERATIONS.append({"path": path, "method": method, "tag": tag, "summary": summary,
                           "authenticated": authenticated, "payload": payload, "query": query or {},
                           "result": result, "status": status, "upload": upload,
                           "idempotency": idempotency,
                           "operation_id": func.__name__})

        @functools.wraps(func)
        def wrapped(self, **kwargs):
            try:
                secure_transport()
                website = request.website
                request.session = http.Session(http.get_default_session(), secrets.token_hex(32))
                request.session.can_save = False
                request.update_env(user=website.user_id.id, su=False)
                request.update_context(allowed_company_ids=[website.company_id.id], website_id=website.id)
                language = request.httprequest.args.get("lang") or request.httprequest.headers.get("Accept-Language", "en").split(",")[0].split(";")[0]
                language = "ar_001" if language.startswith("ar") else "en_US"
                if language in dict(request.env["res.lang"].get_installed()):
                    request.update_context(lang=language)
                request.cart = request.env["sale.order"]
                maximum = 9 * 1024 * 1024 if upload else 32768
                if (request.httprequest.content_length or 0) > maximum:
                    raise ApiError("payload_too_large", 413)
                auth_limits = {
                    "/auth/login": 10,
                    "/auth/register": 5,
                    "/auth/phone/start": 5,
                    "/auth/recovery": 5,
                    "/auth/browser/start": 10,
                    "/auth/browser/token": 30,
                    "/auth/refresh": 30,
                }
                limit = auth_limits.get(path, 30 if path.startswith("/auth/") else 180)
                action = "mobile-api:" + (func.__name__ if path.startswith("/auth/") else "request")
                subject = request.httprequest.remote_addr or "unknown"
                service = request.env["ab_storefront_auth_service"]
                if not service._rate_allow(action, subject, limit, 60):
                    raise ApiError("rate_limited", 429)
                auth = request.httprequest.headers.get("Authorization", "")
                session = None
                if auth:
                    if not auth.startswith("Bearer "):
                        raise AccessDenied()
                    session = request.env["ab_ecommerce_api_session"]._resolve(auth[7:], website)
                    request.update_env(user=session.user_id.id, su=False)
                    request.update_context(allowed_company_ids=[website.company_id.id], website_id=website.id)
                elif authenticated:
                    raise AccessDenied()
                request.ab_api_session = session
                request.website = website.with_env(request.env)
                request.ab_idempotency_key = None
                if idempotency:
                    key = request.httprequest.headers.get("Idempotency-Key", "")
                    if not re.fullmatch(r"[A-Za-z0-9._~-]{16,128}", key):
                        raise ApiError("invalid_input")
                    request.ab_idempotency_key = key
                request.pricelist = request.website._get_and_cache_current_pricelist()
                request.fiscal_position = request.website._get_and_cache_current_fiscal_position()
                request.ab_api_data = {}
                if payload is not None:
                    if request.httprequest.mimetype != "application/json":
                        raise ApiError("unsupported_media_type", 415)
                    data = request.httprequest.get_json()
                    validate(data, payload)
                    request.ab_api_data = data
                supplied = set(request.httprequest.args) - {"lang"}
                if supplied - set(query or {}):
                    raise ApiError("invalid_input")
                request.ab_api_query = {}
                for name, definition in (query or {}).items():
                    value = request.httprequest.args.get(name, definition.get("default"))
                    if value is None:
                        continue
                    try:
                        if definition.get("type") == "integer":
                            value = int(value)
                        elif definition.get("type") == "number":
                            value = float(value)
                    except (ValueError, TypeError):
                        raise ApiError("invalid_input") from None
                    validate(value, definition)
                    request.ab_api_query[name] = value
                with request.env.cr.savepoint():
                    path_names = re.findall(r"<(?:[^:]+:)?(\w+)>", path)
                    data = func(self, **{k: kwargs[k] for k in path_names})
                    if isinstance(data, http.Response):
                        return data
                    return respond(data, status=status)
            except ApiError as exc:
                return respond(code=exc.code, status=exc.status)
            except AccessDenied:
                return respond(code="unauthorized", status=401)
            except AccessError:
                return respond(code="forbidden", status=403)
            except MissingError:
                return respond(code="not_found", status=404)
            except (ValidationError, UserError):
                return respond(code="business_rule", status=422)
            except (BadRequest, ValueError, TypeError):
                return respond(code="invalid_input", status=400)
            except OperationalError:
                raise
            except HTTPException as exc:
                return respond(code="invalid_input", status=exc.code)
            except Exception:
                _logger.error("Storefront API operation failed: %s", func.__name__, exc_info=True)
                return respond(code="internal_error", status=500)

        return http.route(PREFIX + path, type="http", auth="public", website=True,
                          methods=[method], csrf=False, save_session=False, sitemap=False, multilang=False,
                          max_content_length=9 * 1024 * 1024 if upload else 32768)(wrapped)
    return decorate
