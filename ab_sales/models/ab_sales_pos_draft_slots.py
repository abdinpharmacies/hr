# -*- coding: utf-8 -*-
"""Employee draft slots and cache reconciliation without invoice deletion."""
from copy import deepcopy
from uuid import uuid4
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
        """Use durable callcenter state, never browser flags, to unlock a bill."""
        Header = self.env['ab_sales_header'].with_context(active_test=False)
        tokens = [self._draft_id(bill) for bill in bills]
        found = Header.sudo().search(fields.Domain('pos_client_token', 'in', tokens))
        by_token = {record.pos_client_token: Header.browse(record.id) for record in found}
        prepared, completed = [], set()
        for bill in bills:
            header = by_token.get(self._draft_id(bill))
            submission = bill.get('submission') or {}
            if not isinstance(submission, dict):
                raise UserError(_('Invalid draft cache payload.'))
            if header:
                header.check_access('read')
                if header.create_uid != self.env.user:
                    raise AccessError(_('You cannot access this draft bill.'))
                if header.store_id.id != bill['header']['store_id']:
                    raise AccessError(_('The draft bill branch does not match its invoice.'))
                if header.status in ('pending', 'saved'):
                    completed.add(self._draft_id(bill))
                    continue
                result = header._branch_result()
                busy = header._branch_submission_in_progress()
                submission = dict(submission, status=header.status,
                    attempted=header.branch_submission_started, local_header_id=header.id,
                    branch_header_id=header.branch_header_id, revision=header.branch_request_revision,
                    message=result['message'], unresolved=False, in_progress=busy)
                marker = result.get('correction')
                correcting = bool(marker and bill.get('correction') == marker)
                if not correcting:
                    bill.pop('correction', None)
                bill['slot_locked'] = busy or not (result['can_edit'] or correcting)
                bill['slot_protected'] = True
                bill['eplus_serial'] = header.eplus_serial
            else:
                unresolved = bool(submission.get('unresolved') or submission.get('attempted')
                                  or submission.get('local_header_id'))
                submission = dict(submission, unresolved=unresolved)
                if not unresolved:
                    submission.update(status='prepending', attempted=False)
                bill['slot_locked'] = unresolved
                bill['slot_protected'] = unresolved
            submission.pop('checking', None)
            bill.update(submission=submission, submission_status=submission.get('status', 'prepending'),
                submission_attempted=bool(submission.get('attempted')),
                submission_checking=bool(submission.get('unresolved')),
                submission_in_progress=bool(submission.get('in_progress')),
                submission_can_edit=not bill['slot_locked'],
                odoo_header_id=submission.get('local_header_id') or False)
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
        records = self.env["ab_sales_pos_draft_cache"].sudo().search(domain)
        Header = self.env['ab_sales_header'].sudo()
        if 'pos_hr_employee_id' in Header._fields and records:
            invoices = Header.search(fields.Domain('pos_client_token', 'in', records.mapped('pos_client_token')))
            foreign = invoices.filtered(lambda h: h.pos_hr_employee_id and h.pos_hr_employee_id != employee)
            if foreign:
                records = records.filtered(lambda r: r.pos_client_token not in foreign.mapped('pos_client_token'))
        return records

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

    def _draft_add_replacements(self, result, employee, stores, records):
        """Follow server-owned replacement links, including after a lost response."""
        Header = self.env['ab_sales_header'].sudo().with_context(active_test=False)
        by_token = {record.pos_client_token: record for record in records}
        frontier, visited, links = set(by_token), set(), {}
        # Resolve a batch at each generation instead of querying every normal draft.
        while frontier:
            visited.update(frontier)
            headers = Header.search(fields.Domain('pos_client_token', 'in', list(frontier)))
            replacements = {header.pos_client_token: header.branch_replacement_token for header in headers
                            if header.create_uid == self.env.user and header.branch_replacement_token}
            if not replacements:
                break
            successors = self._draft_records(employee, stores, tokens=list(set(replacements.values())))
            by_token.update({record.pos_client_token: record for record in successors})
            links.update({token: target for token, target in replacements.items() if target in by_token})
            frontier = set(successors.mapped('pos_client_token')) - visited
        for record in records:
            token, seen = record.pos_client_token, set()
            while token in links and token not in seen:
                seen.add(token)
                token = links[token]
            current = by_token[token]
            if token == record.pos_client_token:
                continue
            result['replacements'][record.pos_client_token] = token
            if record.pos_client_token not in result['removed_ids']:
                result['removed_ids'].append(record.pos_client_token)
            replacement_result = self._draft_result(employee, current)
            result['revision'].update(replacement_result['revision'])
            result['removed_ids'] += replacement_result['removed_ids']
            if current.state == 'active' and not any(b['id'] == token for b in result['bills']):
                result['bills'] += replacement_result['bills']
        result['bills'], completed = self._draft_authoritative_states(result['bills'])
        result['removed_ids'] += list(completed)
        result['completed_ids'] += list(completed)
        result['count'] = len(result['bills'])
        return result

    @api.model
    def pos_recover_rejected_draft(self, token, bill=None, pos_hr_session_token=None):
        """Retire an attempted identity, retaining its audit and one editable successor."""
        self._pos_require_sales_session(pos_hr_session_token)
        employee, stores = self._draft_scope(pos_hr_session_token=pos_hr_session_token)
        if bill is not None and not isinstance(bill, dict):
            raise UserError(_('Invalid draft cache payload.'))
        if not employee:
            raise AccessError(_('A valid employee session is required for draft bills.'))
        header = self.env['ab_sales_header'].with_context(active_test=False).search(
            fields.Domain('pos_client_token', '=', str(token or '')), limit=1)
        if (not header or header.create_uid != self.env.user or header.store_id.id not in stores
                or ('pos_hr_employee_id' in header._fields and header.pos_hr_employee_id
                    and header.pos_hr_employee_id != employee)):
            raise AccessError(_('You cannot access this draft bill.'))
        header.check_access('write')
        with header._branch_attempt():
            records = self._draft_records(employee, stores, tokens=[token])
            if header.sudo().branch_replacement_token:
                return self._draft_add_replacements(self._draft_result(employee, records), employee, stores, records)
            if header.status != 'rejected' or header.eplus_serial:
                raise UserError(_('Only a confirmed rejected bill can be restored as a draft.'))
            # Fresh submit/status responses already verified identity, revision and can_edit.
            # Older installed records need that evidence from the branch first.
            if not header.sudo().branch_rejection_editable:
                self._confirm_correction_rejection(header)
            if not header.sudo().branch_rejection_editable:
                raise UserError(_('Only a confirmed rejected bill can be restored as a draft.'))
            record = records[:1]
            if record:
                if not record.try_lock_for_update():
                    raise UserError(_('This draft is being edited. Refresh and try again.'))
                record.invalidate_recordset()
                if record.state != 'active':
                    raise UserError(_('This draft is no longer available. Refresh the draft list.'))
                if bill is not None and bill.get('draft_revision') != record.revision:
                    return self._draft_result(employee, record, outcomes=[{
                        'token': token, 'status': 'conflict', 'revision': record.revision,
                        'bill': deepcopy(record.bill_json)}])
            source = bill if bill is not None else record.bill_json if record else None
            if not source:
                raise UserError(_('Invalid draft cache payload.'))
            restored = self._draft_payload(source, stores)
            if self._draft_id(restored) != token or restored['header']['store_id'] != header.store_id.id:
                raise AccessError(_('Invalid draft identity or branch.'))
            # A replacement consumes the original draft's place, not a second admission.
            # No invoice or invoice line is deleted or modified.
            Cache = self.env['ab_sales_pos_draft_cache'].sudo()
            if not record:
                record = Cache.create({'pos_client_token': token, 'user_id': self.env.uid,
                    'employee_id': employee.id, 'store_id': header.store_id.id,
                    'bill_json': deepcopy(restored)})
            replacement = str(uuid4())
            restored.update(id=replacement, submission={'status': 'prepending', 'attempted': False,
                'unresolved': False, 'in_progress': False}, submission_status='prepending',
                submission_attempted=False, submission_checking=False, submission_in_progress=False,
                submission_can_edit=True, submission_message='', slot_locked=False, slot_protected=False,
                odoo_header_id=False, eplus_serial=0)
            restored['header']['pos_client_token'] = replacement
            restored.pop('correction', None)
            new_record = Cache.create({'pos_client_token': replacement, 'user_id': self.env.uid,
                'employee_id': employee.id, 'store_id': header.store_id.id, 'bill_json': restored,
                'last_synced_at': fields.Datetime.now()})
            history = list(header.sudo().branch_submission_history or [])
            history.append({'event': 'restored_as_draft', 'replacement_token': replacement,
                'revision': header.branch_request_revision, 'restored_by': self.env.uid,
                'restored_at': fields.Datetime.to_string(fields.Datetime.now())})
            header.sudo()._write_branch_state({'branch_replacement_token': replacement,
                'branch_submission_history': history, 'branch_correction': False})
            record.write({'state': 'retired', 'revision': record.revision + 1})
            result = self._draft_result(employee, record | new_record, selected_id=replacement)
            result['replacements'] = {token: replacement}
            return result

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
        result = self._draft_add_replacements(self._draft_result(employee, records), employee, stores, records)
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
        # Remote submission omits service-user relations. The local creator
        # still owns the callcenter invoice; employee, cache ownership and
        # branch checks remain mandatory.
        if invoice and "pos_hr_employee_id" in Header._fields and invoice.pos_hr_employee_id and (
                invoice.pos_hr_employee_id != employee
                or (invoice.pos_hr_service_user_id or invoice.create_uid).id != self.env.uid):
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
        if invoice and invoice._correction_marker():
            self._validate_correction_bill(invoice, bill)
        elif bill.get('correction'):
            raise UserError(_('This correction is no longer active. Refresh the bill.'))
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
            occupied = sum(not value.get("slot_locked") or bool(value.get("correction")) for value in active_bills)
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
        return self._draft_add_replacements(
            self._draft_result(employee, records, outcomes, selected_id), employee, stores, records)

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
