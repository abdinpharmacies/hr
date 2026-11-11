"""Configure AB Odoo Sync on branch or report databases.

Run with Odoo shell, for example:

SYNC_ROLE=branch \
SYNC_REPORT_URL=http://report-server:4090 \
SYNC_REPORT_DATABASE=abdin_report \
SYNC_API_KEY=change-me \
SYNC_SOURCE_MODELS=ab_sales_header,ab_sales_line \
/opt/odoo19/venv19/bin/python /opt/odoo19/server/odoo-bin shell \
    -c /opt/odoo19/odoo19.conf -d branch_db < ab_odoo_sync/scripts/configure_sync.py
"""

import json
import os

from odoo.tools import config


def _log(message):
    print("[ab_odoo_sync_config] %s" % message)


def _fail(message):
    raise RuntimeError(message)


def _env(name, default=""):
    return (os.environ.get(name, default) or "").strip()


def _env_bool(name, default=False):
    raw = _env(name)
    if not raw:
        return default
    return raw.lower() in {"1", "true", "yes", "y", "on"}


def _env_int(name, default=False):
    raw = _env(name)
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as ex:
        raise RuntimeError("%s must be an integer." % name) from ex
    if value <= 0:
        raise RuntimeError("%s must be a positive integer." % name)
    return value


def _env_json(name, default):
    raw = _env(name)
    if not raw:
        return default
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as ex:
        raise RuntimeError("%s must be valid JSON." % name) from ex
    return value


def _env_csv(name):
    raw = _env(name)
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def _require_model(model_name):
    if model_name not in env:
        _fail("Model %s is not installed in database %s." % (model_name, env.cr.dbname))
    return env[model_name].sudo()


def _set_param(key, value):
    if value in (False, None, ""):
        return
    if DRY_RUN:
        _log("DRY-RUN set ir.config_parameter %s=%s" % (key, value))
        return
    env["ir.config_parameter"].sudo().set_param(key, value)
    _log("Set ir.config_parameter %s" % key)


def _activate_cron(xmlid, active=True):
    cron = env.ref(xmlid, raise_if_not_found=False)
    if not cron:
        _log("Cron %s is not installed; skipped." % xmlid)
        return
    if DRY_RUN:
        _log("DRY-RUN set cron %s active=%s" % (xmlid, active))
        return
    cron.sudo().write({"active": bool(active)})
    _log("Set cron %s active=%s" % (xmlid, active))


def _upsert(model, domain, vals, label):
    record = model.search(domain, limit=1)
    if DRY_RUN:
        action = "update" if record else "create"
        _log("DRY-RUN %s %s: %s" % (action, label, vals))
        return record
    if record:
        record.write(vals)
        _log("Updated %s" % label)
        return record
    record = model.create(vals)
    _log("Created %s" % label)
    return record


def _source_specs_from_env():
    specs = _env_json("SYNC_SOURCE_SPECS_JSON", [])
    if specs:
        if not isinstance(specs, list):
            _fail("SYNC_SOURCE_SPECS_JSON must be a JSON list.")
        return specs
    return [{"model_name": model_name, "active": True} for model_name in _env_csv("SYNC_SOURCE_MODELS")]


def _profile_specs_from_env():
    specs = _env_json("SYNC_PROFILE_SPECS_JSON", [])
    if specs:
        if not isinstance(specs, list):
            _fail("SYNC_PROFILE_SPECS_JSON must be a JSON list.")
        return specs

    apply_mode = _env("SYNC_APPLY_MODE", "mirror_sync")
    auto_apply = _env_bool("SYNC_AUTO_APPLY", True)
    return [
        {
            "name": model_name,
            "source_model_name": model_name,
            "target_model_name": model_name,
            "apply_mode": apply_mode,
            "auto_apply": auto_apply,
            "active": True,
        }
        for model_name in _env_csv("SYNC_PROFILE_MODELS")
    ]


def _branch_specs_from_env():
    specs = _env_json("SYNC_BRANCHES_JSON", [])
    if specs:
        if not isinstance(specs, list):
            _fail("SYNC_BRANCHES_JSON must be a JSON list.")
        return specs

    db_serial = _env_int("SYNC_BRANCH_DB_SERIAL")
    if not db_serial:
        db_serial = _env_int("SYNC_DB_SERIAL")
    if not db_serial:
        return []
    name = _env("SYNC_BRANCH_NAME", "Branch %s" % db_serial)
    return [{"name": name, "db_serial": db_serial, "active": True}]


