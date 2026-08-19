import base64
import datetime
import logging
from collections import defaultdict, deque

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


def _prepare_upload_snapshots(records):
    if not records:
        return []
    Outbox = records.env["ab_odoo_sync_outbox"].with_context(
        skip_ab_odoo_sync_upload=True,
    ).sudo()
    return [Outbox.prepare_record_snapshot(record) for record in records]


def _emit_prepared_upload_snapshots(env, snapshots, operation):
    if not snapshots:
        return
    Outbox = env["ab_odoo_sync_outbox"].with_context(
        skip_ab_odoo_sync_upload=True,
    ).sudo()
    for snapshot in snapshots:
        Outbox.capture_prepared_snapshot(snapshot, operation=operation)


def _get_upload_aggregate_parents(records):
    if not records:
        return False
    return records.env["ab_odoo_sync_upload_source"].sudo().get_aggregate_parents(records)


def _get_unlink_dependency_index(env):
    registry = env.registry
    cache_name = "_ab_odoo_sync_unlink_dependency_index"
    dependency_index = getattr(registry, cache_name, None)
    if dependency_index is not None:
        return dependency_index

    dependency_index = defaultdict(list)
    for model_name, model_class in sorted(registry.models.items()):
        if getattr(model_class, "_abstract", False) or not getattr(
            model_class,
            "_auto",
            True,
        ):
            continue
        for field_name, field in sorted(model_class._fields.items()):
            if (
                field.type != "many2one"
                or not field.store
                or not field.comodel_name
                or field.comodel_name not in registry.models
            ):
                continue
            ondelete = (field.ondelete or "set null").lower()
            if field.company_dependent and ondelete != "restrict":
                # Odoo stores company-dependent relations in JSONB and clears
                # references itself instead of applying a database cascade.
                ondelete = "set null"
            dependency_index[field.comodel_name].append(
                (model_name, field_name, ondelete)
            )

    dependency_index = {
        model_name: tuple(dependencies)
        for model_name, dependencies in dependency_index.items()
    }
    setattr(registry, cache_name, dependency_index)
    return dependency_index


def _get_unlink_capture_models(records):
    service = records.env["ab_odoo_sync_service"].sudo()
    role = service.get_server_role()
    main_models = set()
    upload_models = set()

    if role == "main" and not records.env.context.get("skip_ab_odoo_sync_event"):
        main_models = set(
            records.env["ab_odoo_sync_config"]
            .sudo()
            .search([("active", "=", True)])
            .mapped("model_name")
        )
    elif role == "branch" and not records.env.context.get("skip_ab_odoo_sync_upload"):
        upload_models = set(
            records.env["ab_odoo_sync_upload_source"]
            .sudo()
            .search([("active", "=", True)])
            .mapped("model_name")
        )

    excluded_models = {
        "ir.model.data",
        "ir.module.module",
    }

    def is_capturable(model_name):
        return (
            model_name in records.env.registry.models
            and model_name not in excluded_models
            and not model_name.startswith("ab.odoo.sync.")
            and not model_name.startswith("ab_odoo_sync")
        )

    return (
        {model_name for model_name in main_models if is_capturable(model_name)},
        {model_name for model_name in upload_models if is_capturable(model_name)},
    )


def _get_relevant_unlink_models(dependency_index, capture_models):
    relevant_models = set(capture_models)
    changed = True
    while changed:
        changed = False
        for parent_model_name, dependencies in dependency_index.items():
            if parent_model_name in relevant_models:
                continue
            for child_model_name, _field_name, ondelete in dependencies:
                if (
                    ondelete == "cascade"
                    and child_model_name in relevant_models
                ) or (
                    ondelete == "set null"
                    and child_model_name in capture_models
                ):
                    relevant_models.add(parent_model_name)
                    changed = True
                    break
    return relevant_models


