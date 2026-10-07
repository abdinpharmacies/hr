import logging
import re

from psycopg2 import IntegrityError

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import mute_logger


_logger = logging.getLogger(__name__)


class AbEmployeeAccess(models.Model):
    _inherit = "ab_employee_access"

    @api.model
    def _cron_sync_employee_sales_roles(self, default_pin=None):
        """Create missing access profiles using HR's searchable working status.

        This private administrator automation intentionally covers all employees.
        Existing profiles and sessions are never updated by this automation.
        """
        if default_pin is not None and (
            not isinstance(default_pin, str)
            or not re.fullmatch(r"[0-9]{4}", default_pin)
        ):
            raise ValidationError(_("Default POS PIN must be a string containing exactly four digits."))

        profiles_model = self.sudo().with_context(active_test=False)
        employees_model = self.env["ab_hr_employee"].sudo().with_context(active_test=False)
        mappings = self.env["ab_employee_access_sales_job_role_mapping"].sudo().search(
            fields.Domain("job_id.active", "=", True)
            & fields.Domain("role_id.active", "=", True)
        )
        roles_by_job = {mapping.job_id.id: mapping.role_id for mapping in mappings}
        # Retain result/log keys for callers; update counters always stay zero.
        counts = dict.fromkeys(
            ("created", "assigned", "disabled", "reenabled", "revoked", "skipped", "failures"), 0
        )
        last_id = 0
        while employees := employees_model.search(
            fields.Domain("id", ">", last_id), order="id", limit=500
        ):
            last_id = employees[-1].id
            working_ids = set(employees_model.search(
                fields.Domain("id", "in", employees.ids)
                & fields.Domain("is_working", "=", True)
            ).ids)
            profiles = profiles_model.search(fields.Domain("employee_id", "in", employees.ids))
            employees_with_profiles = set(profiles.employee_id.ids)

            for employee in employees:
                if employee.id in employees_with_profiles:
                    counts["skipped"] += 1
                    continue
                delta = dict.fromkeys(counts, 0)
                try:
                    # SQL exception parameters can contain PINs. Log only the
                    # employee ID and exception type after the savepoint rolls back.
                    with mute_logger("odoo.sql_db"), self.env.cr.savepoint():
                        working = employee.active and employee.id in working_ids
                        role = roles_by_job.get(employee.job_id.id) if working else None
                        if role:
                            store = employee.department_id.store_id
                            values = {
                                "employee_id": employee.id,
                                "costcenter_id": employee.costcenter_id.id,
                                "pos_role_id": role.id,
                                "pos_allowed_store_ids": [fields.Command.set(store.ids)],
                                "pos_allow_login": bool(store),
                            }
                            if default_pin is not None:
                                values["pos_pin"] = default_pin
                            profiles_model.create(values)
                            delta["created"] = 1
                            delta["assigned"] = 1
                        else:
                            delta["skipped"] = 1
                    for key, value in delta.items():
                        counts[key] += value
                except (UserError, IntegrityError) as error:
                    counts["failures"] += 1
                    _logger.warning(
                        "Employee sales access sync failed for employee %s (%s)",
                        employee.id, type(error).__name__,
                    )
        _logger.info(
            "Employee sales access sync: created=%(created)s assigned=%(assigned)s "
            "disabled=%(disabled)s reenabled=%(reenabled)s revoked=%(revoked)s "
            "skipped=%(skipped)s failures=%(failures)s", counts,
        )
        return counts

    pos_pin = fields.Char(
        string="POS PIN",
        copy=False,
        default=lambda self: self._generate_pos_pin(),
        groups="ab_employee_access_sales.group_ab_employee_access_sales_manager"
    )

    pos_session_ids = fields.One2many("ab_employee_access_sales_pos_session", "profile_id")
    pos_operation_log_ids = fields.One2many("ab_employee_access_sales_operation_log", "profile_id")

    @api.depends("pos_pin_last_changed", "pos_pin_rotation_days", "pos_role_id.pin_rotation_days")
    def _compute_pos_pin_expired(self):
        now = fields.Datetime.now()
        for rec in self:
            rotation_days = rec._effective_pos_permissions().get("pin_rotation_days", 90)
            changed_at = rec.pos_pin_last_changed or rec.write_date or rec.create_date or now
            deadline = fields.Datetime.add(changed_at, days=rotation_days)
            rec.pos_pin_expired = bool(deadline and deadline < now)

    def _effective_pos_permissions(self):
        self.ensure_one()
        if self.pos_use_custom_permissions:
            return super()._effective_pos_permissions()
        if self.pos_role_id:
            return self.pos_role_id.permission_payload()
        return super()._effective_pos_permissions()

    def pos_permission_payload(self):
        self.ensure_one()
        payload = super().pos_permission_payload()
        payload.update({
            "role_id": self.pos_role_id.id if self.pos_role_id else False,
            "role_name": self.pos_role_id.display_name if self.pos_role_id else "",
        })
        return payload
