from odoo import api, fields, models
from odoo.exceptions import UserError


class EplusStockSnapshot(models.Model):
    _inherit = "ab_eplus_stock_snapshot"

    @api.model
    def _ab_require_safe_website_resync(self, warehouse):
        latest_sync = self.env["ab_eplus_inventory_sync_job"].sudo().search([
            ("state", "=", "done"),
            ("warehouse_id", "=", warehouse.id),
            ("date_done", "!=", False),
        ], order="date_done desc, id desc", limit=1)
        domain = [
            ("state", "=", "done"),
            ("sale_line_id.order_id.website_id", "!=", False),
            ("sale_line_id.order_id.warehouse_id", "=", warehouse.id),
            ("product_id.product_tmpl_id.ab_product_id", "!=", False),
            ("location_dest_id.usage", "=", "customer"),
        ]
        if latest_sync:
            domain.append(("date", ">", latest_sync.date_done))
        delivered = self.env["stock.move"].sudo().search(domain, limit=1)
        if delivered:
            raise UserError(self.env._(
                "Eplus inventory sync is blocked because website deliveries are not reflected in Eplus stock. Syncing now would restore sold stock."
            ))

    def _sync_to_odoo_inventory(self):
        warehouse = self._get_inventory_sync_warehouse()
        self._ab_require_safe_website_resync(warehouse)
        return super()._sync_to_odoo_inventory()


class EplusInventorySyncJob(models.Model):
    _inherit = "ab_eplus_inventory_sync_job"

    def _prepare_full_sync(self):
        for job in self:
            warehouse = job.warehouse_id or self.env["ab_eplus_stock_snapshot"]._get_inventory_sync_warehouse()
            self.env["ab_eplus_stock_snapshot"]._ab_require_safe_website_resync(warehouse)
        return super()._prepare_full_sync()

    def _process_next_batch(self):
        self.ensure_one()
        try:
            self.env["ab_eplus_stock_snapshot"]._ab_require_safe_website_resync(self.warehouse_id)
        except UserError as error:
            self.write({
                "state": "failed",
                "date_done": fields.Datetime.now(),
                "last_message": str(error),
            })
            return False
        return super()._process_next_batch()