def _configure_branch():
    _require_model("ab_odoo_sync_upload_source")
    _set_param("ab_odoo_sync.report_url", _env("SYNC_REPORT_URL"))
    _set_param("ab_odoo_sync.report_database", _env("SYNC_REPORT_DATABASE"))
    _set_param("ab_odoo_sync.api_key", _env("SYNC_API_KEY"))
    _set_param("ab_odoo_sync.batch_size", _env("SYNC_BATCH_SIZE"))

    expected_db_serial = _env_int("SYNC_DB_SERIAL")
    configured_db_serial = config.get("db_serial", False)
    if expected_db_serial and str(configured_db_serial or "") != str(expected_db_serial):
        _fail(
            "Branch db_serial mismatch. odoo.conf has %s but SYNC_DB_SERIAL is %s. "
            "Set db_serial in odoo.conf; it is not stored in ir.config_parameter."
            % (configured_db_serial, expected_db_serial)
        )
    if not configured_db_serial:
        _log("Warning: db_serial is missing from odoo.conf. Branch upload will be skipped.")

    Source = _require_model("ab_odoo_sync_upload_source")
    for spec in _source_specs_from_env():
        model_name = (spec.get("model_name") or "").strip()
        if not model_name:
            continue
        vals = {
            "model_name": model_name,
            "active": bool(spec.get("active", True)),
        }
        if spec.get("aggregate_parent_field"):
            vals["aggregate_parent_field"] = spec["aggregate_parent_field"]
        _upsert(
            Source.with_context(active_test=False),
            [("model_name", "=", model_name)],
            vals,
            "upload source %s" % model_name,
        )

    if _env_bool("SYNC_ACTIVATE_CRONS", False):
        _activate_cron("ab_odoo_sync_upload.ir_cron_ab_odoo_sync_branch_upload", True)

    if _env_bool("SYNC_TEST_CONNECTION", False) and not DRY_RUN:
        result = env["ab_odoo_sync_service"].sudo().test_upload_connection()
        _log("Connection test result: %s" % result)


def _configure_report():
    Branch = _require_model("ab_odoo_sync_branch_registry")
    Profile = _require_model("ab_odoo_sync_apply_profile")
    Mapping = _require_model("ab_odoo_sync_field_mapping")

    _set_param("ab_odoo_sync.api_key", _env("SYNC_API_KEY"))

    for spec in _branch_specs_from_env():
        db_serial = int(spec.get("db_serial") or 0)
        if db_serial <= 0:
            _fail("Branch db_serial must be a positive integer.")
        vals = {
            "name": spec.get("name") or "Branch %s" % db_serial,
            "db_serial": db_serial,
            "active": bool(spec.get("active", True)),
        }
        _upsert(
            Branch.with_context(active_test=False),
            [("db_serial", "=", db_serial)],
            vals,
            "branch registry db_serial %s" % db_serial,
        )

    for spec in _profile_specs_from_env():
        source_model_name = (spec.get("source_model_name") or "").strip()
        if not source_model_name:
            continue
        vals = {
            "name": spec.get("name") or source_model_name,
            "sequence": int(spec.get("sequence", 10)),
            "source_model_name": source_model_name,
            "apply_mode": spec.get("apply_mode") or "mirror_sync",
            "target_model_name": spec.get("target_model_name") or source_model_name,
            "allow_placeholder_creation": bool(spec.get("allow_placeholder_creation", True)),
            "auto_apply": bool(spec.get("auto_apply", True)),
            "active": bool(spec.get("active", True)),
        }
        _upsert(
            Profile.with_context(active_test=False),
            [("source_model_name", "=", source_model_name)],
            vals,
            "apply profile %s" % source_model_name,
        )

    mapping_specs = _env_json("SYNC_MAPPING_SPECS_JSON", [])
    if mapping_specs:
        if not isinstance(mapping_specs, list):
            _fail("SYNC_MAPPING_SPECS_JSON must be a JSON list.")
        if DRY_RUN:
            _log("DRY-RUN ensure %s field mapping(s)" % len(mapping_specs))
        else:
            Mapping.ensure_mappings(mapping_specs)
            _log("Ensured %s field mapping(s)" % len(mapping_specs))

    if _env_bool("SYNC_LOAD_MATCHING_FIELDS", False):
        source_model_names = [
            spec.get("source_model_name")
            for spec in _profile_specs_from_env()
            if isinstance(spec, dict) and spec.get("source_model_name")
        ]
        profiles = Profile.search(
            [("source_model_name", "in", source_model_names)]
        )
        if DRY_RUN:
            _log("DRY-RUN load matching fields for %s profile(s)" % len(profiles))
        else:
            profiles.action_load_matching_fields()
            _log("Loaded disabled matching fields for %s profile(s)" % len(profiles))

    if _env_bool("SYNC_ACTIVATE_CRONS", False):
        _activate_cron("ab_odoo_sync_mapping.ir_cron_ab_odoo_sync_queue_upload_apply", True)


ROLE = _env("SYNC_ROLE").lower()
DRY_RUN = _env_bool("SYNC_DRY_RUN", False)

if ROLE not in {"branch", "report"}:
    _fail("Set SYNC_ROLE to branch or report.")

_log("Configuring %s database %s" % (ROLE, env.cr.dbname))
if ROLE == "branch":
    _configure_branch()
else:
    _configure_report()

if DRY_RUN:
    env.cr.rollback()
    _log("Dry-run finished; rolled back.")
else:
    env.cr.commit()
    _log("Configuration committed.")
