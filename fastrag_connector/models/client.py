import ipaddress
import json
import shlex
import threading
from urllib.parse import urlencode, urlsplit
from uuid import UUID

import requests
from odoo import _, api, models
from odoo.exceptions import UserError


_sessions = threading.local()
MAX_JSON = 8 * 1024 * 1024
MAX_FILE = 20 * 1024 * 1024


def normalize_url(value):
    try:
        parsed = urlsplit(value.strip())
        parsed.port  # Validate explicit ports.
        if (not parsed.hostname or parsed.username is not None or parsed.query or parsed.fragment
                or parsed.path not in ("", "/") or "\\" in value or any(c.isspace() for c in value.strip())):
            raise ValueError
        if parsed.scheme == "http" and ipaddress.ip_address(parsed.hostname).is_loopback:
            return parsed.geturl().rstrip("/")
        if parsed.scheme == "https":
            return parsed.geturl().rstrip("/")
    except ValueError:
        pass
    raise UserError(_("Enter an HTTPS FastRAG URL, or an HTTP URL on a literal loopback IP."))


def resource(record_id, child=""):
    try:
        return f"/v1/records/{UUID(str(record_id))}{child}"
    except ValueError:
        raise UserError(_("Enter a valid record UUID.")) from None


def uuid(value):
    try:
        return str(UUID(str(value)))
    except ValueError:
        raise UserError(_("Enter a valid UUID.")) from None


def curl_command(method, url, body, params, upload, binary, secret):
    params = {k: v for k, v in (params or {}).items() if v is not None}
    args = ["curl", "--fail-with-body", "--silent", "--show-error", "--header", "@-", "-X", method]
    if body is not None:
        args += ["-H", "Content-Type: application/json", "--data-binary", json.dumps(body)]
    if upload:
        args += ["-F", "file=@/path/to/local-file", "--form-string", "caption=" + upload[2]]
    if binary:
        args += ["--output", "fastrag-attachment.bin"]
    args.append(url + ("?" + urlencode(params, doseq=True) if params else ""))
    return ("printf 'Authorization: Bearer %s\\n' \"$FASTRAG_API_KEY\" | "
            + shlex.join(args).replace(secret, "[redacted]"))


class FastragClient(models.AbstractModel):
    _name = "fastrag.api.client"
    _description = "FastRAG server-side API client"

    def _config(self):
        params = self.env["ir.config_parameter"].sudo()
        return normalize_url(params.get_param("fastrag.base_url", "")), params.get_param("fastrag.api_key", "")

    def _request(self, method, path, *, body=None, params=None, upload=None, key=None, binary=False):
        base, secret = self._config()
        if not secret:
            raise UserError(_("Configure a FastRAG API key first."))
        if not getattr(_sessions, "http", None):
            _sessions.http = requests.Session()
            _sessions.http.trust_env = False
        headers = {"Authorization": f"Bearer {secret}"}
        if key:
            headers["Idempotency-Key"] = uuid(key)
        if upload and len(upload[1]) > MAX_FILE:
            raise UserError(_("The attachment exceeds 20 MiB."))
        try:
            with _sessions.http.request(
                method, base + path, json=body, params=params, headers=headers, allow_redirects=False,
                files={"file": (upload[0], upload[1])} if upload else None,
                data={"caption": upload[2]} if upload else None, timeout=(5, 120), stream=True,
            ) as response:
                status = response.status_code
                success = 200 <= status < 300
                is_file = binary and success
                limit = MAX_FILE if is_file else MAX_JSON
                data = bytearray()
                for chunk in response.iter_content(65536):
                    data.extend(chunk)
                    if len(data) > limit:
                        raise UserError(_("The FastRAG response exceeded the size limit."))
                request_id = response.headers.get("X-Request-ID", "")
                if secret in request_id:
                    request_id = ""
                result = {"status": status, "request_id": request_id[:128], "data": None,
                          "curl": curl_command(method, base + path, body, params, upload, binary, secret)}
                if is_file:
                    result["file"] = bytes(data)
                elif data:
                    # Only show known API errors, not arbitrary HTML from a gateway.
                    try:
                        payload = json.loads(data.decode("utf-8").replace(secret, "[redacted]"))
                    except (ValueError, RecursionError):
                        payload = None
                    if success or isinstance(payload, dict) and isinstance(payload.get("detail"), str):
                        result["data"] = payload
                return result
        except requests.RequestException:
            raise UserError(_("FastRAG request failed. Check connectivity and TLS settings.")) from None
        finally:
            _sessions.http.cookies.clear()

    @api.private
    def test_connection(self):
        return self._request("GET", "/v1/connection")

    @api.private
    def list_records(self, **params):
        return self._request("GET", "/v1/records", params=params)

    @api.private
    def create_record(self, data, key=None):
        return self._request("POST", "/v1/records", body=data, key=key)

    @api.private
    def get_record(self, record_id):
        return self._request("GET", resource(record_id))

    @api.private
    def update_record(self, record_id, data):
        return self._request("PATCH", resource(record_id), body=data)

    @api.private
    def archive_record(self, record_id):
        return self.update_record(record_id, {"archived": True})

    @api.private
    def add_attachment(self, record_id, filename, content, caption="", key=None):
        return self._request("POST", resource(record_id, "/attachments"), upload=(filename, content, caption), key=key)

    @api.private
    def download_attachment(self, record_id, file_id):
        return self._request("GET", resource(record_id, f"/attachments/{uuid(file_id)}"), binary=True)

    @api.private
    def remove_attachment(self, record_id, file_id):
        return self._request("DELETE", resource(record_id, f"/attachments/{uuid(file_id)}"))

    @api.private
    def index_record(self, record_id, key=None):
        return self._request("POST", resource(record_id, "/index"), key=key)

    @api.private
    def get_job_status(self, job_id):
        return self._request("GET", f"/v1/jobs/{uuid(job_id)}")

    @api.private
    def search_records(self, question):
        return self._request("POST", "/v1/search", body={"question": question})

    @api.private
    def ask_question(self, question):
        return self._request("POST", "/v1/answers", body={"question": question})
