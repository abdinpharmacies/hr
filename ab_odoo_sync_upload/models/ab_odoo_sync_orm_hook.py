import logging
from collections import defaultdict, deque

from odoo import api, models
from odoo.models import BaseModel

_logger = logging.getLogger(__name__)

_ORIGINAL_CREATE = None
_ORIGINAL_WRITE = None
_ORIGINAL_UNLINK = None
_PATCHED = False


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
    global _ORIGINAL_CREATE, _ORIGINAL_WRITE, _ORIGINAL_UNLINK, _PATCHED
    if _PATCHED:
        return

    _ORIGINAL_CREATE = BaseModel.create
    _ORIGINAL_WRITE = BaseModel.write
    _ORIGINAL_UNLINK = BaseModel.unlink

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

    BaseModel.create = create_with_ab_sync_upload
    BaseModel.write = write_with_ab_sync_upload
    BaseModel.unlink = unlink_with_ab_sync_upload
    _PATCHED = True


class AbOdooSyncUploadOrmHook(models.AbstractModel):
    _name = "ab_odoo_sync_upload_orm_hook"
    _description = "AB Odoo Sync Upload ORM Hook"

    def _register_hook(self):
        result = super()._register_hook()
        _patch_base_model_methods()
        return result