def _build_unlink_plan(records, capture_models, relevant_models):
    """Return cascade archives and surviving set-null records for ``records``."""
    dependency_index = _get_unlink_dependency_index(records.env)
    archive_records = {}
    cascade_edges = defaultdict(set)
    set_null_records = {}
    set_null_fields = defaultdict(set)
    expanded = set()
    pending = deque()

    root_records = records.exists()
    for record in root_records:
        key = (record._name, record.id)
        archive_records[key] = record
    if root_records:
        pending.append(root_records)

    while pending:
        current = pending.popleft().exists()
        unexpanded_ids = [
            record.id
            for record in current
            if (record._name, record.id) not in expanded
        ]
        if not unexpanded_ids:
            continue

        current = current.browse(unexpanded_ids)
        expanded.update((current._name, record_id) for record_id in unexpanded_ids)
        dependencies = dependency_index.get(current._name, ())
        for child_model_name, field_name, ondelete in dependencies:
            if ondelete not in {"cascade", "set null"}:
                # Restrict/no-action dependencies are intentionally left to
                # the original unlink. No sync records are written unless it succeeds.
                continue
            if ondelete == "cascade" and child_model_name not in relevant_models:
                continue
            if ondelete == "set null" and child_model_name not in capture_models:
                continue

            children = (
                current.env[child_model_name]
                .with_context(active_test=False)
                .sudo()
                .search([(field_name, "in", unexpanded_ids)])
            )
            if not children:
                continue

            if ondelete == "cascade":
                for child in children:
                    child_key = (child._name, child.id)
                    parent = child[field_name]
                    if parent:
                        cascade_edges[(current._name, parent.id)].add(child_key)
                    archive_records.setdefault(child_key, child)
                pending.append(children)
                continue

            for child in children:
                child_key = (child._name, child.id)
                set_null_records.setdefault(child_key, child)
                set_null_fields[child_key].add(field_name)

    archive_order = []
    visited = set()
    visiting = set()

    def add_archive_record(record_key):
        if record_key in visited:
            return
        if record_key in visiting:
            return
        visiting.add(record_key)
        for child_key in sorted(cascade_edges.get(record_key, ())):
            add_archive_record(child_key)
        visiting.remove(record_key)
        visited.add(record_key)
        archive_order.append(archive_records[record_key])

    for root in root_records:
        add_archive_record((root._name, root.id))
    for record_key in sorted(archive_records):
        add_archive_record(record_key)

    surviving_set_null = [
        (set_null_records[record_key], tuple(sorted(field_names)))
        for record_key, field_names in sorted(set_null_fields.items())
        if record_key not in archive_records
    ]
    return archive_order, surviving_set_null


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
        if not records:
            return _ORIGINAL_UNLINK(records)

        main_capture_models, upload_capture_models = _get_unlink_capture_models(records)
        capture_models = main_capture_models | upload_capture_models
        dependency_index = _get_unlink_dependency_index(records.env)
        relevant_models = _get_relevant_unlink_models(
            dependency_index,
            capture_models,
        )
        if records._name not in relevant_models:
            return _ORIGINAL_UNLINK(records)

        archive_records, set_null_records = _build_unlink_plan(
            records,
            capture_models,
            relevant_models,
        )
        main_archive_records = []
        prepared_upload_archives = []
        upload_parents = False

        for record in archive_records:
            if record._name in main_capture_models:
                main_archive_records.append(record)
            if record._name in upload_capture_models:
                prepared_upload_archives.extend(_prepare_upload_snapshots(record))

        if records._name in upload_capture_models:
            try:
                upload_parents = _get_upload_aggregate_parents(records)
            except Exception:
                _logger.exception(
                    "ab_odoo_sync aggregate parent preparation failed before unlink for model %s",
                    records._name,
                )
                raise

        result = _ORIGINAL_UNLINK(records)

        try:
            main_set_null_pairs = []
            upload_set_null_records = []
            for record, field_names in set_null_records:
                survivor = record.exists()
                if not survivor:
                    continue
                vals = {field_name: False for field_name in field_names}
                if survivor._name in main_capture_models:
                    main_set_null_pairs.append((survivor, vals))
                if survivor._name in upload_capture_models:
                    upload_set_null_records.append(survivor)

            if main_set_null_pairs:
                _emit_events(records, "write", main_set_null_pairs)
            if upload_set_null_records:
                for survivor in upload_set_null_records:
                    _emit_upload_snapshots(survivor, "upsert")

            if main_archive_records:
                _emit_events(
                    records,
                    "unlink",
                    [(record, {"id": record.id}) for record in main_archive_records],
                )
            _emit_prepared_upload_snapshots(
                records.env,
                prepared_upload_archives,
                "archive",
            )
        except Exception:
            _logger.exception(
                "ab_odoo_sync unlink synchronization failed for model %s",
                records._name,
            )
            raise

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
