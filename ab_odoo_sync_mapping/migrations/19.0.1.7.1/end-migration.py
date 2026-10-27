"""Configure source audit fields and explicit ignores on deployed sales profiles."""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {"skip_sync_apply_feeders": True})
    Profile = env["ab_odoo_sync_apply_profile"]
    Mapping = env["ab_odoo_sync_field_mapping"]
    profiles = Profile.with_context(active_test=False).search([
        ("source_model_name", "in", ["ab_sales_header", "ab_sales_line", "ab_sales_return_header", "ab_sales_return_line"]),
        ("apply_mode", "=", "mirror_sync"),
    ])
    for profile in profiles:
        target = env[profile.target_model_name]
        for name in ("create_uid", "create_date", "write_uid", "write_date",
                     "activity_ids", "message_follower_ids", "message_ids", "push_message"):
            audit = name in {"create_uid", "create_date", "write_uid", "write_date"}
            if audit and not Profile._is_passive_audit_field(target._fields.get(name)):
                continue
            vals = {
                "profile_id": profile.id, "source_field_name": name,
                "target_field_name": name if audit else False,
                "mapping_type": ("sync_many2one" if name.endswith("_uid") else "direct") if audit else "ignore",
                "sync_enabled": True, "required": False,
                "relation_source_key": False, "relation_target_key": False,
                "auto_generated": False,
            }
            # One intended behavior per source field; keep any unrelated mappings.
            existing = profile.mapping_ids.filtered(
                lambda mapping: mapping.source_field_name == name and (not audit or mapping.target_field_name == name)
            )
            if existing:
                existing.write({key: value for key, value in vals.items() if key != "profile_id"})
            else:
                Mapping.create(vals)
