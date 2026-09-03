import hashlib
import logging

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools import ormcache
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)

_HISTORICAL_RUNNING_STATES = {"queued", "running"}
_HISTORICAL_TERMINAL_STATES = {"done", "failed", "cancelled"}
_HISTORICAL_UPLOAD_CHANNEL = "root.historical_sales"


class AbOdooSyncUploadSource(models.Model):
    _name = "ab_odoo_sync_upload_source"
    _description = "AB Odoo Sync Upload Source"
    _order = "model_name"

    model_name = fields.Char(string="Source Model", required=True, index=True)
    aggregate_parent_field = fields.Char(
        string="Aggregate Parent Field",
        help="Optional Many2one field whose parent must be re-snapshotted after this model changes.",
    )
    historical_upload_months = fields.Integer(
        string="Historical Upload Past Months",
        default=0,
        help=(
            "Set past months to fill Historical Upload From quickly. "
            "It does not start a backfill by itself."
        ),
    )
    historical_upload_from = fields.Datetime(
        string="Historical Upload From",
        help=(
            "UTC datetime cutoff for manual historical upload backfills. "
            "Records with write_date on or after this value are eligible."
        ),
    )
    historical_upload_state = fields.Selection(
        selection=[
            ("not_started", "Not Started"),
            ("queued", "Queued"),
            ("running", "Running"),
            ("done", "Done"),
            ("failed", "Failed"),
            ("cancelled", "Cancelled"),
        ],
        string="Historical Upload State",
        default="not_started",
        required=True,
        readonly=True,
        index=True,
    )
    historical_upload_frozen_until = fields.Datetime(
        string="Historical Upload Frozen Until",
        readonly=True,
    )
    historical_upload_cursor_write_date = fields.Datetime(
        string="Historical Upload Cursor Write Date",
        readonly=True,
    )
    historical_upload_cursor_id = fields.Integer(
        string="Historical Upload Cursor ID",
        readonly=True,
    )
    historical_upload_processed_count = fields.Integer(
        string="Historical Upload Processed Count",
        readonly=True,
    )
    historical_upload_queued_count = fields.Integer(
        string="Historical Upload Queued Count",
        readonly=True,
    )
    historical_upload_skipped_count = fields.Integer(
        string="Historical Upload Skipped Count",
        readonly=True,
    )
    historical_upload_last_error = fields.Text(
        string="Historical Upload Last Error",
        readonly=True,
    )
    historical_upload_completed_at = fields.Datetime(
        string="Historical Upload Completed At",
        readonly=True,
    )
    active = fields.Boolean(default=False, index=True)

    _uniq_model_name = models.Constraint(
        "UNIQUE(model_name)",
        "Source model must be unique in upload sources.",
    )

    @ormcache("dbname", "model_name", cache="stable")
    def _is_upload_source_cached(self, dbname, model_name):
        if not model_name:
            return False
        self.flush_model(["model_name", "active"])
        self.env.cr.execute(
            """
            SELECT 1
              FROM ab_odoo_sync_upload_source
             WHERE active = TRUE
               AND model_name = %s
             LIMIT 1
            """,
            (model_name,),
        )
        return bool(self.env.cr.fetchone())

    @api.model
    def is_upload_source(self, model_name):
        if not model_name:
            return False
        if self.env["ab_odoo_sync_rules"].sudo().is_upload_source_forbidden(model_name):
            return False
        try:
            return bool(self._is_upload_source_cached(self.env.cr.dbname, model_name))
        except Exception:
            # The table may not be available during early registry setup.
            return False

    @api.constrains("historical_upload_months")
    def _check_historical_upload_months(self):
        for record in self:
            if record.historical_upload_months < 0:
                raise ValidationError(
                    _("Historical Upload Past Months cannot be negative.")
                )

    @api.constrains("historical_upload_from")
    def _check_historical_upload_from(self):
        now = fields.Datetime.now()
        for record in self:
            if record.historical_upload_from and record.historical_upload_from > now:
                raise ValidationError(_("Historical Upload From cannot be in the future."))

    @api.onchange("historical_upload_months")
    def _onchange_historical_upload_months(self):
        for record in self:
            if record.historical_upload_months > 0:
                record.historical_upload_from = fields.Datetime.now() - relativedelta(
                    months=record.historical_upload_months
                )

    @api.constrains("model_name", "aggregate_parent_field")
    def _check_model_name(self):
        for record in self:
            if record.model_name not in self.env:
                raise ValidationError(
                    _("Source model %(model)s is not installed in this database.")
                    % {"model": record.model_name}
                )
            if self.env["ab_odoo_sync_rules"].sudo().is_upload_source_forbidden(record.model_name):
                raise ValidationError(
                    _("Source model %(model)s is protected by sync-rules.md and cannot be a branch upload source.")
                    % {"model": record.model_name}
                )
            if record.aggregate_parent_field:
                field = self.env[record.model_name]._fields.get(
                    record.aggregate_parent_field
                )
                if not field or field.type != "many2one":
                    raise ValidationError(
                        _("Aggregate parent field %(field)s must be a Many2one on %(model)s.")
                        % {
                            "field": record.aggregate_parent_field,
                            "model": record.model_name,
                        }
                    )

    @api.model
    def get_aggregate_parents(self, records):
        if not records:
            return False
        source = self.sudo().search(
            [
                ("model_name", "=", records._name),
                ("active", "=", True),
            ],
            limit=1,
        )
        if not source or not source.aggregate_parent_field:
            return False
        return records.mapped(source.aggregate_parent_field).exists()

    @api.model
    def _historical_upload_reset_values(self):
        return {
            "historical_upload_state": "not_started",
            "historical_upload_frozen_until": False,
            "historical_upload_cursor_write_date": False,
            "historical_upload_cursor_id": 0,
            "historical_upload_processed_count": 0,
            "historical_upload_queued_count": 0,
            "historical_upload_skipped_count": 0,
            "historical_upload_last_error": False,
            "historical_upload_completed_at": False,
        }

    def _check_historical_upload_admin(self):
        if not self.env.user.has_group("base.group_system"):
            raise AccessError(
                _("Only System administrators can manage historical upload backfills.")
            )

    def _get_historical_upload_model(self):
        self.ensure_one()
        if self.model_name not in self.env:
            raise UserError(
                _("Source model %(model)s is not installed in this database.")
                % {"model": self.model_name}
            )
        if self.env["ab_odoo_sync_rules"].sudo().is_upload_source_forbidden(self.model_name):
            raise UserError(
                _("Source model %(model)s is protected by sync-rules.md and cannot be a branch upload source.")
                % {"model": self.model_name}
            )
        return self.env[self.model_name].with_context(active_test=False).sudo()

    def _validate_historical_upload_queue(self):
        now = fields.Datetime.now()
        for source in self:
            if not source.active:
                raise UserError(
                    _("Activate %(model)s before queuing historical upload.")
                    % {"model": source.model_name}
                )
            if not source.historical_upload_from:
                raise UserError(
                    _("Set Historical Upload From before queuing historical upload for %(model)s.")
                    % {"model": source.model_name}
                )
            if source.historical_upload_from > now:
                raise UserError(
                    _("Historical Upload From cannot be in the future for %(model)s.")
                    % {"model": source.model_name}
                )
            model = source._get_historical_upload_model()
            write_date_field = model._fields.get("write_date")
            if not write_date_field or not write_date_field.store:
                raise UserError(
                    _("Source model %(model)s must have a stored write_date field for historical upload.")
                    % {"model": source.model_name}
                )

    def _historical_upload_identity_key(self):
        self.ensure_one()
        raw = "%s:%s:%s:%s:%s" % (
            self.id,
            self.historical_upload_from or "",
            self.historical_upload_frozen_until or "",
            self.historical_upload_cursor_write_date or "",
            self.historical_upload_cursor_id or 0,
        )
        digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()
        return f"ab_odoo_sync_historical_upload:{self.id}:{digest}"

    def _schedule_historical_upload_batch(self):
        self.ensure_one()
        if self.historical_upload_state not in _HISTORICAL_RUNNING_STATES:
            return False
        self.sudo().with_delay(
            identity_key=self._historical_upload_identity_key(),
            description=_("Queue historical branch upload batch"),
            max_retries=0,
            channel=_HISTORICAL_UPLOAD_CHANNEL,
        ).job_queue_historical_upload_batch()
        return True

    def _historical_upload_domain(self):
        self.ensure_one()
        domain = (
            fields.Domain("write_date", ">=", self.historical_upload_from)
            & fields.Domain("write_date", "<=", self.historical_upload_frozen_until)
        )
        if self.historical_upload_cursor_write_date:
            cursor_domain = fields.Domain(
                "write_date", "<", self.historical_upload_cursor_write_date
            ) | (
                fields.Domain(
                    "write_date", "=", self.historical_upload_cursor_write_date
                )
                & fields.Domain("id", "<", self.historical_upload_cursor_id or 0)
            )
            domain &= cursor_domain
        return domain

    def _process_historical_upload_batch(self):
        self.ensure_one()
        if self.historical_upload_state not in _HISTORICAL_RUNNING_STATES:
            return {"status": "skipped", "processed": 0, "queued": 0, "skipped": 0}
        if not self.historical_upload_frozen_until:
            self.with_context(skip_ab_odoo_sync_upload_source_guard=True).sudo().write(
                {"historical_upload_frozen_until": fields.Datetime.now()}
            )

        if self.historical_upload_state == "queued":
            self.with_context(skip_ab_odoo_sync_upload_source_guard=True).sudo().write(
                {
                    "historical_upload_state": "running",
                    "historical_upload_last_error": False,
                }
            )

        Model = self._get_historical_upload_model().with_context(
            skip_ab_odoo_sync_upload=True
        )
        batch_size = self.env["ab_odoo_sync_service"].sudo().get_batch_size()
        records = Model.search(
            list(self._historical_upload_domain()),
            order="write_date DESC, id DESC",
            limit=batch_size,
        )
        if not records:
            self.with_context(skip_ab_odoo_sync_upload_source_guard=True).sudo().write(
                {
                    "historical_upload_state": "done",
                    "historical_upload_completed_at": fields.Datetime.now(),
                    "historical_upload_last_error": False,
                }
            )
            return {"status": "done", "processed": 0, "queued": 0, "skipped": 0}

        Outbox = self.env["ab_odoo_sync_outbox"].with_context(
            skip_ab_odoo_sync_upload=True,
            defer_ab_odoo_sync_upload_sender=True,
        ).sudo()
        snapshots = Outbox.prepare_record_snapshots(records)
        snapshots, skipped_count = Outbox.filter_uncovered_upsert_snapshots(snapshots)
        outboxes = Outbox.capture_prepared_snapshots(snapshots, operation="upsert")
        if outboxes:
            self.env["ab_odoo_sync_service"].sudo().queue_historical_upload_batch(
                outboxes
            )

        last_record = records[-1]
        processed_count = len(records)
        queued_count = len(outboxes)
        self.with_context(skip_ab_odoo_sync_upload_source_guard=True).sudo().write(
            {
                "historical_upload_cursor_write_date": last_record.write_date,
                "historical_upload_cursor_id": last_record.id,
                "historical_upload_processed_count": (
                    self.historical_upload_processed_count + processed_count
                ),
                "historical_upload_queued_count": (
                    self.historical_upload_queued_count + queued_count
                ),
                "historical_upload_skipped_count": (
                    self.historical_upload_skipped_count + skipped_count
                ),
                "historical_upload_last_error": False,
            }
        )
        if processed_count < batch_size:
            self.with_context(skip_ab_odoo_sync_upload_source_guard=True).sudo().write(
                {
                    "historical_upload_state": "done",
                    "historical_upload_completed_at": fields.Datetime.now(),
                }
            )
            status = "done"
        else:
            self._schedule_historical_upload_batch()
            status = "running"
        return {
            "status": status,
            "processed": processed_count,
            "queued": queued_count,
            "skipped": skipped_count,
        }

    def job_queue_historical_upload_batch(self):
        results = []
        for source in self.sudo().exists():
            try:
                results.append(source._process_historical_upload_batch())
            except Exception as ex:
                source.with_context(
                    skip_ab_odoo_sync_upload_source_guard=True
                ).sudo().write(
                    {
                        "historical_upload_state": "failed",
                        "historical_upload_last_error": str(ex),
                    }
                )
                _logger.exception(
                    "AB Odoo Sync historical upload backfill failed for %s",
                    source.model_name,
                )
                raise
        _logger.info("AB Odoo Sync historical upload batch result: %s", results)
        return results

    def action_queue_historical_upload(self):
        self._check_historical_upload_admin()
        self._validate_historical_upload_queue()
        queued_count = 0
        skipped_count = 0
        now = fields.Datetime.now()

        for source in self:
            if source.historical_upload_state in _HISTORICAL_RUNNING_STATES:
                skipped_count += 1
                continue
            if source.historical_upload_state == "done":
                skipped_count += 1
                continue

            if (
                source.historical_upload_state == "failed"
                and source.historical_upload_frozen_until
            ):
                vals = {
                    "historical_upload_state": "queued",
                    "historical_upload_last_error": False,
                    "historical_upload_completed_at": False,
                }
            else:
                vals = self._historical_upload_reset_values()
                vals.update(
                    {
                        "historical_upload_state": "queued",
                        "historical_upload_frozen_until": now,
                    }
                )

            source.with_context(skip_ab_odoo_sync_upload_source_guard=True).sudo().write(
                vals
            )
            source._schedule_historical_upload_batch()
            queued_count += 1

        return self._notification(
            _("Historical Branch Upload"),
            _(
                "Queued historical upload for %(queued)s source(s); "
                "%(skipped)s source(s) were already queued, running, or done."
            )
            % {"queued": queued_count, "skipped": skipped_count},
            "success" if queued_count else "warning",
        )

    def action_cancel_historical_upload(self):
        self._check_historical_upload_admin()
        cancellable_sources = self.filtered(
            lambda source: source.historical_upload_state in _HISTORICAL_RUNNING_STATES
        )
        cancellable_sources.with_context(
            skip_ab_odoo_sync_upload_source_guard=True
        ).sudo().write(
            {
                "historical_upload_state": "cancelled",
                "historical_upload_completed_at": False,
            }
        )
        return self._notification(
            _("Historical Branch Upload"),
            _("Cancelled historical upload for %(count)s source(s).")
            % {"count": len(cancellable_sources)},
            "success" if cancellable_sources else "warning",
        )

    @api.model
    def _is_loadable_model(self, model_name):
        if not model_name or model_name not in self.env:
            return False
        if model_name.startswith("ab_odoo_sync"):
            return False
        if self.env["ab_odoo_sync_rules"].sudo().is_upload_source_forbidden(model_name):
            return False
        try:
            model = self.env[model_name]
        except KeyError:
            return False
        if getattr(model, "_abstract", False) or getattr(model, "_transient", False):
            return False
        return bool(getattr(model, "_auto", True))

    def action_load_installed_models(self):
        existing = set(
            self.with_context(active_test=False).sudo().search([]).mapped("model_name")
        )
        vals_list = []
        for model_record in self.env["ir.model"].sudo().search([], order="model"):
            model_name = model_record.model
            if model_name in existing or not self._is_loadable_model(model_name):
                continue
            vals_list.append(
                {
                    "model_name": model_name,
                    "active": False,
                }
            )
            existing.add(model_name)
        created = len(self.sudo().create(vals_list)) if vals_list else 0
        return self._notification(
            _("Branch Upload Sources"),
            _("Loaded %(count)s installed model(s) as inactive upload sources.")
            % {"count": created},
            "success" if created else "warning",
        )

    @api.model
    def ensure_upload_sources(self, source_specs):
        existing = {
            source.model_name: source
            for source in self.with_context(active_test=False).sudo().search([])
        }
        vals_list = []
        for spec in source_specs or []:
            model_name = (spec.get("model_name") or "").strip()
            if not model_name or model_name in existing:
                continue
            if self.env["ab_odoo_sync_rules"].sudo().is_upload_source_forbidden(model_name):
                raise ValueError(
                    _("Source model %(model)s is protected by sync-rules.md and cannot be a branch upload source.")
                    % {"model": model_name}
                )
            vals = {
                "model_name": model_name,
                "active": bool(spec.get("active", False)),
            }
            if spec.get("aggregate_parent_field"):
                vals["aggregate_parent_field"] = spec["aggregate_parent_field"]
            if spec.get("historical_upload_months"):
                vals["historical_upload_months"] = spec["historical_upload_months"]
            if spec.get("historical_upload_from"):
                vals["historical_upload_from"] = spec["historical_upload_from"]
            vals_list.append(vals)
        if vals_list:
            self.sudo().create(vals_list)
        return True

    @api.model
    def _notification(self, title, message, notification_type):
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": title,
                "message": message,
                "type": notification_type,
                "sticky": False,
                "next": {
                    "type": "ir.actions.client",
                    "tag": "reload",
                },
            },
        }

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self.env.registry.clear_cache("stable")
        return records

    def write(self, vals):
        if not self.env.context.get("skip_ab_odoo_sync_upload_source_guard"):
            blocked_fields = {
                "model_name",
                "active",
                "historical_upload_months",
                "historical_upload_from",
            }
            if blocked_fields & set(vals):
                running_sources = self.filtered(
                    lambda source: source.historical_upload_state
                    in _HISTORICAL_RUNNING_STATES
                )
                if running_sources:
                    raise UserError(
                        _(
                            "Cannot change Source Model, Active, Historical Upload Past Months, or Historical Upload From while a historical upload is queued or running."
                        )
                    )

        state_by_id = {record.id: record.historical_upload_state for record in self}
        cutoff_by_id = {record.id: record.historical_upload_from for record in self}
        result = super().write(vals)
        self.env.registry.clear_cache("stable")

        if (
            "historical_upload_from" in vals
            and not self.env.context.get("skip_ab_odoo_sync_upload_source_guard")
        ):
            reset_sources = self.filtered(
                lambda source: state_by_id.get(source.id)
                in _HISTORICAL_TERMINAL_STATES
                and cutoff_by_id.get(source.id) != source.historical_upload_from
            )
            if reset_sources:
                reset_sources.with_context(
                    skip_ab_odoo_sync_upload_source_guard=True
                ).sudo().write(self._historical_upload_reset_values())
        return result

    def unlink(self):
        result = super().unlink()
        self.env.registry.clear_cache("stable")
        return result
