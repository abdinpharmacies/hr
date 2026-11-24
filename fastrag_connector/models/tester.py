import base64
import json
import re
from time import monotonic
from uuid import uuid4

from odoo import _, fields, models
from odoo.exceptions import AccessError, UserError

from .client import MAX_FILE, normalize_url


OPERATIONS = [
    ("test_connection", "Test connection"),
    ("list_records", "List records"),
    ("create_record", "Create record"),
    ("get_record", "Get record"),
    ("update_record", "Update record"),
    ("archive_record", "Archive record"),
    ("add_attachment", "Add attachment / image"),
    ("download_attachment", "Download attachment"),
    ("remove_attachment", "Remove attachment"),
    ("index_record", "Queue indexing"),
    ("get_job_status", "Get job status"),
    ("search_records", "Search"),
    ("ask_question", "Ask a question"),
]


class FastragTester(models.TransientModel):
    _name = "fastrag.api.tester"
    _description = "FastRAG API settings and tester"

    base_url = fields.Char(default=lambda s: s.env["ir.config_parameter"].sudo().get_param(
        "fastrag.base_url", "http://127.0.0.1:8111"), required=True)
    operation = fields.Selection(OPERATIONS, default="test_connection", required=True)
    record_id = fields.Char("Record UUID")
    file_id = fields.Char("Attachment UUID")
    job_id = fields.Char("Job UUID")
    title = fields.Char(default="FastRAG connection test")
    record_text = fields.Text(default="Test knowledge: The demo support desk opens at 9 AM.")
    json_input = fields.Text("JSON fields", default="{}", help="Update fields or list query parameters.")
    question = fields.Text(default="When does the demo support desk open?")
    upload = fields.Binary(attachment=False)
    upload_name = fields.Char()
    caption = fields.Char()
    confirm_change = fields.Boolean("Confirm change to the specified record")
    result = fields.Text(readonly=True)
    curl_example = fields.Char("Copy cURL", readonly=True)
    download = fields.Binary(readonly=True, attachment=False)
    download_name = fields.Char(readonly=True, default="fastrag-attachment.bin")
    # Do not persist replacement keys in transient records, even briefly.
    replacement_key = fields.Char(compute="_empty_key", inverse="_ignore_key")

    def _empty_key(self):
        for wizard in self:
            wizard.replacement_key = False

    def _ignore_key(self):
        self._require_admin()
        params = self.env["ir.config_parameter"].sudo()
        for wizard in self:
            key = wizard.replacement_key
            if key:
                if not re.fullmatch(r"[A-Za-z0-9_-]{32,128}", key):
                    raise UserError(_("Enter a valid FastRAG API key."))
                params.set_param("fastrag.base_url", normalize_url(wizard.base_url))
                params.set_param("fastrag.api_key", key)
                wizard.invalidate_recordset(["replacement_key"], flush=False)

    def _require_admin(self):
        if not self.env.user.has_group("base.group_system"):
            raise AccessError(_("Only system administrators can use the FastRAG tester."))
        self.check_access("write")

    def _reopen(self):
        return {"type": "ir.actions.act_window", "name": _("FastRAG API Tester"), "res_model": self._name,
                "res_id": self.id, "view_mode": "form", "target": "current"}

    def action_save_connection(self):
        self.ensure_one()
        self._require_admin()
        self.env["ir.config_parameter"].sudo().set_param("fastrag.base_url", normalize_url(self.base_url))
        self.write({"result": _("Connection settings saved."), "curl_example": False, "download": False})
        return self._reopen()

    def _json_object(self):
        try:
            result = json.loads(self.json_input or "{}", parse_constant=lambda value: float("nan"))
            if not isinstance(result, dict):
                raise ValueError
            json.dumps(result, allow_nan=False)
            return result
        except (ValueError, RecursionError):
            raise UserError(_("Enter a valid JSON object.")) from None

    def action_run(self):
        self.ensure_one()
        self._require_admin()
        client = self.env["fastrag.api.client"]
        if normalize_url(self.base_url) != client._config()[0]:
            raise UserError(_("Save connection settings before running an API method."))
        op = self.operation
        rid, fid = self.record_id, self.file_id
        if op in {"update_record", "archive_record", "add_attachment", "remove_attachment", "index_record"}:
            if not self.confirm_change:
                raise UserError(_("Confirm the change to the specified record first."))
        started = monotonic()
        if op == "test_connection":
            response = client.test_connection()
        elif op == "list_records":
            params = self._json_object()
            if params.keys() - {"limit", "after", "source_id"}:
                raise UserError(_("List records only accepts limit, after and source_id."))
            response = client.list_records(**params)
        elif op == "create_record":
            response = client.create_record({"title": self.title, "text": self.record_text or "",
                                             "source_id": f"odoo-tester:{uuid4()}"}, key=uuid4())
        elif op == "get_record":
            response = client.get_record(rid)
        elif op == "update_record":
            response = client.update_record(rid, self._json_object())
        elif op == "archive_record":
            response = client.archive_record(rid)
        elif op == "add_attachment":
            if not self.upload or not self.upload_name:
                raise UserError(_("Choose an attachment first."))
            if len(self.upload) > (MAX_FILE + 2) // 3 * 4:
                raise UserError(_("The attachment exceeds 20 MiB."))
            response = client.add_attachment(rid, self.upload_name, base64.b64decode(self.upload),
                                             self.caption or "", key=uuid4())
        elif op == "download_attachment":
            response = client.download_attachment(rid, fid)
        elif op == "remove_attachment":
            response = client.remove_attachment(rid, fid)
        elif op == "index_record":
            response = client.index_record(rid, key=uuid4())
        elif op == "get_job_status":
            response = client.get_job_status(self.job_id)
        elif op == "search_records":
            response = client.search_records(self.question or "")
        else:
            response = client.ask_question(self.question or "")
        data = response["data"]
        values = {"confirm_change": False, "download": False, "curl_example": response.get("curl")}
        if 200 <= response["status"] < 300 and isinstance(data, dict):
            if op == "create_record":
                values.update(record_id=data["id"], operation="get_record")
            elif op == "add_attachment":
                values["file_id"] = data["id"]
            elif op == "index_record":
                values["job_id"] = data["id"]
        if "file" in response:
            values["download"] = base64.b64encode(response["file"])
        render = json.dumps(data, ensure_ascii=False, indent=2)
        values["result"] = f"HTTP {response['status']} · {monotonic() - started:.2f}s · {response['request_id']}\n\n{render[:40000]}"
        if len(render) > 40000:
            values["result"] += "\n[Output truncated]"
        self.write(values)
        return self._reopen()
