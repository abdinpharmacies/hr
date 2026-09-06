from odoo import api, fields, models


_OPERATION_LOG_MODEL = "ab_employee_access_sales_operation_log"


class AbSalesSyncUploadOutbox(models.Model):
    _inherit = "ab_odoo_sync_outbox"

    @api.model
    def capture_prepared_snapshots(self, snapshots, operation="upsert"):
        # All live, historical, and prepared archive captures pass this boundary.
        snapshots = [
            snapshot
            for snapshot in snapshots or []
            if not (
                snapshot.get("model_name") == _OPERATION_LOG_MODEL
                and snapshot.get("payload_json", {}).get("fields", {}).get(
                    "operation_type"
                ) == "heartbeat"
            )
        ]
        return super().capture_prepared_snapshots(snapshots, operation=operation)


class AbSalesSyncUploadSource(models.Model):
    _inherit = "ab_odoo_sync_upload_source"

    def _historical_upload_domain(self):
        domain = super()._historical_upload_domain()
        if self.model_name == _OPERATION_LOG_MODEL:
            domain &= fields.Domain("operation_type", "!=", "heartbeat")
        return domain
