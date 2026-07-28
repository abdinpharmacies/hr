import json

from odoo import api, fields, models
from odoo.exceptions import UserError


class AbOdooSyncEvent(models.Model):
    _name = "ab_odoo_sync_event"
    _description = "AB Odoo Sync Event"
    _order = "id asc"

    model_name = fields.Char(required=True, index=True)
    record_id = fields.Integer(required=True, index=True)
    operation = fields.Selection(
        selection=[
            ("create", "Create"),
            ("write", "Write"),
            ("unlink", "Unlink"),
        ],
        required=True,
        index=True,
    )
    payload_json = fields.Json(default=dict)
    changed_fields_json = fields.Json(default=list)
    source_server = fields.Char(default="main", required=True, index=True)

    @api.model
    def get_events_after(self, last_event_id=0, limit=1000):
        limit = max(1, min(int(limit or 1000), 10000))
        last_event_id = int(last_event_id or 0)
        events = self.search([("id", ">", last_event_id)], order="id asc", limit=limit)
        return [
            {
                "id": ev.id,
                "model_name": ev.model_name,
                "record_id": ev.record_id,
                "operation": ev.operation,
                "payload_json": ev.payload_json or {},
                "changed_fields_json": ev.changed_fields_json or [],
                "source_server": ev.source_server,
                "create_date": fields.Datetime.to_string(ev.create_date) if ev.create_date else None,
            }
            for ev in events
        ]

    def write(self, vals):
        raise UserError("ab_odoo_sync_event is append-only.")

    def unlink(self):
        if not self.env.context.get("ab_odoo_sync_allow_event_cleanup"):
            raise UserError("ab_odoo_sync_event is append-only.")
        return super().unlink()

    def name_get(self):
        return [
            (rec.id, f"{rec.id} | {rec.model_name}:{rec.record_id} [{rec.operation}]")
            for rec in self
        ]

    def _export_row_json(self):
        return json.dumps(
            {
                "id": self.id,
                "model_name": self.model_name,
                "record_id": self.record_id,
                "operation": self.operation,
                "payload_json": self.payload_json,
                "changed_fields_json": self.changed_fields_json,
                "source_server": self.source_server,
            },
            ensure_ascii=False,
        )
