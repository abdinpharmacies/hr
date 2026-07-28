# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AbSalesPerDaySyncWizard(models.TransientModel):
    _name = "ab_sales_per_day_sync_wizard"
    _description = "Sales Per Day Sync Wizard"

    date_from = fields.Date(
        string="Date From",
        required=True,
    )
    date_to = fields.Date(
        string="Date To",
        required=True,
    )
    force_resync = fields.Boolean(
        string="Refresh Done Days",
        default=True,
        help="Refresh days that were already synced successfully.",
    )

    @api.model
    def cron_sync_last_90_sales_per_day(self):
        today = fields.Date.context_today(self)
        date_to = today - timedelta(days=1)
        date_from = date_to - timedelta(days=89)
        wizard = self.sudo().create({
            "date_from": date_from,
            "date_to": date_to,
            "force_resync": True,
        })
        return wizard.action_sync_sales_per_day()

    def action_sync_sales_per_day(self):
        self.ensure_one()
        date_from = fields.Date.to_date(self.date_from)
        date_to = fields.Date.to_date(self.date_to)
        today = fields.Date.context_today(self)

        if not date_from or not date_to:
            raise UserError(_("Date From and Date To are required."))
        if date_from > date_to:
            raise UserError(_("Date From must be before or equal to Date To."))
        if date_to >= today:
            raise UserError(_("Only completed days can be synced. Select a date before today."))

        SalesPerDay = self.env["ab_sales_per_day"].sudo()
        synced_count = 0
        failed_count = 0
        current = date_from
        while current <= date_to:
            result = SalesPerDay.cron_sync_next_sales_day(
                start_date=current,
                end_date=current,
                force_resync=self.force_resync,
            )
            if result:
                synced_count += 1
            else:
                failed_count += 1
            current += timedelta(days=1)

        if failed_count:
            notification_type = "warning"
            message = _(
                "Sales sync finished with warnings. Synced days: %(synced)s. Failed or skipped days: %(failed)s."
            ) % {
                "synced": synced_count,
                "failed": failed_count,
            }
        else:
            notification_type = "success"
            message = _("Sales sync finished. Synced days: %s.") % synced_count

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Sales Per Day Sync"),
                "message": message,
                "type": notification_type,
                "sticky": False,
            },
        }
