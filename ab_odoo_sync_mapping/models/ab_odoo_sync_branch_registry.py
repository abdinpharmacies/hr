import secrets

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _

from .ab_odoo_sync_security import (
    SyncConfigurationError,
    hash_sync_key,
    normalize_hdd_serial,
    verify_sync_key,
)

_SECURITY_MANAGED_FIELDS = {
    "api_key_hash",
    "hdd_serial",
    "pending_hdd_serial",
    "hardware_binding_state",
    "hardware_approved_by_id",
    "hardware_approved_at",
    "hardware_rejected_by_id",
    "hardware_rejected_at",
    "hardware_rejection_reason",
    "hardware_replaced_by_id",
    "hardware_replaced_at",
    "hardware_replacement_reason",
    "last_hardware_mismatch_at",
}


class AbOdooSyncBranchRegistry(models.Model):
    _name = "ab_odoo_sync_branch_registry"
    _inherit = "ab_odoo_sync_passive_mirror_mixin"
    _log_access = False
    _description = "AB Odoo Sync Branch Registration"
    _order = "db_serial"

    name = fields.Char()
    db_serial = fields.Integer(string="DB Serial", index=True)
    api_key_hash = fields.Char(string="API Key Hash", readonly=True, copy=False)
    has_api_key = fields.Boolean(
        string="Has API Key",
        compute="_compute_has_api_key",
    )
    hdd_serial = fields.Char(
        string="Approved Hardware Serial",
        readonly=True,
        copy=False,
    )
    pending_hdd_serial = fields.Char(
        string="Pending Hardware Serial",
        readonly=True,
        copy=False,
    )
    hardware_binding_state = fields.Selection(
        selection=[
            ("unbound", "Unbound"),
            ("pending", "Pending Approval"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
        ],
        default="unbound",
        required=True,
        readonly=True,
        index=True,
        copy=False,
    )
    hardware_approved_by_id = fields.Many2one(
        "res.users",
        string="Hardware Approved By",
        readonly=True,
        copy=False,
    )
    hardware_approved_at = fields.Datetime(
        string="Hardware Approved At",
        readonly=True,
        copy=False,
    )
    hardware_rejected_by_id = fields.Many2one(
        "res.users",
        string="Hardware Rejected By",
        readonly=True,
        copy=False,
    )
    hardware_rejected_at = fields.Datetime(
        string="Hardware Rejected At",
        readonly=True,
        copy=False,
    )
    hardware_rejection_reason = fields.Text(
        string="Hardware Rejection Reason",
        readonly=True,
        copy=False,
    )
    hardware_replaced_by_id = fields.Many2one(
        "res.users",
        string="Hardware Replaced By",
        readonly=True,
        copy=False,
    )
    hardware_replaced_at = fields.Datetime(
        string="Hardware Replaced At",
        readonly=True,
        copy=False,
    )
    hardware_replacement_reason = fields.Text(
        string="Hardware Replacement Reason",
        readonly=True,
        copy=False,
    )
    last_hardware_mismatch_at = fields.Datetime(
        string="Last Hardware Mismatch At",
        readonly=True,
        copy=False,
    )
    audit_ids = fields.One2many(
        "ab_odoo_sync_branch_audit",
        "branch_id",
        string="Security Audit",
        readonly=True,
    )
    last_upload_at = fields.Datetime(string="Last Upload At", readonly=True)
    active = fields.Boolean(default=True, index=True)

    _uniq_db_serial = models.Constraint(
        "UNIQUE(db_serial)",
        "DB serial must be unique in the branch registry.",
    )
    _uniq_sync_identity = models.Constraint(
        "UNIQUE(db_serial, rec_id)",
        "Source DB and record ID must be unique per branch registration.",
    )
    _positive_db_serial = models.Constraint(
        "CHECK(db_serial > 0)",
        "DB serial must be a positive integer.",
    )

    def _compute_has_api_key(self):
        for branch in self:
            branch.has_api_key = bool(branch.api_key_hash)

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get("ab_odoo_sync_security_write"):
            for vals in vals_list:
                if _SECURITY_MANAGED_FIELDS.intersection(vals):
                    raise UserError(
                        _("Use branch security actions to update sync credentials.")
                    )
        return super().create(vals_list)

    def write(self, vals):
        if (
            not self.env.context.get("ab_odoo_sync_security_write")
            and _SECURITY_MANAGED_FIELDS.intersection(vals)
        ):
            raise UserError(_("Use branch security actions to update sync credentials."))
        return super().write(vals)

    def unlink(self):
        raise UserError(_("Archive branch registrations instead of deleting them."))

    def _require_system_user(self):
        if not self.env.user.has_group("base.group_system"):
            raise UserError(_("Only Settings users can manage branch sync security."))

    def _lock_for_update(self):
        if not self.ids:
            return
        self.flush_recordset(list(_SECURITY_MANAGED_FIELDS))
        self.env.cr.execute(
            "SELECT id FROM ab_odoo_sync_branch_registry WHERE id IN %s FOR UPDATE",
            (tuple(self.ids),),
        )
        self.invalidate_recordset(list(_SECURITY_MANAGED_FIELDS), flush=False)

    def _audit(self, event_type, **values):
        self.ensure_one()
        vals = {
            "branch_id": self.id,
            "event_type": event_type,
            "hdd_serial": values.get("hdd_serial") or self.hdd_serial or False,
            "pending_hdd_serial": values.get("pending_hdd_serial")
            or self.pending_hdd_serial
            or False,
            "reason": values.get("reason") or False,
            "user_id": values.get("user_id", self.env.uid),
        }
        return self.env["ab_odoo_sync_branch_audit"].sudo().create(vals)

    def _key_wizard_action(self, api_key):
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Branch API Key"),
                "message": _("New API key for %(branch)s: %(api_key)s")
                % {
                    "branch": self.display_name,
                    "api_key": api_key,
                },
                "type": "success",
                "sticky": True,
            },
        }

    def action_generate_api_key(self):
        self.ensure_one()
        self._require_system_user()
        api_key = secrets.token_urlsafe(32)
        try:
            api_key_hash = hash_sync_key(api_key)
        except SyncConfigurationError as ex:
            raise UserError(str(ex)) from ex
        self._lock_for_update()
        self.with_context(ab_odoo_sync_security_write=True).sudo().write(
            {"api_key_hash": api_key_hash}
        )
        self._audit("key_rotated")
        return self._key_wizard_action(api_key)

    def action_approve_pending_hardware(self):
        self.ensure_one()
        self._require_system_user()
        self._lock_for_update()
        branch = self.sudo()
        if not branch.pending_hdd_serial:
            raise UserError(_("There is no pending hardware serial to approve."))
        now = fields.Datetime.now()
        approved_serial = branch.pending_hdd_serial
        branch.with_context(ab_odoo_sync_security_write=True).write(
            {
                "hdd_serial": approved_serial,
                "pending_hdd_serial": False,
                "hardware_binding_state": "approved",
                "hardware_approved_by_id": self.env.uid,
                "hardware_approved_at": now,
                "hardware_rejected_by_id": False,
                "hardware_rejected_at": False,
                "hardware_rejection_reason": False,
            }
        )
        branch._audit(
            "hardware_approved",
            hdd_serial=approved_serial,
            user_id=self.env.uid,
        )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Branch Hardware Approval"),
                "message": _("Pending hardware serial approved."),
                "type": "success",
                "sticky": False,
            },
        }

    def action_open_reject_pending_hardware(self):
        self.ensure_one()
        self._require_system_user()
        wizard = self.env["ab_odoo_sync_branch_hardware_reject_wizard"].create(
            {"branch_id": self.id}
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Reject Pending Hardware"),
            "res_model": "ab_odoo_sync_branch_hardware_reject_wizard",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_reject_pending_hardware(self, reason):
        self.ensure_one()
        self._require_system_user()
        reason = (reason or "").strip()
        if not reason:
            raise UserError(_("A rejection reason is required."))
        self._lock_for_update()
        branch = self.sudo()
        if not branch.pending_hdd_serial:
            raise UserError(_("There is no pending hardware serial to reject."))
        pending_serial = branch.pending_hdd_serial
        branch.with_context(ab_odoo_sync_security_write=True).write(
            {
                "pending_hdd_serial": False,
                "hardware_binding_state": (
                    "rejected" if not branch.hdd_serial else "approved"
                ),
                "hardware_rejected_by_id": self.env.uid,
                "hardware_rejected_at": fields.Datetime.now(),
                "hardware_rejection_reason": reason,
            }
        )
        branch._audit(
            "hardware_rejected",
            pending_hdd_serial=pending_serial,
            reason=reason,
            user_id=self.env.uid,
        )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Branch Hardware Rejection"),
                "message": _("Pending hardware serial rejected."),
                "type": "warning",
                "sticky": False,
                "next": {"type": "ir.actions.client", "tag": "reload"},
            },
        }

    def action_open_replace_hardware(self):
        self.ensure_one()
        self._require_system_user()
        wizard = self.env["ab_odoo_sync_branch_hardware_replace_wizard"].create(
            {"branch_id": self.id}
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Replace Branch Hardware"),
            "res_model": "ab_odoo_sync_branch_hardware_replace_wizard",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_replace_hardware(self, replacement_hdd_serial, reason):
        self.ensure_one()
        self._require_system_user()
        replacement_hdd_serial = normalize_hdd_serial(replacement_hdd_serial)
        reason = (reason or "").strip()
        if not reason:
            raise UserError(_("A replacement reason is required."))
        api_key = secrets.token_urlsafe(32)
        try:
            api_key_hash = hash_sync_key(api_key)
        except SyncConfigurationError as ex:
            raise UserError(str(ex)) from ex
        self._lock_for_update()
        branch = self.sudo()
        if branch.hdd_serial and replacement_hdd_serial == branch.hdd_serial:
            raise UserError(_("Replacement hardware serial must be different."))
        now = fields.Datetime.now()
        old_serial = branch.hdd_serial
        branch.with_context(ab_odoo_sync_security_write=True).write(
            {
                "api_key_hash": api_key_hash,
                "hdd_serial": replacement_hdd_serial,
                "pending_hdd_serial": False,
                "hardware_binding_state": "approved",
                "hardware_approved_by_id": self.env.uid,
                "hardware_approved_at": now,
                "hardware_replaced_by_id": self.env.uid,
                "hardware_replaced_at": now,
                "hardware_replacement_reason": reason,
                "hardware_rejected_by_id": False,
                "hardware_rejected_at": False,
                "hardware_rejection_reason": False,
            }
        )
        branch._audit(
            "hardware_replaced",
            hdd_serial=replacement_hdd_serial,
            reason=reason,
            user_id=self.env.uid,
        )
        branch._audit(
            "key_rotated",
            hdd_serial=replacement_hdd_serial,
            reason=reason,
            user_id=self.env.uid,
        )
        if old_serial:
            branch._audit(
                "hardware_replaced",
                hdd_serial=old_serial,
                pending_hdd_serial=replacement_hdd_serial,
                reason=reason,
                user_id=self.env.uid,
            )
        return branch._key_wizard_action(api_key)

    def verify_api_key(self, received_key):
        self.ensure_one()
        if not self.api_key_hash:
            return False
        try:
            return verify_sync_key(received_key, self.api_key_hash)
        except (SyncConfigurationError, ValueError):
            return False

    @api.private
    def enroll_pending_hardware(self, hdd_serial):
        self.ensure_one()
        hdd_serial = normalize_hdd_serial(hdd_serial)
        self._lock_for_update()
        branch = self.sudo()
        if not branch.hdd_serial:
            if branch.hardware_binding_state not in {"unbound", "pending"}:
                return False, "hardware_pending"
        expected_serial = branch.hdd_serial or branch.pending_hdd_serial
        if expected_serial and expected_serial != hdd_serial:
            branch.with_context(ab_odoo_sync_security_write=True).write(
                {"last_hardware_mismatch_at": fields.Datetime.now()}
            )
            branch._audit(
                "hardware_mismatch",
                hdd_serial=branch.hdd_serial,
                pending_hdd_serial=hdd_serial,
                reason=_("Authenticated request used an unapproved hardware serial."),
            )
            return False, "hardware_mismatch"
        if not branch.hdd_serial:
            branch.with_context(ab_odoo_sync_security_write=True).write(
                {
                    "hdd_serial": hdd_serial,
                    "pending_hdd_serial": False,
                    "hardware_binding_state": "approved",
                    "hardware_approved_by_id": False,
                    "hardware_approved_at": fields.Datetime.now(),
                }
            )
            branch._audit(
                "hardware_approved",
                hdd_serial=hdd_serial,
                reason=_("Hardware automatically bound on first authenticated request."),
                user_id=False,
            )
        return True, False
