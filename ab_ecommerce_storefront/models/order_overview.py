from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from odoo import api, fields, models
from odoo.exceptions import AccessError
from odoo.tools import format_amount, format_datetime


class SaleOrderOverview(models.Model):
    _inherit = "sale.order"

    @api.model
    def _ab_order_overview_check_access(self):
        user = self.env.user
        if not (user.has_group("sales_team.group_sale_salesman") or user.has_group("base.group_system")):
            raise AccessError(self.env._("You cannot access the order overview."))
        self.browse().check_access("read")

    @api.model
    def _ab_order_overview_domains(self):
        base = fields.Domain("website_id", "!=", False) & fields.Domain(
            "company_id", "in", self.env.companies.ids
        )
        operational = base & (
            fields.Domain("state", "!=", "draft")
            | fields.Domain("ab_call_center_order_type", "=", "prescription")
        )
        local_today = fields.Date.context_today(self)
        local_start = datetime.combine(local_today, time.min, ZoneInfo(self.env.user.tz or "UTC"))
        utc_start = local_start.astimezone(timezone.utc).replace(tzinfo=None)
        utc_end = (local_start + timedelta(days=1)).astimezone(timezone.utc).replace(tzinfo=None)
        return {
            "all": operational,
            "new": operational & fields.Domain("state", "in", ("draft", "sent")),
            "unpaid": base & fields.Domain("state", "=", "sent"),
            "processing": operational & fields.Domain("ab_call_center_status", "=", "preparing"),
            "assigned": operational
            & fields.Domain("user_id", "!=", False)
            & fields.Domain("ab_call_center_status", "in", ("received", "confirmed", "preparing")),
            "deliveries": base
            & fields.Domain("ab_last_mile_delivered_date", ">=", fields.Datetime.to_string(utc_start))
            & fields.Domain("ab_last_mile_delivered_date", "<", fields.Datetime.to_string(utc_end)),
            "cancelled": base & fields.Domain("state", "=", "cancel"),
            "abandoned": base & fields.Domain("is_abandoned_cart", "=", True),
        }

    @api.model
    def get_ab_order_overview(self):
        self._ab_order_overview_check_access()
        domains = self._ab_order_overview_domains()
        counts = {key: self.search_count(domain) for key, domain in domains.items() if key != "all"}
        payment_labels = dict(self.fields_get(["ab_call_center_payment_status"])[
            "ab_call_center_payment_status"
        ]["selection"])
        recent = self.search(domains["all"], order="date_order desc, id desc", limit=8)
        return {
            "counts": counts,
            "recent": [
                {
                    "id": order.id,
                    "name": order.name,
                    "customer": order.partner_id.name,
                    "status": order._ab_call_center_status_label(),
                    "status_code": order.ab_call_center_status,
                    "payment": payment_labels.get(order.ab_call_center_payment_status, ""),
                    "amount": format_amount(self.env, order.amount_total, order.currency_id),
                    "date": format_datetime(self.env, order.date_order, dt_format=False),
                }
                for order in recent
            ],
        }

    @api.model
    def action_ab_order_overview_bucket(self, bucket):
        self._ab_order_overview_check_access()
        domains = self._ab_order_overview_domains()
        if bucket not in domains:
            raise AccessError(self.env._("You cannot access this order group."))
        xml_id = (
            "website_sale.action_view_abandoned_tree"
            if bucket == "abandoned"
            else "website_sale.action_orders_ecommerce"
        )
        action = dict(self.env["ir.actions.actions"]._for_xml_id(xml_id))
        action["domain"] = list(domains[bucket])
        action["context"] = (
            {"show_sale": True, "create": False}
            if bucket == "abandoned"
            else {"show_sale": True, "ab_call_center_workspace": True}
        )
        return action

    @api.model
    def action_ab_order_overview_open(self, order_id):
        self._ab_order_overview_check_access()
        if isinstance(order_id, bool) or not isinstance(order_id, int):
            raise AccessError(self.env._("You cannot access this order."))
        order = self.browse(order_id).exists()
        order.check_access("read")
        if not order.website_id or order.company_id not in self.env.companies:
            raise AccessError(self.env._("You cannot access this order."))
        action = dict(self.env["ir.actions.actions"]._for_xml_id("website_sale.action_orders_ecommerce"))
        action.update({
            "res_id": order.id,
            "views": [(self.env.ref("ab_ecommerce_storefront.view_sale_order_call_center_form").id, "form")],
            "view_mode": "form",
            "context": {"show_sale": True, "ab_call_center_workspace": True},
        })
        return action
