import json
import time
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AbDrugEgImportDashboard(models.Model):
    _name = "ab.drug.eg.import.dashboard"
    _description = "Drug-EG Import Dashboard"

    STATE_KEY = "ab_website_seo_optimization.drug_eg_import_state"
    DEFAULT_API_URL = "https://ready-api.vercel.app/api/drugs-eg"
    DEFAULT_TOTAL_PRODUCTS = 25070

    name = fields.Char(default="Drug-EG Import Dashboard", required=True)
    api_url = fields.Char(default=DEFAULT_API_URL, required=True)
    page_size = fields.Integer(default=100, required=True)
    max_requests_per_run = fields.Integer(default=290, required=True)
    request_delay_seconds = fields.Float(default=0.25)
    all_drugs = fields.Integer(default=DEFAULT_TOTAL_PRODUCTS, readonly=True)
    imported_count = fields.Integer(compute="_compute_status")
    remaining_count = fields.Integer(compute="_compute_status")
    last_checkpoint_at = fields.Datetime(compute="_compute_status")
    next_page = fields.Integer(compute="_compute_status")
    request_count = fields.Integer(compute="_compute_status")
    done = fields.Boolean(compute="_compute_status")
    last_message = fields.Text(readonly=True)

    @api.depends("all_drugs")
    def _compute_status(self):
        DrugData = self.env["ab.product.drug.data"].sudo()
        for dashboard in self:
            state = dashboard._load_state()
            imported_count = DrugData.search_count([("active", "=", True)])
            dashboard.imported_count = imported_count
            dashboard.remaining_count = max((dashboard.all_drugs or 0) - imported_count, 0)
            dashboard.last_checkpoint_at = state.get("last_checkpoint_at") or False
            dashboard.next_page = int(state.get("next_page") or 1)
            dashboard.request_count = int(state.get("request_count") or 0)
            dashboard.done = bool(state.get("done"))

    def action_start_import(self):
        self.ensure_one()
        self._save_state(self._make_initial_state())
        return self._run_import_from_checkpoint()

    def action_continue_import(self):
        self.ensure_one()
        return self._run_import_from_checkpoint()

    def action_check_checkpoint(self):
        self.ensure_one()
        state = self._load_state()
        message = _(
            "Checkpoint: next page %(page)s, imported rows %(rows)s, requests %(requests)s, done: %(done)s."
        ) % {
            "page": state.get("next_page") or 1,
            "rows": state.get("total_rows") or 0,
            "requests": state.get("request_count") or 0,
            "done": bool(state.get("done")),
        }
        self.last_message = message
        return self._reload_with_notification(_("Drug-EG Checkpoint"), message, "info")

    def _run_import_from_checkpoint(self):
        self.ensure_one()
        state = self._load_state()
        if state.get("done"):
            return self._reload_with_notification(
                _("Drug-EG Import"),
                _("Drug-EG import is already complete. Use Start Import to reset and import again."),
                "success",
            )
        assistant = self._get_ready_api_assistant()
        api_key = assistant.api_key
        page_size = min(max(self.page_size or 100, 1), 100)
        page = int(state.get("next_page") or 1)
        total = int(state.get("total_rows") or 0)
        request_count = int(state.get("request_count") or 0)
        requests_this_run = 0
        DrugData = self.env["ab.product.drug.data"].sudo()
        try:
            while True:
                if self.max_requests_per_run and requests_this_run >= self.max_requests_per_run:
                    message = _("Stopped at the per-run request limit. Continue later to resume from page %s.") % page
                    self.last_message = message
                    return self._reload_with_notification(_("Drug-EG Import Paused"), message, "warning")
                source_url, payload = self._fetch_page(api_key, page, page_size)
                requests_this_run += 1
                request_count += 1
                items = self._extract_items(payload)
                if not items:
                    state.update({
                        "done": True,
                        "request_count": request_count,
                        "last_page": page,
                        "last_page_rows": 0,
                        "last_checkpoint_at": fields.Datetime.to_string(fields.Datetime.now()),
                    })
                    self._save_state(state)
                    self.env.cr.commit()
                    break
                for item in items:
                    DrugData.upsert_from_drug_eg_item(item, source_url=source_url)
                    total += 1
                state.update({
                    "next_page": page + 1,
                    "total_rows": total,
                    "request_count": request_count,
                    "done": not self._payload_has_more(payload, len(items), page_size),
                    "last_page": page,
                    "last_page_rows": len(items),
                    "last_checkpoint_at": fields.Datetime.to_string(fields.Datetime.now()),
                })
                self._save_state(state)
                self.last_message = _("Imported page %(page)s with %(rows)s rows. Next page: %(next_page)s.") % {
                    "page": page,
                    "rows": len(items),
                    "next_page": page + 1,
                }
                self.env.cr.commit()
                if state["done"]:
                    break
                page += 1
                if self.request_delay_seconds and self.request_delay_seconds > 0:
                    time.sleep(self.request_delay_seconds)
        except UserError:
            raise
        except Exception as error:
            raise UserError(_("Drug-EG import stopped. Continue later after resolving this error: %s") % error) from error
        return self._reload_with_notification(
            _("Drug-EG Import Finished" if state.get("done") else "Drug-EG Import Paused"),
            self.last_message or _("Drug-EG import checkpoint was updated."),
            "success" if state.get("done") else "warning",
        )

    def _get_ready_api_assistant(self):
        assistant = self.env["ab.seo.assistant"].sudo().search([
            ("provider", "=", "ready_api"),
            ("assistant_type", "=", "data_source"),
            ("active", "=", True),
            ("api_key", "!=", False),
        ], limit=1, order="sequence, id")
        if not assistant:
            raise UserError(_("Configure the Ready API key under SEO Optimization > Settings > Data Sources before importing."))
        return assistant

    def _fetch_page(self, api_key, page, page_size):
        query = {
            "page": page,
            "limit": page_size,
        }
        url = "%s?%s" % ((self.api_url or self.DEFAULT_API_URL).rstrip("/"), urlencode(query))
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "Authorization": "Bearer %s" % api_key,
                "User-Agent": "ab-website-seo-optimization-drug-eg-import/19.0",
            },
            method="GET",
        )
        try:
            with urlopen(request, timeout=30) as response:
                return url, json.loads(response.read().decode("utf-8") or "{}")
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")[:500]
            if error.code == 401:
                raise UserError(_("Ready API rejected the API key. Details: %s") % detail) from error
            if error.code == 429:
                raise UserError(_("Ready API rate limit was exceeded. Continue later after quota reset. Details: %s") % detail) from error
            raise UserError(_("Ready API returned HTTP %(code)s. Details: %(detail)s") % {
                "code": error.code,
                "detail": detail,
            }) from error

    def _extract_items(self, payload):
        if isinstance(payload, list):
            return payload
        if not isinstance(payload, dict):
            return []
        for key in ("data", "items", "results", "drugs", "products", "all_products", "All_products"):
            values = payload.get(key)
            if isinstance(values, list):
                return values
        nested_products = []
        for key in ("ingredients", "active_ingredients", "all_data", "All Data"):
            values = payload.get(key)
            if not isinstance(values, list):
                continue
            for ingredient in values:
                if not isinstance(ingredient, dict):
                    continue
                ingredient_name = self._first_present(ingredient, "name", "ingredient", "scientific_name", "active_ingredient")
                category = self._first_present(ingredient, "category", "therapeutic_category")
                for product_key in ("products", "items", "drugs"):
                    products = ingredient.get(product_key)
                    if not isinstance(products, list):
                        continue
                    for product in products:
                        if isinstance(product, dict):
                            product = dict(product)
                            product.setdefault("scientific_name", ingredient_name)
                            product.setdefault("active_ingredient", ingredient_name)
                            product.setdefault("category", category)
                            nested_products.append(product)
            if nested_products:
                return nested_products
        return []

    def _payload_has_more(self, payload, item_count, page_size):
        if isinstance(payload, dict) and isinstance(payload.get("pagination"), dict):
            pagination = payload["pagination"]
            if "hasMore" in pagination:
                return bool(pagination.get("hasMore"))
            if "totalPages" in pagination and "page" in pagination:
                try:
                    return int(pagination["page"]) < int(pagination["totalPages"])
                except (TypeError, ValueError):
                    pass
        return item_count >= page_size

    def _first_present(self, data, *keys):
        for key in keys:
            value = data.get(key) if isinstance(data, dict) else None
            if value not in (None, False, "", []):
                return str(value)
        return False

    def _make_initial_state(self):
        return {
            "api_url": self.api_url or self.DEFAULT_API_URL,
            "page_size": min(max(self.page_size or 100, 1), 100),
            "next_page": 1,
            "total_rows": 0,
            "request_count": 0,
            "done": False,
            "last_page": 0,
            "last_page_rows": 0,
            "last_checkpoint_at": False,
        }

    def _load_state(self):
        raw_state = self.env["ir.config_parameter"].sudo().get_param(self.STATE_KEY)
        if not raw_state:
            return self._make_initial_state()
        try:
            return json.loads(raw_state)
        except json.JSONDecodeError:
            return self._make_initial_state()

    def _save_state(self, state):
        self.env["ir.config_parameter"].sudo().set_param(self.STATE_KEY, json.dumps(state, sort_keys=True))

    def _reload_with_notification(self, title, message, notification_type):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Drug-EG Import Dashboard"),
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
            "context": {
                "params": {
                    "next": {
                        "type": "ir.actions.client",
                        "tag": "display_notification",
                        "params": {
                            "title": title,
                            "message": message,
                            "type": notification_type,
                            "sticky": notification_type != "success",
                        },
                    }
                }
            },
        }
