import logging
import time

from psycopg2.errors import DeadlockDetected, SerializationFailure

from odoo import SUPERUSER_ID, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _

from .ab_product import WEBSITE_SYNC_CHUNK_SIZE

_logger = logging.getLogger(__name__)
WEBSITE_SYNC_WORKER_LOCK = (190019, 732)


class WebsiteProductSyncJob(models.Model):
    _name = "ab_website_product_sync_job"
    _description = "Website Product Sync Job"
    _order = "create_date desc, id desc"
    _one_running_job = models.UniqueIndex(
        "(state) WHERE state = 'running'", "Another website product sync is already running.",
    )

    name = fields.Char(required=True, readonly=True, default=lambda self: _("Website Product Sync"))
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
    batch_size_option = fields.Selection(
        selection=[
            ("250", "250"),
            ("500", "500"),
            ("1000", "1000"),
            ("5000", "5000"),
            ("10000", "10000"),
            ("15000", "15000"),
        ],
        string="Batch Size",
        default="250",
        help="Number of products processed by Process Next Batch. Internal chunks are limited to 250 products; background processing commits after each chunk.",
    )
    batch_size = fields.Integer(default=250, readonly=True)
    total_count = fields.Integer(readonly=True)
    processed_count = fields.Integer(readonly=True)
    created_count = fields.Integer(readonly=True)
    updated_count = fields.Integer(readonly=True)
    skipped_count = fields.Integer(readonly=True)
    failed_count = fields.Integer(readonly=True)
    unchanged_count = fields.Integer(string="Unchanged", readonly=True)
    already_synced_count = fields.Integer(string="Already Synchronized", readonly=True, copy=False)
    catalog_count = fields.Integer(string="Catalog Products", compute="_compute_progress")
    completed_count = fields.Integer(string="Synchronized Products", compute="_compute_progress")
    remaining_count = fields.Integer(string="Remaining Products", compute="_compute_progress")
    missing_count = fields.Integer(string="Missing on Website", compute="_compute_remaining_types")
    review_count = fields.Integer(string="Needs Review", compute="_compute_remaining_types")
    sync_mode = fields.Selection(
        [("full", "Full Sync"), ("delta", "Changed Products")], default="full", readonly=True,
        string="Sync Mode",
    )
    progress = fields.Float(compute="_compute_progress", string="Progress")
    progress_style = fields.Char(compute="_compute_progress", string="Progress Style")
    progress_percent_label = fields.Char(compute="_compute_progress", string="Progress Label")
    status_title = fields.Char(compute="_compute_status_text", string="Status Title")
    status_text = fields.Char(compute="_compute_status_text", string="Status Text")
    last_message = fields.Char(readonly=True)
    date_start = fields.Datetime(readonly=True)
    date_done = fields.Datetime(readonly=True)
    line_ids = fields.One2many("ab_website_product_sync_job_line", "job_id", readonly=True)
    background_requested = fields.Boolean(string="Background Sync Requested", readonly=True, copy=False)
    background_user_id = fields.Many2one("res.users", string="Background Sync Requested By", readonly=True, copy=False)
    background_company_id = fields.Many2one("res.company", string="Background Sync Company", readonly=True, copy=False)
    background_error = fields.Text(string="Background Sync Error", readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            batch_size_option = vals.get("batch_size_option")
            if batch_size_option and "batch_size" not in vals:
                vals["batch_size"] = int(batch_size_option)
        return super().create(vals_list)

    def write(self, vals):
        if vals.get("batch_size_option") and "batch_size" not in vals:
            vals = dict(vals, batch_size=int(vals["batch_size_option"]))
        return super().write(vals)

    @api.depends("processed_count", "total_count", "already_synced_count", "failed_count", "state")
    def _compute_progress(self):
        for job in self:
            total = job.total_count + job.already_synced_count
            completed = job.already_synced_count + max(job.processed_count - job.failed_count, 0)
            if total:
                progress = min(100.0, (completed / total) * 100.0)
            elif job.state == "done":
                progress = 100.0
            else:
                progress = 0.0
            job.progress = progress
            job.catalog_count = total
            job.completed_count = completed
            job.remaining_count = max(job.total_count - job.processed_count, 0) + job.failed_count
            job.progress_style = "width: %.2f%%;" % progress
            job.progress_percent_label = "%.2f%%" % (min(progress, 99.99) if job.remaining_count else progress)

    @api.depends("line_ids.state", "line_ids.operation")
    def _compute_remaining_types(self):
        counts = self.env["ab_website_product_sync_job_line"]._read_group(
            fields.Domain("job_id", "in", self.ids) & fields.Domain("state", "in", ("pending", "failed")),
            ["job_id", "operation"], ["__count"],
        )
        by_job = {(job.id, operation): count for job, operation, count in counts}
        for job in self:
            job.missing_count = by_job.get((job.id, "create"), 0)
            job.review_count = by_job.get((job.id, "update"), 0)

    @api.depends("state", "processed_count", "total_count", "last_message", "background_requested")
    def _compute_status_text(self):
        for job in self:
            if job.state == "done":
                job.status_title = _("Products Fully Synchronized")
                job.status_text = _("All selected Abdin products are synchronized with the website shop.")
            elif job.state == "failed":
                job.status_title = _("Product Sync Failed")
                job.status_text = job.last_message or _("The sync stopped before completion.")
            elif job.state == "cancelled":
                job.status_title = _("Product Sync Cancelled")
                job.status_text = job.last_message or _("The sync was cancelled.")
            elif job.state == "draft":
                job.status_title = _("Checking Remaining Products") if job.background_requested else _("Ready to Sync Products")
                job.status_text = job.last_message or _("Start a full sync to create or update website products from Abdin products.")
            else:
                job.status_title = _("Product Sync In Progress")
                job.status_text = job.last_message or _("Odoo is processing Abdin products in background batches.")

    @api.model
    def action_open_full_sync_console(self):
        existing = self._find_unfinished_job()
        if existing:
            return existing.action_open()
        job = self.create({
            "name": _("Website Product Sync"),
            "last_message": _("Ready to start full website product sync."),
        })
        return job.action_open()

    def action_start_full_sync(self):
        self.ensure_one()
        self.check_access("write")
        if not self.env["ab_product"]._lock_website_sync(wait=False):
            return {"type": "ir.actions.client", "tag": "reload"}
        job = self._continuation_job()
        if not job.background_requested:
            if job.state == "draft":
                job.sudo()._prepare_full_sync()
            else:
                job.sudo()._skip_clean_pending_lines()
        return job.action_open()

    @api.model
    def _find_unfinished_job(self):
        running = self.search(fields.Domain("state", "=", "running"), limit=1)
        if running:
            return running
        completed = self.search(fields.Domain("state", "=", "done")
                                & fields.Domain("sync_mode", "=", "full"), order="id desc", limit=1)
        return self.search(
            fields.Domain("state", "in", ("cancelled", "failed"))
            & fields.Domain("id", ">", completed.id or 0)
            & fields.Domain("line_ids", "any", [("state", "in", ("pending", "failed"))]), limit=1,
        )

    def _continuation_job(self):
        self.ensure_one()
        existing = self._find_unfinished_job()
        if existing:
            return existing
        if self.state == "draft":
            return self
        return self.create({"batch_size_option": self.batch_size_option or "250"})

    def action_show_remaining(self):
        self.ensure_one()
        self.check_access("read")
        return {
            "type": "ir.actions.act_window", "name": _("Remaining Products"),
            "res_model": "ab_website_product_sync_job_line", "view_mode": "list",
            "views": [(self.env.ref("ab_website_sale_product.ab_website_product_sync_remaining_view_list").id, "list")],
            "domain": [("job_id", "=", self.id), ("state", "in", ("pending", "failed"))],
        }

    @api.model
    def _full_sync_product_domain(self):
        return fields.Domain([
            ("active", "=", True),
            ("allow_sale", "=", True),
            ("website_sale_available", "=", True),
        ])

    def _prepare_full_sync(self):
        self.ensure_one()
        self.env["ab_product"]._lock_website_sync()
        running_job = self.search([("state", "=", "running")], limit=1)
        if running_job and running_job != self:
            raise UserError(_("Another website product sync is already running."))

        Product = self.env["ab_product"].sudo().with_context(active_test=False)
        domain = self._full_sync_product_domain()
        catalog_count = Product.search_count(domain)
        domain &= fields.Domain("website_sync_pending", "=", True) | fields.Domain("website_sync_template_ids", "=", False)
        last_product = Product.search(domain, order="id desc", limit=1)
        if not catalog_count:
            raise UserError(_("No website-available Abdin products were found."))

        self.write({
            "name": _("Website Product Sync - %s") % fields.Datetime.now(),
            "state": "running",
            "batch_size": self._get_batch_size(),
            "total_count": 0,
            "processed_count": 0,
            "created_count": 0,
            "updated_count": 0,
            "skipped_count": 0,
            "failed_count": 0,
            "unchanged_count": 0,
            "already_synced_count": catalog_count,
            "sync_mode": "full",
            "date_start": fields.Datetime.now(),
            "date_done": False,
        })
        last_id = 0
        upper_id = last_product.id if last_product else 0
        total = 0
        while True:
            products = Product.search(domain & fields.Domain("id", ">", last_id)
                                      & fields.Domain("id", "<=", upper_id), order="id", limit=2000)
            if not products:
                break
            self._add_product_lines(products)
            last_id = products[-1].id
            total += len(products)
            self.env.invalidate_all()
        self.write({
            "total_count": total,
            "already_synced_count": catalog_count - total,
            "last_message": _("%(ready)s already synchronized; %(remaining)s product(s) need creation or review.") % {
                "ready": catalog_count - total, "remaining": total,
            },
        })
        if not total:
            self._mark_done()

    def _skip_clean_pending_lines(self):
        self.ensure_one()
        Line = self.env["ab_website_product_sync_job_line"].sudo()
        domain = fields.Domain("job_id", "=", self.id) & fields.Domain("state", "=", "pending")
        domain &= fields.Domain("ab_product_id.website_sync_pending", "=", False)
        domain &= fields.Domain("ab_product_id.website_sync_template_ids", "!=", False)
        count = 0
        while lines := Line.with_context(active_test=False).search(domain, order="id", limit=2000):
            lines.write({"state": "unchanged"})
            count += len(lines)
        if count:
            self.write({"processed_count": self.processed_count + count,
                        "unchanged_count": self.unchanged_count + count})
            self.last_message = _("%(ready)s already synchronized; %(remaining)s product(s) need creation or review.") % {
                "ready": self.completed_count, "remaining": self.remaining_count,
            }
        if self.processed_count >= self.total_count:
            self._mark_done()

    def _add_product_lines(self, products):
        templates = self.env["product.template"].sudo().with_context(active_test=False).search(
            fields.Domain("ab_product_id", "in", products.ids),
        )
        by_product = {template.ab_product_id.id: template.id for template in templates}
        self.env["ab_website_product_sync_job_line"].sudo().create([
            {"job_id": self.id, "ab_product_id": product.id,
             "product_template_id": by_product.get(product.id, False),
             "operation": "update" if product.id in by_product else "create"}
            for product in products
        ])

    def action_start_delta_sync(self):
        self.check_access("write")
        job = self.sudo()._queue_delta_sync()
        return job.action_open() if job else {"type": "ir.actions.client", "tag": "reload"}

    @api.model
    def _queue_delta_sync(self, limit=1000):
        Product = self.env["ab_product"].sudo().with_context(active_test=False)
        if not Product._lock_website_sync(wait=False):
            return self.browse()
        running = self.sudo().search(fields.Domain("state", "=", "running"), limit=1)
        if running:
            return running
        products = Product.search(fields.Domain("website_sync_pending", "=", True), order="id", limit=min(max(limit, 1), 5000))
        if not products:
            return self.browse()
        linked = self.env["product.template"].sudo().with_context(active_test=False).search(
            fields.Domain("ab_product_id", "in", products.ids),
        ).ab_product_id
        eligible = products.filtered(lambda p: p.active and p.allow_sale and p.website_sale_available)
        selected = products & (linked | eligible)
        (products - selected).write({"website_sync_pending": False})
        if not selected:
            return self.browse()
        job = self.sudo().create({
            "state": "running", "sync_mode": "delta", "total_count": len(selected),
            "date_start": fields.Datetime.now(),
        })
        job._add_product_lines(selected)
        self.env.ref("ab_website_sale_product.ir_cron_process_website_product_sync_jobs").sudo()._trigger()
        return job

    def action_retry_failed(self):
        self.ensure_one()
        self.check_access("write")
        if not self.env["ab_product"]._lock_website_sync(wait=False):
            return {"type": "ir.actions.client", "tag": "reload"}
        if not self.try_lock_for_update():
            return {"type": "ir.actions.client", "tag": "reload"}
        failed = self.env["ab_website_product_sync_job_line"].sudo().search(
            fields.Domain("job_id", "=", self.id) & fields.Domain("state", "=", "failed"),
        )
        if failed:
            failed.write({"state": "pending"})
            self.write({"state": "running", "date_done": False, "failed_count": 0,
                        "processed_count": self.processed_count - len(failed)})
            self.env.ref("ab_website_sale_product.ir_cron_process_website_product_sync_jobs").sudo()._trigger()
        return {"type": "ir.actions.client", "tag": "reload"}

    def action_open(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Website Product Sync"),
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_process_next_batch(self):
        self.ensure_one()
        self.check_access("write")
        if self.background_requested:
            raise UserError(_("Full sync is already running in the background."))
        self.sudo()._process_batches(batch_count=1)
        return {"type": "ir.actions.client", "tag": "reload"}

    def action_process_to_completion(self):
        self.ensure_one()
        self.check_access("write")
        if self.background_requested:
            return {"type": "ir.actions.client", "tag": "reload"}
        if not self._background_worker_online():
            raise UserError(_("The dedicated Website Product Sync worker is offline. Start the module worker service and try again."))
        job = self._continuation_job()
        job.check_access("write")
        if job.state in ("cancelled", "failed"):
            if job.failed_count:
                job.action_retry_failed()
            elif job.state == "cancelled":
                job.write({"state": "running", "date_done": False})
        if job.state not in ("draft", "running"):
            return job.action_open()
        job.write({
            "background_requested": True,
            "background_user_id": self.env.uid,
            "background_company_id": self.env.company.id,
            "background_error": False,
            "last_message": _("All remaining products are queued for background synchronization."),
        })
        return {"type": "ir.actions.client", "tag": "reload"} if job == self else job.action_open()

    @api.model
    def _background_worker_online(self):
        self.env.cr.execute("SELECT pg_try_advisory_lock(%s, %s)", WEBSITE_SYNC_WORKER_LOCK)
        acquired = self.env.cr.fetchone()[0]
        if acquired:
            self.env.cr.execute("SELECT pg_advisory_unlock(%s, %s)", WEBSITE_SYNC_WORKER_LOCK)
        return not acquired

    def _process_background_checkpoint(self):
        self.ensure_one()
        if not self.env["ab_product"]._lock_website_sync(wait=False) or not self.try_lock_for_update():
            return 0
        self.invalidate_recordset()
        if not self.background_requested or self.state not in ("draft", "running"):
            return 0
        user = self.background_user_id
        company = self.background_company_id
        if (not user.active and user.id != SUPERUSER_ID) or company not in user.company_ids:
            raise UserError(_("The background sync requester no longer has access to this company."))
        authorized = self.with_user(user).with_context(allowed_company_ids=company.ids)
        authorized.check_access("write")
        if self.state == "draft":
            authorized.sudo()._prepare_full_sync()
            return 0
        authorized.sudo()._skip_clean_pending_lines()
        before = self.processed_count
        authorized.sudo()._process_next_batch(limit=WEBSITE_SYNC_CHUNK_SIZE)
        return self.processed_count - before

    def get_background_progress(self):
        self.ensure_one()
        self.check_access("read")
        return self.read([
            "state", "processed_count", "total_count", "already_synced_count", "background_requested", "background_error",
        ])[0]

    def action_open_abdin_products(self):
        return self.env.ref("ab_website_sale_product.action_ab_products_ecommerce_sync").read()[0]

    def action_cancel(self):
        self.filtered(lambda job: job.state in ("draft", "running")).write({
            "state": "cancelled",
            "background_requested": False,
            "date_done": fields.Datetime.now(),
            "last_message": _("Sync cancelled."),
        })

    @api.model
    def cron_process_website_product_sync_jobs(self):
        self.check_access("write")
        cron = self.env["ir.cron"]
        while True:
            jobs = self.sudo().search(fields.Domain("state", "=", "running")
                                      & fields.Domain("background_requested", "=", False), order="id", limit=1)
            if not jobs:
                return
            before = jobs.processed_count
            more = jobs._process_next_batch()
            processed = jobs.processed_count - before
            remaining = max(jobs.total_count - jobs.processed_count, 0)
            if not processed and more:
                return
            if not cron._commit_progress(processed, remaining=remaining) or not more:
                return

    def _process_batches(self, batch_count=1):
        for job in self:
            for __index in range(batch_count):
                remaining = job._get_batch_size()
                while remaining > 0 and job.state == "running":
                    before = job.processed_count
                    more = job._process_next_batch(limit=remaining)
                    processed = job.processed_count - before
                    remaining -= processed
                    if not more or processed <= 0:
                        break
                if job.state != "running" or remaining > 0:
                    break

    def _process_all_remaining_batches(self):
        return self.action_process_to_completion()

    def _get_batch_size(self):
        self.ensure_one()
        return max(int(self.batch_size_option or self.batch_size or 250), 1)

    def _process_next_batch(self, limit=None):
        self.ensure_one()
        if not self.env["ab_product"]._lock_website_sync(wait=False) or not self.try_lock_for_update():
            return True
        self.invalidate_recordset()
        if self.state != "running":
            return False
        pending_lines = self.env["ab_website_product_sync_job_line"].sudo().search([
            ("job_id", "=", self.id),
            ("state", "=", "pending"),
        ], order="id", limit=min(self._get_batch_size() if limit is None else limit, WEBSITE_SYNC_CHUNK_SIZE))
        if not pending_lines:
            self._mark_done()
            return False

        started = time.monotonic()
        queries = self.env.cr.sql_log_count
        products = pending_lines.ab_product_id.sudo()
        eligible = products.filtered(lambda p: p.active and p.allow_sale and p.website_sale_available)
        if self.sync_mode == "delta":
            eligible |= self.env["product.template"].sudo().with_context(active_test=False).search(
                fields.Domain("ab_product_id", "in", products.ids),
            ).ab_product_id
        results = self._sync_products_with_recovery(eligible)
        state_ids = {state: [] for state in ("created", "updated", "unchanged", "skipped", "failed")}
        attempts_by_state = {}
        for line in pending_lines:
            template_id, state, message = results.get(line.ab_product_id.id, (line.product_template_id.id, "skipped", False))
            if state == "failed":
                template_id = line.product_template_id.id
            state_ids[state].append(line.id)
            attempts_by_state.setdefault((state, line.attempts + 1), []).append(line.id)
            values = {}
            if line.product_template_id.id != template_id:
                values["product_template_id"] = template_id
            if line.message != message:
                values["message"] = message
            if values:
                line.write(values)
        for (state, attempts), line_ids in attempts_by_state.items():
            self.env["ab_website_product_sync_job_line"].browse(line_ids).write({"state": state, "attempts": attempts})

        processed_now = len(pending_lines)
        self.write({
            "processed_count": self.processed_count + processed_now,
            "created_count": self.created_count + len(state_ids["created"]),
            "updated_count": self.updated_count + len(state_ids["updated"]),
            "unchanged_count": self.unchanged_count + len(state_ids["unchanged"]),
            "skipped_count": self.skipped_count + len(state_ids["skipped"]),
            "failed_count": self.failed_count + len(state_ids["failed"]),
            "last_message": _("Processed %(processed)s of %(total)s product(s).") % {
                "processed": min(self.total_count, self.processed_count + processed_now),
                "total": self.total_count,
            },
        })
        elapsed = time.monotonic() - started
        _logger.info("Website sync job=%s products=%s seconds=%.3f products_sec=%.2f queries=%s outcomes=%s",
                     self.id, processed_now, elapsed, processed_now / max(elapsed, 0.001),
                     self.env.cr.sql_log_count - queries, {state: len(ids) for state, ids in state_ids.items()})
        if self.processed_count >= self.total_count:
            self._mark_done()
            return False
        return True

    def _sync_products_with_recovery(self, products):
        if not products:
            return {}
        try:
            with self.env.cr.savepoint():
                outcomes = {}
                templates = products._sync_website_products(outcomes=outcomes)
                result = {template.ab_product_id.id: (template.id, outcomes[template.ab_product_id.id], False)
                          for template in templates}
            return result
        except (SerializationFailure, DeadlockDetected):
            raise
        except Exception as error:
            if len(products) == 1:
                _logger.exception("Website sync job %s failed for ab_product %s", self.id, products.id)
                return {products.id: (False, "failed", str(error))}
        middle = len(products) // 2
        return {**self._sync_products_with_recovery(products[:middle]),
                **self._sync_products_with_recovery(products[middle:])}

    def _mark_done(self):
        self.background_requested = False
        if self.failed_count:
            self.write({
                "state": "failed",
                "processed_count": self.total_count,
                "date_done": fields.Datetime.now(),
                "last_message": _("Product sync completed with %(failed)s failed product(s).") % {
                    "failed": self.failed_count,
                },
            })
            return
        self.write({
            "state": "done",
            "processed_count": self.total_count,
            "date_done": fields.Datetime.now(),
            "last_message": _("Website products fully synchronized."),
        })


class WebsiteProductSyncJobLine(models.Model):
    _name = "ab_website_product_sync_job_line"
    _description = "Website Product Sync Job Line"
    _order = "id"
    _pending_job_idx = models.Index("(job_id, id) WHERE state = 'pending'")

    job_id = fields.Many2one("ab_website_product_sync_job", required=True, ondelete="cascade")
    attempts = fields.Integer(string="Attempts", readonly=True)
    ab_product_id = fields.Many2one("ab_product", string="Abdin Product", readonly=True)
    product_template_id = fields.Many2one("product.template", string="Website Product", readonly=True)
    operation = fields.Selection(
        selection=[
            ("create", "Create"),
            ("update", "Update"),
        ],
        readonly=True,
    )
    state = fields.Selection(
        selection=[
            ("pending", "Pending"),
            ("created", "Created"),
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
