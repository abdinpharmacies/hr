import logging
from collections import defaultdict, deque

from odoo import api, models
from odoo.api import Environment
from odoo.models import BaseModel

_logger = logging.getLogger(__name__)

_ORIGINAL_CREATE = None
_ORIGINAL_WRITE = None
_ORIGINAL_WRITE_MULTI = None
_ORIGINAL_UNLINK = None
_ORIGINAL_ADD_TO_COMPUTE = None
_PATCHED = False
_COLLECTOR_KEY = "ab_odoo_sync_upload.pending_snapshots"
_LOG_ACCESS_FIELDS = {"create_uid", "create_date", "write_uid", "write_date"}


def _is_sync_model(model_name):
    return model_name.startswith("ab.odoo.sync.") or model_name.startswith(
        "ab_odoo_sync"
    )


def _should_capture_upload(model):
    if model.env.context.get("skip_ab_odoo_sync_upload"):
        return False
    if _is_sync_model(model._name):
        return False
    if model._name in {"ir.model.data", "ir.module.module"}:
        return False
    return (
        model.env["ab_odoo_sync_upload_source"]
        .sudo()
        .is_upload_source(model._name)
    )


def _is_real_record_id(record_id):
    return type(record_id) is int and record_id > 0


def _get_upload_collector_state(env):
    state = env.cr.precommit.data.get(_COLLECTOR_KEY)
    if state is None:
        state = {
            "scheduled": False,
            "emitting": False,
            "upsert_keys": {},
            "archive_snapshots": {},
            "archive_order": [],
        }
        env.cr.precommit.data[_COLLECTOR_KEY] = state
    if not state["scheduled"]:
        env.cr.precommit.add(lambda: _flush_upload_collector(env))
        state["scheduled"] = True
    return state


def _mark_upload_snapshots(records):
    if not records or records.env.context.get("skip_ab_odoo_sync_upload"):
        return
    state = _get_upload_collector_state(records.env)
    if state["emitting"]:
        return
    for record in records:
        if not _is_real_record_id(record.id):
            continue
        key = (record._name, record.id)
        if key not in state["archive_snapshots"]:
            state["upsert_keys"][key] = key


def _mark_prepared_archive_snapshots(env, snapshots):
    if not snapshots or env.context.get("skip_ab_odoo_sync_upload"):
        return
    state = _get_upload_collector_state(env)
    if state["emitting"]:
        return
    for snapshot in snapshots:
        key = (snapshot.get("model_name"), snapshot.get("rec_id"))
        model_name, record_id = key
        if not model_name or not _is_real_record_id(record_id):
            continue
        if key not in state["archive_snapshots"]:
            state["archive_order"].append(key)
        state["archive_snapshots"][key] = snapshot
        state["upsert_keys"].pop(key, None)


def _capture_upload_snapshot_now(record, operation):
    Outbox = record.env["ab_odoo_sync_outbox"].with_context(
        skip_ab_odoo_sync_upload=True,
    ).sudo()
    Outbox.capture_record(record, operation=operation)


def _capture_prepared_snapshot_now(env, snapshot, operation):
    Outbox = env["ab_odoo_sync_outbox"].with_context(
        skip_ab_odoo_sync_upload=True,
    ).sudo()
    Outbox.capture_prepared_snapshot(snapshot, operation=operation)


def _flush_upload_collector(env):
    state = env.cr.precommit.data.get(_COLLECTOR_KEY)
    if not state or state["emitting"]:
        return
    state["emitting"] = True
    try:
        archive_keys = set(state["archive_snapshots"])
        upsert_by_model = defaultdict(list)
        for model_name, record_id in state["upsert_keys"]:
            if (model_name, record_id) not in archive_keys:
                upsert_by_model[model_name].append(record_id)

        for model_name, record_ids in sorted(upsert_by_model.items()):
            if model_name not in env:
                continue
            records = (
                env[model_name]
                .with_context(active_test=False, skip_ab_odoo_sync_upload=True)
                .sudo()
                .browse(record_ids)
                .exists()
            )
            for record in records:
                _capture_upload_snapshot_now(record, "upsert")

        for key in state["archive_order"]:
            snapshot = state["archive_snapshots"].get(key)
            if snapshot:
                _capture_prepared_snapshot_now(env, snapshot, "archive")
    finally:
        state["emitting"] = False


