# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from psycopg2 import OperationalError


class AbSalesUiApiReplicationInherit(models.TransientModel):
    _inherit = "ab_sales_ui_api"
    _POS_REPLICATION_CRON_PREFIX = "ab_odoo_replication"

    @api.model
    def pos_replication_active_crons(self):
        Cron = self.env["ir.cron"].sudo()
        rows = Cron.search_read(
            [
                ("active", "=", True),
                ("model_id.model", "=", "ab_odoo_replication"),
                ("name", "like", f"{self._POS_REPLICATION_CRON_PREFIX}%"),
            ],
            ["name", "nextcall", "lastcall", "user_id", "model_id", "state"],
            order="name asc",
        )
        out = []
        for row in rows:
            name = row.get("name") or ""
            if not name.startswith(self._POS_REPLICATION_CRON_PREFIX):
                continue
            out.append(
                {
                    "id": int(row.get("id") or 0),
                    "name": name,
                    "nextcall": row.get("nextcall"),
                    "lastcall": row.get("lastcall"),
                    "user_name": (row.get("user_id") or [False, ""])[1] or "",
                    "model_name": (row.get("model_id") or [False, ""])[1] or "",
                    "state": row.get("state") or "",
                }
            )
        return out

    @api.model
    def pos_replication_run_cron(self, cron_id):
        cron_id = int(cron_id or 0)
        if not cron_id:
            raise UserError(_("Missing cron id."))

        cron = self.env["ir.cron"].sudo().browse(cron_id).exists()
        if not cron:
            raise UserError(_("Cron not found."))
        if not cron.active:
            raise UserError(_("Selected cron is inactive."))
        if cron.model_id.model != "ab_odoo_replication":
            raise UserError(_("Only ab_odoo_replication cron is allowed."))
        if not (cron.name or "").startswith(self._POS_REPLICATION_CRON_PREFIX):
            raise UserError(_("Cron name must start with '%s'.") % self._POS_REPLICATION_CRON_PREFIX)
        self._check_user_manual_turn(cron)
        if self._is_cron_nextcall_imminent(cron):
            raise UserError(_("This cron is scheduled to run in less than 10 seconds. Please wait."))
        if self._is_cron_running_now(cron.id):
            raise UserError(_("This cron is already running in background. Please wait for completion."))

        if hasattr(cron, "method_direct_trigger"):
            cron.method_direct_trigger()
        elif cron.ir_actions_server_id:
            cron.ir_actions_server_id.sudo().run()
        else:
            raise UserError(_("Selected cron cannot be triggered manually."))
        self._consume_user_manual_turn(cron)

        return {
            "id": cron.id,
            "name": cron.name or "",
            "message": _("Cron has been triggered."),
        }

    @api.model
    def _check_user_manual_turn(self, cron):
        Turn = self.env["ab_sales_pos_replication_turn"].sudo()
        turn = Turn.search(
            [
                ("user_id", "=", self.env.uid),
                ("cron_id", "=", cron.id),
            ],
            limit=1,
        )
        if not turn or not turn.last_manual_run_at:
            return

        cooldown = self._cron_interval_delta(cron)
        if cooldown <= timedelta(seconds=0):
            return

        next_allowed = turn.last_manual_run_at + cooldown
        now = fields.Datetime.now()
        if now < next_allowed:
            next_allowed_text = fields.Datetime.to_string(next_allowed)
            raise UserError(
                _(
                    "You already consumed your chance for this cron interval. "
                    "Please let another user try. Next chance: %s UTC"
                )
                % next_allowed_text
            )

    @api.model
    def _consume_user_manual_turn(self, cron):
        Turn = self.env["ab_sales_pos_replication_turn"].sudo()
        domain = [
            ("user_id", "=", self.env.uid),
            ("cron_id", "=", cron.id),
        ]
        turn = Turn.search(domain, limit=1)
        now = fields.Datetime.now()
        if turn:
            turn.write({"last_manual_run_at": now})
            return
        Turn.create(
            {
                "user_id": self.env.uid,
                "cron_id": cron.id,
                "last_manual_run_at": now,
            }
        )

    @api.model
    def _cron_interval_delta(self, cron):
        number = int(cron.interval_number or 0)
        if number <= 0:
            number = 1
        interval_type = (cron.interval_type or "minutes").strip()
        if interval_type == "minutes":
            return timedelta(minutes=number)
        if interval_type == "hours":
            return timedelta(hours=number)
        if interval_type == "days":
            return timedelta(days=number)
        if interval_type == "weeks":
            return timedelta(weeks=number)
        if interval_type == "months":
            return timedelta(days=30 * number)
        return timedelta(minutes=number)

    @api.model
    def _is_cron_nextcall_imminent(self, cron):
        nextcall = cron.nextcall
        if not nextcall:
            return False
        now = fields.Datetime.now()
        return nextcall <= (now + timedelta(seconds=10))

    @api.model
    def _is_cron_running_now(self, cron_id):
        # Odoo cron workers lock ir_cron rows; if NOWAIT lock fails, the cron is already running.
        self.env.cr.execute("SAVEPOINT ab_pos_repl_cron_lock_check")
        try:
            self.env.cr.execute(
                "SELECT id FROM ir_cron WHERE id = %s FOR UPDATE NOWAIT",
                (int(cron_id),),
            )
        except OperationalError:
            self.env.cr.execute("ROLLBACK TO SAVEPOINT ab_pos_repl_cron_lock_check")
            return True
        except Exception:
            self.env.cr.execute("ROLLBACK TO SAVEPOINT ab_pos_repl_cron_lock_check")
            raise
        self.env.cr.execute("ROLLBACK TO SAVEPOINT ab_pos_repl_cron_lock_check")
        return False
