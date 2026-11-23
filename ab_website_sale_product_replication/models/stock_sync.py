import logging

from odoo import _, api, models
from odoo.addons.integration_queue_job.exception import RetryableJobError
from odoo.exceptions import AccessError, UserError


_logger = logging.getLogger(__name__)


class EplusStockSnapshot(models.Model):
    _inherit = "ab_eplus_stock_snapshot"

    @api.model
    def _refresh_after_replication(self):
        if not self.env.user.has_group("base.group_system"):
            raise AccessError(_("Only administrators can run the scheduled Eplus stock refresh."))
        previous_count = self.sudo().search_count([("active", "=", True)])
        try:
            self.action_refresh_from_eplus()
        except UserError as error:
            raise RetryableJobError(str(error), seconds=300) from error
        current_count = self.sudo().search_count([("active", "=", True)])
        if not current_count or (previous_count and current_count < previous_count * 0.9):
            raise UserError(_("Eplus stock refresh returned too few rows; the previous snapshot was kept."))
        _logger.info("Eplus stock refreshed after replication: active=%s", current_count)

    @api.model
    def _refresh_branches_after_replication(self):
        if not self.env.user.has_group("base.group_system"):
            raise AccessError(_("Only administrators can run the scheduled Eplus stock refresh."))
        Store = self.env["ab_eplus_stock_snapshot_store"].sudo()
        previous_count = Store.search_count([("active", "=", True)])
        try:
            self.action_refresh_branch_stock_from_eplus()
        except UserError as error:
            raise RetryableJobError(str(error), seconds=300) from error
        current_count = Store.search_count([("active", "=", True)])
        if not current_count or (previous_count and current_count < previous_count * 0.9):
            raise UserError(_("Eplus branch stock refresh returned too few rows; the previous snapshot was kept."))
        _logger.info("Eplus branch stock refreshed after replication: active=%s", current_count)


class EplusInventorySyncJob(models.Model):
    _inherit = "ab_eplus_inventory_sync_job"

    @api.model
    def _start_after_replication(self):
        if not self.env.user.has_group("base.group_system"):
            raise AccessError(_("Only administrators can run the scheduled Eplus stock refresh."))
        if self.sudo().search([("state", "=", "running")], limit=1):
            raise RetryableJobError(_("Another Eplus inventory sync is already running."), seconds=300)
        action = self.sudo().action_open_full_sync_console()
        job = self.sudo().browse(action["res_id"])
        job._prepare_full_sync()
        if job.state == "running":
            self.env.ref("ab_website_sale_product.ir_cron_process_eplus_inventory_sync_jobs").sudo()._trigger()
        _logger.info("Odoo inventory sync started after Eplus refresh: job=%s state=%s", job.id, job.state)


class WebsiteProductSyncJob(models.Model):
    _inherit = "ab_website_product_sync_job"

    @api.model
    def _start_after_replication(self):
        if not self.env.user.has_group("base.group_system"):
            raise AccessError(_("Only administrators can run the scheduled website product sync."))
        action = self.sudo().action_open_full_sync_console()
        job = self.sudo().browse(action["res_id"])
        if job.state != "running":
            result = job.action_start_full_sync()
            if result.get("tag") == "reload":
                raise RetryableJobError(_("Another website product sync is already running."), seconds=300)
        if job.state == "running":
            job.write({"background_requested": False})
            self.env.ref("ab_website_sale_product.ir_cron_process_website_product_sync_jobs").sudo()._trigger()
        _logger.info("Website product sync started after replication: job=%s state=%s", job.id, job.state)