def _emit_upload_snapshots(records, operation):
    if not records:
        return
    if operation != "upsert":
        for record in records:
            _capture_upload_snapshot_now(record, operation)
        return
    _mark_upload_snapshots(records)


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
    if operation != "archive":
        for snapshot in snapshots:
            _capture_prepared_snapshot_now(env, snapshot, operation)
        return
    _mark_prepared_archive_snapshots(env, snapshots)


def _get_upload_aggregate_parents(records):
    if not records:
        return False
    return (
        records.env["ab_odoo_sync_upload_source"]
        .sudo()
        .get_aggregate_parents(records)
    )


def _get_unlink_dependency_index(env):
    registry = env.registry
    cache_name = "_ab_odoo_sync_upload_unlink_dependency_index"
    dependency_index = getattr(registry, cache_name, None)
    if dependency_index is not None:
        return dependency_index

    dependencies = defaultdict(list)
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
                ondelete = "set null"
            dependencies[field.comodel_name].append(
                (model_name, field_name, ondelete)
            )

    dependency_index = {
        model_name: tuple(model_dependencies)
        for model_name, model_dependencies in dependencies.items()
    }
    setattr(registry, cache_name, dependency_index)
    return dependency_index


def _get_upload_capture_models(records):
    if records.env.context.get("skip_ab_odoo_sync_upload"):
        return set()

    excluded_models = {"ir.model.data", "ir.module.module"}
    configured_models = set(
        records.env["ab_odoo_sync_upload_source"]
        .sudo()
        .search([("active", "=", True)])
        .mapped("model_name")
    )
    return {
        model_name
        for model_name in configured_models
        if (
            model_name in records.env.registry.models
            and model_name not in excluded_models
            and not _is_sync_model(model_name)
        )
    }


def _is_meaningful_stored_write(model, vals_list):
    for vals in vals_list:
        for field_name in vals:
            if field_name in _LOG_ACCESS_FIELDS:
                continue
            field = model._fields.get(field_name)
            if field and field.store:
                return True
    return False


def _should_capture_low_level_write(records, vals_list):
    if not records or records.env.context.get("skip_ab_odoo_sync_upload"):
        return False
    if not _is_meaningful_stored_write(records, vals_list):
        return False
    return _should_capture_upload(records)


