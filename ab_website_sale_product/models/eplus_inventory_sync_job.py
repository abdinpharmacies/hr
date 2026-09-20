import logging

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)


class EplusInventorySyncJob(models.Model):
    _name = "ab_eplus_inventory_sync_job"
    _description = "Eplus Inventory Sync Job"
    _order = "create_date desc, id desc"

    name = fields.Char(required=True, readonly=True, default=lambda self: _("Eplus Inventory Sync"))
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("running", "Running"),
            ("done", "Done"),
            ("failed", "Failed"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        required=True,
        readonly=True,
    )
    warehouse_id = fields.Many2one("stock.warehouse", readonly=True)
    location_id = fields.Many2one("stock.location", readonly=True)
    batch_size = fields.Integer(default=1000, readonly=True)
    total_count = fields.Integer(readonly=True)
    processed_count = fields.Integer(readonly=True)
    updated_count = fields.Integer(readonly=True)
    unchanged_count = fields.Integer(readonly=True)
    skipped_count = fields.Integer(readonly=True)
    failed_count = fields.Integer(readonly=True)
    progress = fields.Float(compute="_compute_progress", string="Progress")
    progress_style = fields.Char(compute="_compute_progress", string="Progress Style")
    progress_percent_label = fields.Char(compute="_compute_progress", string="Progress Label")
    status_title = fields.Char(compute="_compute_status_text", string="Status Title")
    status_text = fields.Char(compute="_compute_status_text", string="Status Text")
    last_message = fields.Char(readonly=True)
    date_start = fields.Datetime(readonly=True)
    date_done = fields.Datetime(readonly=True)
    line_ids = fields.One2many("ab_eplus_inventory_sync_job_line", "job_id", readonly=True)

    @api.depends("processed_count", "total_count", "state")
    def _compute_progress(self):
        for job in self:
            if job.total_count:
                progress = min(100.0, (job.processed_count / job.total_count) * 100.0)
            elif job.state == "done":
                progress = 100.0
            else:
                progress = 0.0
            job.progress = progress
            job.progress_style = "width: %.2f%%;" % progress
            job.progress_percent_label = "%.0f%%" % progress

    @api.depends("state", "processed_count", "total_count", "last_message")
    def _compute_status_text(self):
        for job in self:
            if job.state == "done":
                job.status_title = _("Inventory Fully Synchronized")
                job.status_text = _("All required products are synchronized with Odoo Inventory.")
            elif job.state == "failed":
                job.status_title = _("Inventory Sync Failed")
                job.status_text = job.last_message or _("The sync stopped before completion.")
            elif job.state == "cancelled":
                job.status_title = _("Inventory Sync Cancelled")
                job.status_text = job.last_message or _("The sync was cancelled.")
            elif job.state == "draft":
                job.status_title = _("Ready to Sync Inventory")
                job.status_text = job.last_message or _("Start a full sync to update Odoo Inventory from the current Eplus snapshot.")
            else:
                job.status_title = _("Inventory Sync In Progress")
                job.status_text = job.last_message or _("Odoo is processing Eplus stock in background batches.")

    @api.model
    def action_open_full_sync_console(self):
        running_job = self.search([("state", "=", "running")], limit=1)
        if running_job:
            return running_job.action_open()

        Snapshot = self.env["ab_eplus_stock_snapshot"].sudo()
        warehouse = Snapshot._get_inventory_sync_warehouse()
        location = warehouse.lot_stock_id
        if not location:
            raise UserError(_("The selected warehouse has no stock location."))
        job = self.create({
            "name": _("Eplus Inventory Sync"),
            "warehouse_id": warehouse.id,
            "location_id": location.id,
            "last_message": _("Ready to start full inventory sync from Eplus snapshot."),
        })
        return job.action_open()

    def action_start_full_sync(self):
        self.ensure_one()
        if self.state == "running":
            self.sudo()._process_all_remaining_batches()
            return {"type": "ir.actions.client", "tag": "reload"}

        self.sudo()._prepare_full_sync()
        self.env.ref("ab_website_sale_product.ir_cron_process_eplus_inventory_sync_jobs").sudo()._trigger()
        self.sudo()._process_batches(batch_count=1)
        return {"type": "ir.actions.client", "tag": "reload"}

    def _prepare_full_sync(self):
        self.ensure_one()
        running_job = self.search([("state", "=", "running")], limit=1)
        if running_job and running_job != self:
            raise UserError(_("Another Eplus inventory sync is already running."))

        Snapshot = self.env["ab_eplus_stock_snapshot"].sudo()
        warehouse = self.warehouse_id or Snapshot._get_inventory_sync_warehouse()
        location = self.location_id or warehouse.lot_stock_id
        if not location:
            raise UserError(_("The selected warehouse has no stock location."))

        groups = Snapshot._read_group(
            [("active", "=", True), ("product_id", "!=", False)],
            groupby=["product_id"],
            aggregates=["itm_qty:sum"],
        )
        if not groups:
            raise UserError(_("No matched Eplus stock rows are available to sync."))

        products_by_ab_product = Snapshot._get_inventory_sync_products(groups)
        candidate_vals = []
        skipped_count = 0
        for ab_product, eplus_qty in groups:
            product = products_by_ab_product.get(ab_product.id)
            if not product or product.type == "service":
                skipped_count += 1
                continue
            candidate_vals.append({
                "ab_product_id": ab_product.id,
                "product_product_id": product.id,
                "target_qty": max(eplus_qty or 0.0, 0.0),
            })

        if not candidate_vals and not skipped_count:
            raise UserError(_("No syncable products were found."))

        products = self.env["product.product"].sudo().browse([
            vals["product_product_id"] for vals in candidate_vals
        ])
        current_qty_by_product = Snapshot._get_inventory_sync_current_quantities(products, location)
        pending_vals = []
        unchanged_vals = []
        for vals in candidate_vals:
            product = products.browse(vals["product_product_id"])
            current_qty = current_qty_by_product.get(product.id, 0.0)
            rounding = product.uom_id.rounding
            if float_compare(current_qty, vals["target_qty"], precision_rounding=rounding) == 0:
                unchanged_vals.append(dict(vals, state="unchanged"))
            else:
                pending_vals.append(vals)

        processed_count = len(unchanged_vals)
        total_count = len(candidate_vals)
        has_pending = bool(pending_vals)
        self.line_ids.unlink()
        self.write({
            "name": _("Eplus Inventory Sync - %s") % fields.Datetime.now(),
            "warehouse_id": warehouse.id,
            "location_id": location.id,
            "state": "running" if has_pending else "done",
            "total_count": total_count,
            "processed_count": processed_count,
            "updated_count": 0,
            "unchanged_count": len(unchanged_vals),
            "skipped_count": skipped_count,
            "failed_count": 0,
            "date_start": fields.Datetime.now(),
            "date_done": fields.Datetime.now() if not has_pending else False,
            "last_message": _("Prepared %(total)s product(s). %(unchanged)s already matched, %(pending)s pending, %(skipped)s skipped.") % {
                "total": total_count,
                "unchanged": len(unchanged_vals),
                "pending": len(pending_vals),
                "skipped": skipped_count,
            },
        })
        Line = self.env["ab_eplus_inventory_sync_job_line"].sudo()
        line_vals = unchanged_vals + pending_vals
        for index in range(0, len(line_vals), 5000):
            Line.create([
                dict(vals, job_id=self.id)
                for vals in line_vals[index:index + 5000]
            ])
        if not has_pending:
            self._mark_done()

    def action_open(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Eplus Inventory Sync"),
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_process_next_batch(self):
        self.ensure_one()
        self.sudo()._process_batches(batch_count=1)
        return {"type": "ir.actions.client", "tag": "reload"}

    def action_process_to_completion(self):
        self.ensure_one()
        if self.state == "draft":
            self.sudo()._prepare_full_sync()
        self.sudo()._process_all_remaining_batches()
        return {"type": "ir.actions.client", "tag": "reload"}

    def action_open_eplus_stock(self):
        return self.env.ref("ab_website_sale_product.action_ab_eplus_stock_snapshot").read()[0]

    def action_cancel(self):
        self.filtered(lambda job: job.state in ("draft", "running")).write({
            "state": "cancelled",
            "date_done": fields.Datetime.now(),
            "last_message": _("Sync cancelled."),
        })

    @api.model
    def cron_process_inventory_sync_jobs(self):
        jobs = self.sudo().search([("state", "=", "running")], order="id", limit=1)
        for job in jobs:
            job._process_batches(batch_count=5)

    def _process_batches(self, batch_count=1):
        for job in self:
            for __index in range(batch_count):
                if job.state != "running":
                    break
                if not job._process_next_batch():
                    break

    def _process_all_remaining_batches(self):
        for job in self:
            while job.state == "running":
                if not job._process_next_batch():
                    break

    def _process_next_batch(self):
        self.ensure_one()
        pending_lines = self.line_ids.filtered(lambda line: line.state == "pending")[:self.batch_size]
        if not pending_lines:
            self._mark_done()
            return False

        Snapshot = self.env["ab_eplus_stock_snapshot"].sudo()
        Quant = self.env["stock.quant"].sudo().with_context(inventory_mode=True)
        products = pending_lines.product_product_id.sudo()
        current_qty_by_product = Snapshot._get_inventory_sync_current_quantities(products, self.location_id)
        base_quant_by_product = Snapshot._get_inventory_sync_base_quants(products, self.location_id)
        quants_to_apply = Quant.browse()
        create_vals = []
        updated_lines = self.env["ab_eplus_inventory_sync_job_line"].sudo()
        unchanged_lines = self.env["ab_eplus_inventory_sync_job_line"].sudo()
        skipped_lines = self.env["ab_eplus_inventory_sync_job_line"].sudo()

        for line in pending_lines:
            product = line.product_product_id
            if not product or product.type == "service":
                skipped_lines |= line
                continue

            current_qty = current_qty_by_product.get(product.id, 0.0)
            rounding = product.uom_id.rounding
            if float_compare(current_qty, line.target_qty, precision_rounding=rounding) == 0:
                unchanged_lines |= line
                continue

            base_quant = base_quant_by_product.get(product.id)
            delta_qty = line.target_qty - current_qty
            if base_quant:
                base_quant.inventory_quantity = base_quant.quantity + delta_qty
                quants_to_apply |= base_quant
            else:
                create_vals.append({
                    "product_id": product.id,
                    "location_id": self.location_id.id,
                    "inventory_quantity": delta_qty,
                })
            updated_lines |= line

        try:
            if create_vals:
                quants_to_apply |= Quant.create(create_vals)
            if quants_to_apply:
                quants_to_apply.action_apply_inventory()
        except Exception as error:
            _logger.exception("Eplus inventory sync job %s failed", self.id)
            pending_lines.write({"state": "failed", "message": str(error)})
            self.write({
                "state": "failed",
                "failed_count": self.failed_count + len(pending_lines),
                "processed_count": self.processed_count + len(pending_lines),
                "date_done": fields.Datetime.now(),
                "last_message": _("Sync failed: %s") % str(error),
            })
            return False

        updated_lines.write({"state": "updated"})
        unchanged_lines.write({"state": "unchanged"})
        skipped_lines.write({"state": "skipped"})

        processed_now = len(pending_lines)
        self.write({
            "processed_count": self.processed_count + processed_now,
            "updated_count": self.updated_count + len(updated_lines),
            "unchanged_count": self.unchanged_count + len(unchanged_lines),
            "skipped_count": self.skipped_count + len(skipped_lines),
            "last_message": _(
                "Processed %(processed)s of %(total)s product(s)."
            ) % {
                "processed": min(self.total_count, self.processed_count + processed_now),
                "total": self.total_count,
            },
        })
        if self.processed_count >= self.total_count:
            self._mark_done()
            return False
        return True

    def _mark_done(self):
        self.write({
            "state": "done",
            "processed_count": self.total_count,
            "date_done": fields.Datetime.now(),
            "last_message": _("Dashboard fully synchronized."),
        })


class EplusInventorySyncJobLine(models.Model):
    _name = "ab_eplus_inventory_sync_job_line"
    _description = "Eplus Inventory Sync Job Line"
    _order = "id"

    job_id = fields.Many2one("ab_eplus_inventory_sync_job", required=True, ondelete="cascade")
    ab_product_id = fields.Many2one("ab_product", string="Abdin Product", readonly=True)
    product_product_id = fields.Many2one("product.product", string="Odoo Product", readonly=True)
    target_qty = fields.Float(string="Eplus Quantity", readonly=True)
    state = fields.Selection(
        selection=[
            ("pending", "Pending"),
            ("updated", "Updated"),
            ("unchanged", "Unchanged"),
            ("skipped", "Skipped"),
            ("failed", "Failed"),
        ],
        default="pending",
        required=True,
        readonly=True,
    )
    message = fields.Char(readonly=True)
