import base64
import datetime
import logging

from odoo import api, models
from odoo.models import BaseModel

_logger = logging.getLogger(__name__)

_ORIGINAL_CREATE = None
_ORIGINAL_WRITE = None
_ORIGINAL_UNLINK = None
_PATCHED = False


def _to_jsonable(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    if isinstance(value, bytes):
        return base64.b64encode(value).decode("ascii")
    if isinstance(value, dict):
        return {k: _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_jsonable(v) for v in value]
    if hasattr(value, "ids"):
        return list(value.ids)
    return str(value)


def _should_capture(model):
    if model.env.context.get("skip_ab_odoo_sync_event"):
        return False
    if model._name.startswith("ab.odoo.sync.") or model._name.startswith("ab_odoo_sync"):
        return False
    if model._name in {
        "ir.model.data",
        "ir.module.module",
    }:
        return False

    service = model.env["ab_odoo_sync_service"].sudo()
    if service.get_server_role() != "main":
        return False

    return model.env["ab_odoo_sync_config"].sudo().is_model_tracked(model._name)


def _should_capture_upload(model):
    if model.env.context.get("skip_ab_odoo_sync_upload"):
        return False
    if model._name.startswith("ab.odoo.sync.") or model._name.startswith("ab_odoo_sync"):
        return False
    if model._name in {
        "ir.model.data",
        "ir.module.module",
    }:
        return False

    service = model.env["ab_odoo_sync_service"].sudo()
    if service.get_server_role() != "branch":
        return False

    return model.env["ab_odoo_sync_upload_source"].sudo().is_upload_source(model._name)


def _emit_events(model, operation, rec_vals_pairs):
    if not rec_vals_pairs:
        return

    vals_list = []
    for rec, vals in rec_vals_pairs:
        payload = _to_jsonable(vals or {})
        changed_fields = sorted((vals or {}).keys())
        vals_list.append(
            {
                "model_name": rec._name,
                "record_id": rec.id,
                "operation": operation,
                "payload_json": payload,
                "changed_fields_json": changed_fields,
                "source_server": "main",
            }
        )

    model.env["ab_odoo_sync_event"].with_context(skip_ab_odoo_sync_event=True).sudo().create(vals_list)


def _emit_upload_snapshots(records, operation):
    if not records:
        return
    Outbox = records.env["ab_odoo_sync_outbox"].with_context(
        skip_ab_odoo_sync_upload=True,
    ).sudo()
    for record in records:
        Outbox.capture_record(record, operation=operation)


def _get_upload_aggregate_parents(records):
    if not records:
        return False
    return records.env["ab_odoo_sync_upload_source"].sudo().get_aggregate_parents(records)


def _patch_base_model_methods():
    global _ORIGINAL_CREATE, _ORIGINAL_WRITE, _ORIGINAL_UNLINK, _PATCHED
    if _PATCHED:
        return

    _ORIGINAL_CREATE = BaseModel.create
    _ORIGINAL_WRITE = BaseModel.write
    _ORIGINAL_UNLINK = BaseModel.unlink

    @api.model_create_multi
    def create_with_ab_sync(self, vals_list):
        records = _ORIGINAL_CREATE(self, vals_list)
        try:
            if _should_capture(self):
                pairs = []
                records_list = list(records)
                for idx, rec in enumerate(records_list):
                    vals = vals_list[idx] if idx < len(vals_list) else {}
                    pairs.append((rec, vals))
                _emit_events(self, "create", pairs)
        except Exception:
            _logger.exception("ab_odoo_sync create event logging failed for model %s", self._name)

        try:
            if _should_capture_upload(self):
                _emit_upload_snapshots(records, "upsert")
                parents = _get_upload_aggregate_parents(records)
                if parents:
                    _emit_upload_snapshots(parents, "upsert")
        except Exception:
            _logger.exception("ab_odoo_sync branch create snapshot failed for model %s", self._name)
            raise
        return records

    def write_with_ab_sync(self, vals):
        capture = False
        capture_upload = False
        records = self
        try:
            capture = bool(records) and _should_capture(records)
        except Exception:
            capture = False
        try:
            capture_upload = bool(records) and _should_capture_upload(records)
        except Exception:
            capture_upload = False

        res = _ORIGINAL_WRITE(records, vals)

        try:
            if capture:
                _emit_events(records, "write", [(rec, vals) for rec in records])
        except Exception:
            _logger.exception("ab_odoo_sync write event logging failed for model %s", records._name)

        if capture_upload:
            try:
                _emit_upload_snapshots(records, "upsert")
                parents = _get_upload_aggregate_parents(records)
                if parents:
                    _emit_upload_snapshots(parents, "upsert")
            except Exception:
                _logger.exception("ab_odoo_sync branch write snapshot failed for model %s", records._name)
                raise
        return res

    def unlink_with_ab_sync(self):
        records = self
        capture = False
        capture_upload = False
        upload_parents = False
        try:
            capture = bool(records) and _should_capture(records)
            if capture:
                _emit_events(records, "unlink", [(rec, {"id": rec.id}) for rec in records])
        except Exception:
            _logger.exception("ab_odoo_sync unlink pre-log failed for model %s", records._name)

        try:
            capture_upload = bool(records) and _should_capture_upload(records)
        except Exception:
            capture_upload = False
        if capture_upload:
            try:
                upload_parents = _get_upload_aggregate_parents(records)
                _emit_upload_snapshots(records, "archive")
            except Exception:
                _logger.exception("ab_odoo_sync branch archive snapshot failed for model %s", records._name)
                raise

        result = _ORIGINAL_UNLINK(records)
        if upload_parents:
            try:
                _emit_upload_snapshots(upload_parents.exists(), "upsert")
            except Exception:
                _logger.exception("ab_odoo_sync aggregate parent snapshot failed after unlink")
                raise
        return result

    BaseModel.create = create_with_ab_sync
    BaseModel.write = write_with_ab_sync
    BaseModel.unlink = unlink_with_ab_sync
    _PATCHED = True


class AbOdooSyncOrmHook(models.AbstractModel):
    _name = "ab_odoo_sync_orm_hook"
    _description = "AB Odoo Sync ORM Hook"

    def _register_hook(self):
        res = super()._register_hook()
        _patch_base_model_methods()
        return res