def _should_capture_computed_records(env, field, records):
    if not records or records.env.context.get("skip_ab_odoo_sync_upload"):
        return False
    if not field.store or not field.compute:
        return False
    if field.model_name not in env:
        return False
    return _should_capture_upload(env[field.model_name])


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
    dependency_index = _get_unlink_dependency_index(records.env)
    archive_records = {}
    cascade_edges = defaultdict(set)
    set_null_records = {}
    set_null_fields = defaultdict(set)
    expanded = set()
    pending = deque()

    root_records = records.exists()
    for record in root_records:
        archive_records[(record._name, record.id)] = record
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
        for child_model_name, field_name, ondelete in dependency_index.get(
            current._name,
            (),
        ):
            if ondelete not in {"cascade", "set null"}:
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
        if record_key in visited or record_key in visiting:
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
    global _ORIGINAL_CREATE, _ORIGINAL_WRITE, _ORIGINAL_WRITE_MULTI
    global _ORIGINAL_UNLINK, _ORIGINAL_ADD_TO_COMPUTE, _PATCHED
    if _PATCHED:
        return

    _ORIGINAL_CREATE = BaseModel.create
    _ORIGINAL_WRITE = BaseModel.write
    _ORIGINAL_WRITE_MULTI = BaseModel._write_multi
    _ORIGINAL_UNLINK = BaseModel.unlink
    _ORIGINAL_ADD_TO_COMPUTE = Environment.add_to_compute

    @api.model_create_multi
    def create_with_ab_sync_upload(self, vals_list):
        records = _ORIGINAL_CREATE(self, vals_list)
        try:
            if _should_capture_upload(self):
                _emit_upload_snapshots(records, "upsert")
                parents = _get_upload_aggregate_parents(records)
                if parents:
                    _emit_upload_snapshots(parents, "upsert")
        except Exception:
            _logger.exception(
                "AB Odoo Sync upload snapshot failed after create on %s",
                self._name,
            )
            raise
        return records

    def write_with_ab_sync_upload(self, vals):
        records = self
        try:
            capture_upload = bool(records) and _should_capture_upload(records)
        except Exception:
            capture_upload = False

        result = _ORIGINAL_WRITE(records, vals)
        if capture_upload:
            try:
                _emit_upload_snapshots(records, "upsert")
                parents = _get_upload_aggregate_parents(records)
                if parents:
                    _emit_upload_snapshots(parents, "upsert")
            except Exception:
                _logger.exception(
                    "AB Odoo Sync upload snapshot failed after write on %s",
                    records._name,
                )
                raise
        return result

    def write_multi_with_ab_sync_upload(self, vals_list):
        records = self
        try:
            capture_upload = _should_capture_low_level_write(records, vals_list)
        except Exception:
            capture_upload = False

        result = _ORIGINAL_WRITE_MULTI(records, vals_list)
        if capture_upload:
            try:
                _mark_upload_snapshots(records)
            except Exception:
                _logger.exception(
                    "AB Odoo Sync upload snapshot failed after low-level write on %s",
                    records._name,
                )
                raise
        return result

    def unlink_with_ab_sync_upload(self):
        records = self
        if not records:
            return _ORIGINAL_UNLINK(records)

        capture_models = _get_upload_capture_models(records)
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
        prepared_archives = []
        for record in archive_records:
            if record._name in capture_models:
                prepared_archives.extend(_prepare_upload_snapshots(record))

        upload_parents = (
            _get_upload_aggregate_parents(records)
            if records._name in capture_models
            else False
        )
        result = _ORIGINAL_UNLINK(records)

        try:
            for record, field_names in set_null_records:
                survivor = record.exists()
                if survivor and survivor._name in capture_models:
                    _emit_upload_snapshots(survivor, "upsert")
            _emit_prepared_upload_snapshots(
                records.env,
                prepared_archives,
                "archive",
            )
            if upload_parents:
                _emit_upload_snapshots(upload_parents.exists(), "upsert")
        except Exception:
            _logger.exception(
                "AB Odoo Sync upload snapshot failed after unlink on %s",
                records._name,
            )
            raise
        return result

    def add_to_compute_with_ab_sync_upload(self, field, records):
        result = _ORIGINAL_ADD_TO_COMPUTE(self, field, records)
        try:
            if _should_capture_computed_records(self, field, records):
                _mark_upload_snapshots(records)
        except Exception:
            _logger.exception(
                "AB Odoo Sync upload snapshot failed after scheduling recompute "
                "of %s.%s",
                field.model_name,
                field.name,
            )
            raise
        return result

    BaseModel.create = create_with_ab_sync_upload
    BaseModel.write = write_with_ab_sync_upload
    BaseModel._write_multi = write_multi_with_ab_sync_upload
    BaseModel.unlink = unlink_with_ab_sync_upload
    Environment.add_to_compute = add_to_compute_with_ab_sync_upload
    _PATCHED = True


class AbOdooSyncUploadOrmHook(models.AbstractModel):
    _name = "ab_odoo_sync_upload_orm_hook"
    _description = "AB Odoo Sync Upload ORM Hook"

    def _register_hook(self):
        result = super()._register_hook()
        _patch_base_model_methods()
        return result
