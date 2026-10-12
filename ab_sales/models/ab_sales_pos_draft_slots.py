# -*- coding: utf-8 -*-
"""Employee draft slots and cache reconciliation without invoice deletion."""
from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError


class AbSalesPosDraftSlots(models.TransientModel):
    _inherit = "ab_sales_pos_api"

    @api.model
    def pos_draft_store_options(self, pos_hr_session_token=None):
        """Use the same replica, employee and service-user branch permissions."""
        Header = self.env["ab_sales_header"]
        domain = fields.Domain("allow_sale", "=", True)
        allowed = Header._get_allowed_store_ids()
        if allowed:
            domain &= fields.Domain("id", "in", allowed)
        else:
            replica = self.env["ab_replica_db"].sudo().get_current_from_config()
            if replica and replica.allowed_sales_store_ids:
                # A configured list with no eligible branch is not unrestricted.
                domain &= fields.Domain("id", "in", [])
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
        return {"stores": stores.read(["name", "code", "ip1"]), "default_store_id": default_id}

    @api.model
    def _pos_draft_limit(self):
        raw = self.env["ir.config_parameter"].sudo().get_param("ab_sales.pos_draft_limit", "10")
        try:
            limit = int(raw)
        except (TypeError, ValueError):
            limit = 10
        return limit if limit > 0 else 10

    @api.model
    def _draft_id(self, bill):
        return str(bill.get("id") or (bill.get("header") or {}).get("pos_client_token") or "").strip()

    @api.model
    def _draft_timestamp(self, bill):
        try:
            value = datetime.fromisoformat(str(bill.get("updated_at") or bill.get("created_at") or "").replace("Z", "+00:00"))
            return value.replace(tzinfo=value.tzinfo or timezone.utc).timestamp()
        except (TypeError, ValueError, OverflowError):
            return 0

    @api.model
    def _draft_merge(self, *lists, removed=(), prefer_last_equal=True):
        result = {}
        for bills in lists:
            if not isinstance(bills, list):
                raise UserError(_("Invalid draft cache payload."))
            for bill in bills:
                if not isinstance(bill, dict) or not isinstance(bill.get("header"), dict):
                    raise UserError(_("Invalid draft cache payload."))
                store_id = bill["header"].get("store_id")
                token = bill["header"].get("pos_client_token")
                if store_id in (None, False):
                    store_id = None
                if (store_id is not None and (not isinstance(store_id, int) or isinstance(store_id, bool) or store_id <= 0)) or (
                        token is not None and (not isinstance(token, str) or len(token) > 128)):
                    raise UserError(_("Invalid draft cache payload."))
                identity = self._draft_id(bill)
                if not identity or identity in removed:
                    continue
                previous = result.get(identity)
                incoming_time = self._draft_timestamp(bill)
                previous_time = self._draft_timestamp(previous) if previous else 0
                if previous is None or incoming_time > previous_time or (prefer_last_equal and incoming_time == previous_time):
                    result[identity] = deepcopy(bill)
                    result[identity]["header"]["store_id"] = store_id
        return list(result.values())

    @api.model
    def _pos_slots_record(self, cache_key=None, employee_id=None, pos_hr_session_token=None):
        employee = self._pos_draft_employee(employee_id, pos_hr_session_token)
        if (employee_id or pos_hr_session_token) and not employee:
            raise AccessError(_("A valid employee session is required for draft bills."))
        Cache = self.env["ab_sales_pos_draft_cache"].sudo()
        records = Cache.search(fields.Domain("user_id", "=", self.env.uid)
                               & fields.Domain("employee_scope_key", "=", employee.id or 0), order="id")
        if records:
            # Serialize this employee's rows, not every cashier using a shared login.
            if len(records.try_lock_for_update()) != len(records):
                raise UserError(_("Draft cache is busy. Please try again."))
            records.invalidate_recordset()
        else:
            # First visits use a deterministic unique key; subsequent requests
            # lock the cache rows and remain independent of other employees.
            if not self.env.user.sudo().try_lock_for_update():
                raise UserError(_("Draft cache is busy. Please try again."))
            records = Cache.create({"user_id": self.env.uid, "employee_id": employee.id or False,
                                    "cache_key": self._pos_draft_cache_key()})
        # Cache keys are a browser detail, never a way to get another slot pool.
        record = records[:1]
        removed = set(item for row in records for item in (row.removed_bill_ids or []))
        bills = self._draft_merge(*(row.bills_json or [] for row in records), removed=removed)
        return record, bills, removed, employee

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
        replacements = []
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
                header._recover_interrupted_submission()
                if header.status in ("pending", "saved"):
                    completed.add(self._draft_id(bill))
                    replacements.append((bill, header.store_id))
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
        # A confirmed invoice becomes a new cache-only bill, never a copy of
        # the submitted customer's/contract's data or its idempotency token.
        occupied = sum(not bill["slot_locked"] for bill in prepared)
        for previous, store in replacements:
            if occupied >= self._pos_draft_limit():
                break  # Resolving a locked bill must not evict another draft.
            stamp = datetime.now(timezone.utc).isoformat()
            occupied_slots = {bill.get("slot_number") for bill in prepared if not bill["slot_locked"]}
            number = previous.get("slot_number") or previous.get("previous_slot_number")
            if number in occupied_slots or not isinstance(number, int) or not 1 <= number <= self._pos_draft_limit():
                number = next((slot for slot in range(1, self._pos_draft_limit() + 1)
                               if slot not in occupied_slots), None)
            prepared.append({
                "id": "bill-" + uuid4().hex, "local_number": str(int(datetime.now(timezone.utc).timestamp() * 1000)),
                "created_at": stamp, "updated_at": stamp,
                "slot_number": number,
                "completed_bill_id": self._draft_id(previous),
                "header": {"store_id": store.id, "store_name": store.name, "store_code": store.code,
                           "store_ip": store.ip1, "pos_client_token": "pos-" + uuid4().hex},
                "lines": [], "submission_status": "draft", "submission_can_edit": True,
                "submission_in_progress": False, "slot_locked": False, "slot_protected": False,
            })
            occupied += 1
        return prepared, completed

    @api.model
    def _draft_assign_slots(self, bills, limit):
        editable = sorted((bill for bill in bills if not bill["slot_locked"]),
                          key=lambda bill: (-self._draft_timestamp(bill), self._draft_id(bill)))
        chosen = editable[:limit]
        excess = editable[limit:]
        removed = {self._draft_id(bill) for bill in excess if not bill["slot_protected"]}
        kept = [bill for bill in bills if self._draft_id(bill) not in removed]
        used = set()
        for bill in chosen:
            number = bill.get("slot_number")
            if not isinstance(number, int) or isinstance(number, bool) or number < 1 or number > limit or number in used:
                bill["slot_number"] = None
            else:
                used.add(number)
        free = iter(number for number in range(1, limit + 1) if number not in used)
        for bill in chosen:
            if not bill.get("slot_number"):
                bill["slot_number"] = next(free)
        chosen_ids = {self._draft_id(bill) for bill in chosen}
        for bill in kept:
            bill["slot_waiting"] = not bill["slot_locked"] and self._draft_id(bill) not in chosen_ids
            if bill["slot_locked"] or bill["slot_waiting"]:
                if bill.get("slot_number"):
                    bill["previous_slot_number"] = bill["slot_number"]
                bill["slot_number"] = None
        return kept, removed

    @api.model
    def _draft_store_result(self, record, bills, removed, employee, selected_id=None, rejected=()):
        bills = sorted(bills, key=lambda bill: (-self._draft_timestamp(bill), self._draft_id(bill)))
        selected = str(selected_id or record.selected_id or "")
        replacements = {}
        for bill in bills:
            previous_id = bill.pop("completed_bill_id", None)
            if previous_id:
                replacements[previous_id] = self._draft_id(bill)
            if previous_id and previous_id == selected:
                selected = self._draft_id(bill)
        if selected not in {self._draft_id(bill) for bill in bills}:
            selected = self._draft_id(bills[0]) if bills else ""
        # Empty slots have no branch. Only Ready/Used bills remember a branch.
        slot_stores = {}
        for bill in bills:
            if bill.get("slot_number") and bill["header"].get("store_id"):
                slot_stores[str(bill["slot_number"])] = bill["header"]["store_id"]
        values = {"bills_json": bills, "removed_bill_ids": sorted(removed), "selected_id": selected,
                  "slot_store_ids": slot_stores}
        current = {"bills_json": record.bills_json or [], "removed_bill_ids": record.removed_bill_ids or [],
                   "selected_id": record.selected_id or "", "slot_store_ids": record.slot_store_ids or {}}
        if current != values:
            values.update(cache_revision=record.cache_revision + 1, last_synced_at=fields.Datetime.now())
            record.write(values)
        # Older browser keys can have separate rows for the same employee.
        # Consolidate their bills into the canonical row, including deletions.
        secondary = self.env["ab_sales_pos_draft_cache"].sudo().search(
            fields.Domain("user_id", "=", record.user_id.id)
            & fields.Domain("employee_scope_key", "=", record.employee_scope_key)
            & fields.Domain("id", "!=", record.id))
        if secondary:
            secondary.write({"bills_json": [], "selected_id": "", "removed_bill_ids": sorted(removed),
                             "cache_revision": record.cache_revision,
                             "last_synced_at": record.last_synced_at})
        stores = self.env["ab_store"].search(fields.Domain("id", "in", list(set(slot_stores.values()))))
        allowed = self.env["ab_sales_header"]._get_allowed_store_ids()
        by_id = {store.id: {"id": store.id, "name": store.name, "code": store.code}
                 for store in stores if not allowed or store.id in allowed}
        branches = {number: by_id[store_id] for number, store_id in slot_stores.items() if store_id in by_id}
        return {"slot_branches": branches, "cache_key": record.cache_key, "employee_id": employee.id or False,
                "bills": self._pos_draft_cache_with_product_pricing_flags(deepcopy(bills)),
                "selected_id": selected, "last_synced_at": record.last_synced_at,
                "updated_at": record.write_date, "revision": record.cache_revision,
                "removed_ids": sorted(removed), "rejected_ids": list(rejected),
                "draft_limit": self._pos_draft_limit(), "count": len(bills),
                "replacements": replacements}

    @api.model
    def pos_restore_draft_cache(self, bill_id=None, cache_key=None, employee_id=None,
                                pos_hr_session_token=None):
        """Revalidate one existing draft in the caller's employee/branch scope."""
        if not isinstance(bill_id, str) or not bill_id:
            raise UserError(_("Invalid draft cache payload."))
        result = self.pos_load_draft_cache(cache_key=cache_key, employee_id=employee_id,
                                          pos_hr_session_token=pos_hr_session_token)
        bill = next((bill for bill in result["bills"] if self._draft_id(bill) == bill_id), None)
        if not bill:
            raise UserError(_("This draft is no longer available. Refresh the draft list."))
        if bill.get("slot_locked") or bill.get("submission_can_edit") is False:
            raise UserError(_("This draft has an unresolved submission and cannot be restored."))
        result["bills"] = [bill]
        return result

    @api.model
    def pos_load_draft_cache(self, cache_key=None, employee_id=None, pos_hr_session_token=None,
                             bills=None, selected_id=None):
        record, cached, removed, employee = self._pos_slots_record(cache_key, employee_id, pos_hr_session_token)
        merged = self._draft_merge(cached, bills or [], removed=removed)
        merged, completed = self._draft_authoritative_states(merged)
        merged, excess = self._draft_assign_slots(merged, self._pos_draft_limit())
        return self._draft_store_result(record, merged, removed | completed | excess, employee, selected_id)

    @api.model
    def pos_save_draft_cache(self, cache_key=None, bills=None, selected_id=None, employee_id=None,
                             pos_hr_session_token=None, revision=None):
        if not isinstance(bills, list):
            raise UserError(_("Invalid draft cache payload."))
        record, cached, removed, employee = self._pos_slots_record(cache_key, employee_id, pos_hr_session_token)
        stale_revision = revision is not None and revision != record.cache_revision
        cached, completed = self._draft_authoritative_states(cached)
        cached, excess = self._draft_assign_slots(cached, self._pos_draft_limit())
        removed |= completed | excess
        incoming = self._draft_merge(bills, removed=removed)
        incoming, completed = self._draft_authoritative_states(incoming)
        removed |= completed
        existing_ids = {self._draft_id(bill) for bill in cached}
        additions = [bill for bill in incoming if self._draft_id(bill) not in existing_ids]
        occupied = sum(not bill["slot_locked"] and not bill["slot_waiting"] for bill in cached)
        rejected = set()
        for bill in additions:
            if not bill["slot_locked"] and not bill["slot_protected"]:
                if occupied >= self._pos_draft_limit():
                    rejected.add(self._draft_id(bill))
                else:
                    occupied += 1
        incoming = [bill for bill in incoming if self._draft_id(bill) not in rejected]
        merged = self._draft_merge(cached, incoming, removed=removed, prefer_last_equal=not stale_revision)
        # Revision identifies stale snapshots; merge preserves omitted server bills.
        # Deletion exclusively uses pos_remove_draft_cache and permanent tombstones.
        merged, excess = self._draft_assign_slots(merged, self._pos_draft_limit())
        result = self._draft_store_result(record, merged, removed | excess, employee, selected_id, rejected)
        result["stale_revision"] = stale_revision
        return result

    @api.model
    def pos_remove_draft_cache(self, bill_ids=None, cache_key=None, employee_id=None,
                               pos_hr_session_token=None, revision=None):
        if not isinstance(bill_ids, list) or any(not isinstance(item, str) for item in bill_ids):
            raise UserError(_("Invalid draft cache payload."))
        record, cached, removed, employee = self._pos_slots_record(cache_key, employee_id, pos_hr_session_token)
        if revision is not None and revision != record.cache_revision:
            raise UserError(_("Drafts changed in another tab. Reload and try again."))
        cached, completed = self._draft_authoritative_states(cached)
        candidates = []
        for bill in cached:
            if self._draft_id(bill) not in bill_ids or bill.get("submission_checking") or bill.get("submission_in_progress"):
                continue
            if bill["slot_protected"]:
                payload = bill.get("submission_payload")
                # Preserve unsaved/current lines and original submission work,
                # even when the associated invoice happens to have no lines.
                if bill.get("lines") or (payload is not None and
                        (not isinstance(payload, dict) or not isinstance(payload.get("lines"), list) or payload["lines"])):
                    continue
            candidates.append(bill)
        requests = [{"token": bill["header"].get("pos_client_token"), "store_id": bill["header"].get("store_id")}
                    for bill in candidates if bill["slot_protected"]]
        eligible = {}
        for start in range(0, len(requests), 200):
            eligible.update(self.pos_check_draft_discard(requests[start:start + 200]))
        deleted = {self._draft_id(bill) for bill in candidates
                   if not bill["slot_protected"] or eligible.get(bill["header"].get("pos_client_token"))}
        # Mark absent requested ids too: another stale tab must not restore them.
        known_ids = {self._draft_id(bill) for bill in cached}
        deleted |= set(bill_ids) - known_ids
        kept, excess = self._draft_assign_slots([bill for bill in cached if self._draft_id(bill) not in deleted],
                                               self._pos_draft_limit())
        result = self._draft_store_result(record, kept, removed | completed | deleted | excess, employee)
        result["deleted_ids"] = sorted(deleted)
        result["retained_count"] = len(set(bill_ids) - deleted - completed)
        return result
