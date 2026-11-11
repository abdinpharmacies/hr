# -*- coding: utf-8 -*-
"""Employee draft slots and cache reconciliation without invoice deletion."""
from copy import deepcopy
from psycopg2.errors import UniqueViolation

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError


class AbSalesPosDraftSlots(models.TransientModel):
    _inherit = "ab_sales_pos_api"

    @api.model
    def pos_draft_store_options(self, pos_hr_session_token=None):
        """Use the same replica, employee and service-user branch permissions."""
        Header = self.env["ab_sales_header"]
        domain = Header._get_allowed_store_domain()
        stores = self.env["ab_store"].search(domain, order="id")
        if "ab_employee_access_sales_pos_api" in self.env.registry:
            session_api = self.env["ab_employee_access_sales_pos_api"]
            session = session_api._get_session(pos_hr_session_token, states=["active"], required=True)
            if session.service_user_id.id != self.env.uid:
                raise AccessError(_("A valid employee session is required for draft bills."))
            profile = session._get_pos_profile()
            if not profile:
                raise AccessError(_("A valid employee session is required for draft bills."))
            permitted = session_api._available_stores_for_profile(profile)
            permitted_ids = set(permitted.ids)
            stores = stores.filtered(lambda store: store.id in permitted_ids)
        default_id = Header._get_default_store_id()
        if default_id not in stores.ids:
            default_id = stores[:1].id or False
        return {"stores": stores.read(["name", "code", "ip1"]), "default_store_id": default_id,
                "draft_limit": self._pos_draft_limit()}

    @api.model
    def _pos_draft_limit(self):
        raw = self.env["ir.config_parameter"].sudo().get_param("ab_sales.pos_draft_limit", "10")
        try:
            limit = int(raw)
        except (TypeError, ValueError):
            limit = 10
        return limit if limit > 0 else 10

    @api.model
    def _draft_authoritative_states(self, bills):
        """Resolve locks without trusting a client-provided pending/saved status."""
        tokens = {(bill.get("header") or {}).get("pos_client_token") for bill in bills}
        tokens.discard(None)
        tokens.discard("")
        headers = self.env["ab_sales_header"].with_context(active_test=False)
        found = headers.sudo().search(fields.Domain("pos_client_token", "in", list(tokens)))
        by_token = {header.pos_client_token: header.id for header in found}
        allowed = headers._get_allowed_store_ids()
        store_ids = {bill["header"].get("store_id") for bill in bills} | set(found.mapped("store_id").ids)
        stores = self.env["ab_store"].search(fields.Domain("id", "in", list(store_ids - {None, False})))
        readable = set(stores.ids)
        prepared = []
        completed = set()
        for bill in bills:
            store_id = bill["header"].get("store_id")
            if store_id and (store_id not in readable or (allowed and store_id not in allowed)):
                raise AccessError(_("You cannot access the branch of this draft bill."))
            token = bill["header"].get("pos_client_token")
            header_id = by_token.get(token)
            if header_id:
                header = headers.browse(header_id)
                header.check_access("read")
                if not store_id:
                    # A persisted invoice supplies its own authoritative branch.
                    store_id = header.store_id.id
                    if store_id not in readable or (allowed and store_id not in allowed):
                        raise AccessError(_("You cannot access the branch of this draft bill."))
                    bill["header"]["store_id"] = store_id
                if header.store_id.id != store_id:
                    raise AccessError(_("The draft bill branch does not match its invoice."))
                # Recovery belongs to the submission-status API, not cache reads.
                if header.status in ("pending", "saved"):
                    completed.add(self._draft_id(bill))
                    continue
                payload = self._pos_submission_payload(header)
                bill.update({"odoo_header_id": header.id, "submission_status": header.status,
                             "submission_can_edit": payload["can_edit"],
                             "submission_in_progress": payload["submission_in_progress"],
                             "submission_checking": False, "eplus_serial": header.eplus_serial})
                bill["slot_locked"] = not payload["can_edit"] or payload["submission_in_progress"]
                bill["slot_protected"] = True
            else:
                # A lost response can precede the transaction becoming visible.
                unresolved = bool(bill.get("submission_attempted") and not bill.get("submission_validation_failed"))
                bill["slot_locked"] = unresolved or bool(bill.get("odoo_header_id"))
                bill["slot_protected"] = bill["slot_locked"]
                bill["submission_checking"] = bill["slot_locked"]
                if not bill["slot_locked"]:
                    bill["submission_status"] = "draft"
                    bill["submission_can_edit"] = True
                    bill["submission_in_progress"] = False
            prepared.append(bill)
        return prepared, completed

    @api.model
    def _draft_id(self, bill):
        header = bill.get("header")
        return str(header.get("pos_client_token") or "").strip() if isinstance(header, dict) else ""

    @api.model
    def _draft_has_data(self, bill):
        defaults = {"store_id", "store_name", "store_code", "store_ip", "pos_client_token",
                    "customer_mode", "contract_total_invoice_discount_source", "delivery_ui_version"}
        promo = bill.get("promo") or {}
        return bool(bill.get("lines") or promo.get("applied_id") or promo.get("selected_id") or any(
            (bool(value.strip()) if isinstance(value, str) else bool(value))
            for key, value in bill["header"].items() if key not in defaults))

    @api.model
    def _draft_scope(self, employee_id=None, pos_hr_session_token=None):
        if hasattr(self, "_raise_sales_prevented"):
            self._raise_sales_prevented()
        employee = self._pos_draft_employee(employee_id, pos_hr_session_token)
        if employee_id or pos_hr_session_token:
            if not employee:
                raise AccessError(_("A valid employee session is required for draft bills."))
        if not employee:
            return employee, set()
        # Reuse employee profile, replica and service-user branch validation.
        options = self.pos_draft_store_options(pos_hr_session_token=pos_hr_session_token)
        return employee, {store["id"] for store in options["stores"]}

    @api.model
    def _draft_records(self, employee, stores, tokens=None, active_only=False):
        if not employee:
            return self.env["ab_sales_pos_draft_cache"]
        domain = (fields.Domain("user_id", "=", self.env.uid)
                  & fields.Domain("employee_id", "=", employee.id or False)
                  & fields.Domain("store_id", "in", list(stores)))
        if tokens is not None:
            domain &= fields.Domain("pos_client_token", "in", tokens)
        if active_only:
            domain &= fields.Domain("state", "=", "active")
        return self.env["ab_sales_pos_draft_cache"].sudo().search(domain)

    @api.model
    def _draft_check_owner(self, record, employee, stores):
        if record and (record.user_id.id != self.env.uid or record.employee_id != employee
                       or record.store_id.id not in stores):
            raise AccessError(_("You cannot access this draft bill."))

    @api.model
    def _draft_payload(self, raw, stores):
        if (not isinstance(raw, dict) or not isinstance(raw.get("header"), dict)
                or not isinstance(raw.get("lines", []), list) or not isinstance(raw.get("promo", {}), dict)
                or any(not isinstance(line, dict) for line in raw.get("lines", []))):
            raise UserError(_("Invalid draft cache payload."))
        if not isinstance(raw["header"].get("pos_client_token"), str):
            raise UserError(_("Invalid draft cache payload."))
        bill = deepcopy(raw)
        token = self._draft_id(bill)
        store = bill["header"].get("store_id")
        if not token or len(token) > 128 or not isinstance(store, int) or isinstance(store, bool) or store not in stores:
            raise AccessError(_("Invalid draft identity or branch."))
        bill["id"] = token
        bill["header"]["pos_client_token"] = token
        for key in ("draft_revision", "slot_number", "previous_slot_number", "slot_waiting", "backup_status"):
            bill.pop(key, None)
        return bill

    @api.model
    def _draft_content(self, bill):
        # Match the browser's volatile-field exclusions: refreshing stock or
        # rendering prices must not advance the cashier's edit revision.
        transient = {"updated_at", "slot_locked", "slot_protected", "submission_checking",
                     "submission_can_edit", "submission_in_progress", "submission_status",
                     "draft_revision", "backup_status", "slot_number", "slot_waiting", "previous_slot_number",
                     "available_prices_html", "available_prices", "available_prices_base", "inventory_table_html", "inventory_json",
                     "show_details", "loading_details", "balance", "balance_total", "available", "loading"}

        def content(value):
            if isinstance(value, dict):
                return {key: content(item) for key, item in value.items()
                        if key not in transient and key != "pos_balance" and not key.startswith("pos_balance_")}
            if isinstance(value, list):
                return [content(item) for item in value]
            return value
        return content(bill)

    @api.model
    def _draft_result(self, employee, records=(), outcomes=(), selected_id=None):
        bills, removed, revisions = [], [], {}
        for record in records:
            revisions[record.pos_client_token] = record.revision
            if record.state != "active":
                removed.append(record.pos_client_token)
                continue
            bill = deepcopy(record.bill_json)
            bill["draft_revision"] = record.revision
            bills.append(bill)
        return {"employee_id": employee.id or False, "bills": bills,
                "selected_id": selected_id or "", "draft_limit": self._pos_draft_limit(),
                "revision": revisions, "removed_ids": removed, "rejected_ids": [
                    item["token"] for item in outcomes if item["status"] == "capacity"],
                "outcomes": list(outcomes), "replacements": {}, "slot_branches": {}, "count": len(bills),
                "completed_ids": [row.pos_client_token for row in records if row.state == "completed"]}

    @api.model
    def pos_load_draft_cache(self, cache_key=None, employee_id=None, pos_hr_session_token=None):
        employee, stores = self._draft_scope(employee_id, pos_hr_session_token)
        records = self._draft_records(employee, stores, active_only=True)
        # Listing is read-only: no pool row or locks, and no automatic import.
        result = self._draft_result(employee, records)
        prepared, completed = self._draft_authoritative_states(result["bills"])
        result["bills"] = prepared
        result["removed_ids"] += list(completed)
        result["completed_ids"] += list(completed)
        return result

    @api.model
    def pos_draft_workspace(self, tokens=None, cache_key=None, employee_id=None, pos_hr_session_token=None):
        """Reconcile only this browser's known tokens; never pull other workspaces."""
        employee, stores = self._draft_scope(employee_id, pos_hr_session_token)
        if not isinstance(tokens, list) or any(not isinstance(token, str) for token in tokens):
            raise UserError(_("Invalid draft cache payload."))
        records = self.env["ab_sales_pos_draft_cache"].sudo().search(
            fields.Domain("user_id", "=", self.env.uid)
            & fields.Domain("employee_id", "=", employee.id or False)
            & fields.Domain("store_id", "in", list(stores))
            & fields.Domain("pos_client_token", "in", tokens))
        result = self._draft_result(employee, records)
        result["bills"], completed = self._draft_authoritative_states(result["bills"])
        result["completed_ids"] += list(completed)
        result["removed_ids"] += list(completed)
        return result

    @api.model
    def pos_restore_draft_cache(self, bill_id=None, cache_key=None, employee_id=None, pos_hr_session_token=None):
        employee, stores = self._draft_scope(employee_id, pos_hr_session_token)
        if not employee:
            return self._draft_result(employee)
        record = self.env["ab_sales_pos_draft_cache"].sudo().search(
            fields.Domain("pos_client_token", "=", str(bill_id or "")), limit=1)
        self._draft_check_owner(record, employee, stores)
        if not record or record.state != "active":
            raise UserError(_("This draft is no longer available. Refresh the draft list."))
        result = self._draft_result(employee, record)
        prepared, completed = self._draft_authoritative_states(result["bills"])
        if completed or not prepared or prepared[0].get("slot_locked"):
            raise UserError(_("This draft has an unresolved submission and cannot be restored."))
        result["bills"] = self._pos_draft_cache_with_product_pricing_flags(prepared)
        return result

    @api.model
    def _draft_save_one(self, raw, employee, stores):
        reason = self.env["ab_sales_pos_draft_cache"]._payload_invalid_reason(raw)
        if not employee or reason:
            return {"token": (self._draft_id(raw) or str(raw.get("id") or "")) if isinstance(raw, dict) else "",
                    "status": "skipped", "reason": reason or "missing_employee_id"}
        bill = self._draft_payload(raw, stores)
        token = self._draft_id(bill)
        Header = self.env["ab_sales_header"].sudo()
        invoice = Header.search(fields.Domain("pos_client_token", "=", token), limit=1)
        if invoice and "pos_hr_employee_id" in Header._fields and invoice.pos_hr_employee_id and (
                invoice.pos_hr_employee_id != employee or invoice.pos_hr_service_user_id.id != self.env.uid):
            raise AccessError(_("You cannot access this draft bill."))
        Cache = self.env["ab_sales_pos_draft_cache"].sudo()
        record = Cache.search(fields.Domain("pos_client_token", "=", token), limit=1)
        self._draft_check_owner(record, employee, stores)
        if record:
            if not record.try_lock_for_update():
                return {"token": token, "status": "busy"}
            record.invalidate_recordset()
            if record.state != "active":
                return {"token": token, "status": record.state, "revision": record.revision}
        prepared, completed = self._draft_authoritative_states([bill])
        if completed:
            if record:
                record.write({"state": "completed", "revision": record.revision + 1})
            return {"token": token, "status": "completed", "revision": record.revision if record else 0}
        bill = prepared[0]
        meaningful = self._draft_has_data(bill) or bill["slot_protected"]
        if record and meaningful and self._draft_content(record.bill_json) == self._draft_content(bill):
            return {"token": token, "status": "unchanged", "revision": record.revision}
        if record and raw.get("draft_revision") != record.revision:
            return {"token": token, "status": "conflict", "revision": record.revision,
                    "bill": deepcopy(record.bill_json)}
        if not meaningful:
            if record:
                record.write({"state": "retired", "revision": record.revision + 1})
            return {"token": token, "status": "retired" if record else "ready",
                    "revision": record.revision if record else 0}
        values = {"bill_json": bill, "store_id": bill["header"]["store_id"],
                  "last_synced_at": fields.Datetime.now()}
        if record:
            record.write(dict(values, revision=record.revision + 1))
        else:
            # Admission alone needs an employee-wide lock; edits lock one draft.
            Scope = self.env["ab_sales_pos_draft_scope"].sudo()
            domain = fields.Domain("user_id", "=", self.env.uid) & fields.Domain("employee_key", "=", employee.id or 0)
            scope_record = Scope.search(domain, limit=1)
            if not scope_record:
                try:
                    with self.env.cr.savepoint():
                        scope_record = Scope.create({"user_id": self.env.uid, "employee_key": employee.id or 0})
                except UniqueViolation as error:
                    if "uniq_owner" not in (error.diag.constraint_name or ""):
                        raise
                    return {"token": token, "status": "busy"}
            if not scope_record.try_lock_for_update():
                return {"token": token, "status": "busy"}
            scope_record.invalidate_recordset()
            # Updating the marker makes stale repeatable-read snapshots retry;
            # a lock alone cannot protect a count read from an older snapshot.
            scope_record.write({"revision": scope_record.revision + 1})
            active = Cache.search(fields.Domain("user_id", "=", self.env.uid)
                                  & fields.Domain("employee_id", "=", employee.id or False)
                                  & fields.Domain("state", "=", "active"))
            active_bills, _completed = self._draft_authoritative_states([
                deepcopy(row.bill_json) for row in active if row.store_id.id in stores])
            occupied = sum(not value.get("slot_locked") for value in active_bills)
            # Drafts in no-longer-permitted branches still consume shared capacity.
            occupied += len(active.filtered(lambda row: row.store_id.id not in stores))
            if not bill["slot_locked"] and occupied >= self._pos_draft_limit():
                return {"token": token, "status": "capacity"}
            try:
                with self.env.cr.savepoint():
                    record = Cache.create(dict(values, pos_client_token=token, user_id=self.env.uid,
                                               employee_id=employee.id or False))
            except UniqueViolation as error:
                if "uniq_pos_client_token" not in (error.diag.constraint_name or ""):
                    raise
                record = Cache.search(fields.Domain("pos_client_token", "=", token), limit=1)
                if not record:
                    return {"token": token, "status": "busy"}
                return self._draft_save_one(raw, employee, stores)
        return {"token": token, "status": "saved", "revision": record.revision}

    @api.model
    def pos_save_draft_cache(self, cache_key=None, bills=None, selected_id=None, employee_id=None,
                             pos_hr_session_token=None, revision=None):
        employee, stores = self._draft_scope(employee_id, pos_hr_session_token)
        if not isinstance(bills, list):
            raise UserError(_("Invalid draft cache payload."))
        outcomes = []
        for bill in bills:
            # A rejected item never rolls back another item's successful backup.
            try:
                with self.env.cr.savepoint():
                    outcomes.append(self._draft_save_one(bill, employee, stores))
            except (AccessError, UserError) as error:
                outcomes.append({"token": self._draft_id(bill) if isinstance(bill, dict) else "",
                                 "status": "error", "message": str(error)})
        tokens = [item["token"] for item in outcomes if item["status"] in ("saved", "unchanged", "retired", "completed")]
        records = self._draft_records(employee, stores, tokens=tokens)
        return self._draft_result(employee, records, outcomes, selected_id)

    @api.model
    def pos_remove_draft_cache(self, bill_ids=None, cache_key=None, employee_id=None,
                               pos_hr_session_token=None, revision=None):
        employee, stores = self._draft_scope(employee_id, pos_hr_session_token)
        if not employee:
            return self._draft_result(employee)
        if not isinstance(bill_ids, list) or any(not isinstance(token, str) for token in bill_ids):
            raise UserError(_("Invalid draft cache payload."))
        revisions = revision if isinstance(revision, dict) else {}
        Cache = self.env["ab_sales_pos_draft_cache"].sudo()
        deleted, outcomes = [], []
        for token in bill_ids:
            record = Cache.search(fields.Domain("pos_client_token", "=", token), limit=1)
            self._draft_check_owner(record, employee, stores)
            if not record:
                # Never manufacture a tombstone for an unowned token.
                continue
            if not record.try_lock_for_update():
                outcomes.append({"token": token, "status": "busy"})
                continue
            record.invalidate_recordset()
            if record.state != "active":
                deleted.append(token)
                continue
            if revisions.get(token) != record.revision:
                outcomes.append({"token": token, "status": "conflict", "revision": record.revision,
                                 "bill": deepcopy(record.bill_json)})
                continue
            prepared, completed = self._draft_authoritative_states([deepcopy(record.bill_json)])
            protected = prepared and prepared[0].get("slot_protected")
            if protected:
                outcomes.append({"token": token, "status": "protected"})
                continue
            record.write({"state": "completed" if completed else "retired", "revision": record.revision + 1})
            deleted.append(token)
        result = self._draft_result(employee, self._draft_records(employee, stores, active_only=True), outcomes=outcomes)
        result.update(deleted_ids=deleted, removed_ids=deleted, retained_count=len(set(bill_ids) - set(deleted)))
        return result
