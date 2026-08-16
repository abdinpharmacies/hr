from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.translate import _


_TARGET_META_FIELDS = {
    "id",
    "db_serial",
    "rec_id",
    "payload_json",
    "source_revision",
    "event_uuid",
    "source_operation",
    "source_write_date",
    "synced_at",
    "create_uid",
    "create_date",
    "write_uid",
    "write_date",
    "display_name",
}


class AbOdooSyncApplyProfile(models.Model):
    _name = "ab_odoo_sync_apply_profile"
    _description = "AB Odoo Sync Apply Profile"
    _order = "sequence, name"

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    source_model_name = fields.Char(string="Source Model", required=True, index=True)
    target_model_name = fields.Char(string="Target Sync Model", required=True, index=True)
    mapping_ids = fields.One2many(
        "ab_odoo_sync_field_mapping",
        "profile_id",
        string="Field Mappings",
        copy=True,
    )
    auto_apply = fields.Boolean(
        string="Automatically Queue Apply",
        default=False,
        help="Keep disabled while inspecting raw payloads and selecting mappings.",
    )
    active = fields.Boolean(default=True, index=True)

    _uniq_source_model = models.Constraint(
        "UNIQUE(source_model_name)",
        "Only one apply profile is allowed for each source model.",
    )

    @api.constrains("source_model_name", "target_model_name")
    def _check_models(self):
        for profile in self:
            if profile.source_model_name not in self.env:
                raise ValidationError(
                    _("Source model %(model)s is not installed.")
                    % {"model": profile.source_model_name}
                )
            if profile.target_model_name not in self.env:
                raise ValidationError(
                    _("Target sync model %(model)s is not installed.")
                    % {"model": profile.target_model_name}
                )
            target_model = self.env[profile.target_model_name]
            missing = {"db_serial", "rec_id", "payload_json"} - set(target_model._fields)
            if missing:
                raise ValidationError(
                    _("Target sync model %(model)s is missing required fields: %(fields)s")
                    % {
                        "model": profile.target_model_name,
                        "fields": ", ".join(sorted(missing)),
                    }
                )

    @api.model
    def get_for_source(self, source_model_name):
        return self.sudo().search(
            [
                ("source_model_name", "=", source_model_name),
                ("active", "=", True),
            ],
            limit=1,
        )

    @api.model
    def _mapping_type_for_fields(self, source_field, target_field):
        if target_field.type == "one2many":
            return "ignore"
        if target_field.type == "many2one":
            return "sync_many2one" if target_field.comodel_name.endswith("__sync") else "stable_many2one"
        if target_field.type == "many2many":
            return "sync_many2many" if target_field.comodel_name.endswith("__sync") else "stable_many2many"
        if source_field.type == target_field.type:
            return "direct"
        return "ignore"

    def action_load_matching_fields(self):
        Mapping = self.env["ab_odoo_sync_field_mapping"].sudo()
        created = 0
        for profile in self:
            profile._check_models()
            source_model = self.env[profile.source_model_name]
            target_model = self.env[profile.target_model_name]
            existing_pairs = {
                (mapping.source_field_name, mapping.target_field_name)
                for mapping in profile.mapping_ids
            }
            vals_list = []
            for field_name, target_field in sorted(target_model._fields.items()):
                if field_name in _TARGET_META_FIELDS or field_name not in source_model._fields:
                    continue
                pair = (field_name, field_name)
                if pair in existing_pairs:
                    continue
                source_field = source_model._fields[field_name]
                mapping_type = self._mapping_type_for_fields(source_field, target_field)
                vals_list.append(
                    {
                        "profile_id": profile.id,
                        "source_field_name": field_name,
                        "target_field_name": field_name,
                        "mapping_type": mapping_type,
                        "sync_enabled": False,
                    }
                )
            if vals_list:
                created += len(Mapping.create(vals_list))
                profile.invalidate_recordset(["mapping_ids"])

        return self._notification(
            _("Odoo Sync Mapping"),
            _("Loaded %(count)s matching field mapping(s). Enable only the fields that MAIN should apply.")
            % {"count": created},
            "success" if created else "warning",
        )

    def action_apply_pending(self):
        applied = 0
        failed = 0
        Upload = self.env["ab_odoo_sync_upload_record"].sudo()
        for profile in self.sorted("sequence"):
            records = Upload.search(
                [
                    ("model_name", "=", profile.source_model_name),
                    ("status", "in", ["pending", "failed"]),
                    ("active", "=", True),
                ],
                order="source_revision, id",
            )
            for record in records:
                if (
                    record.apply_profile_id != profile
                    or record.target_model_name != profile.target_model_name
                ):
                    record.write(
                        {
                            "apply_profile_id": profile.id,
                            "target_model_name": profile.target_model_name,
                        }
                    )
                record._apply_to_target()
                if record.status == "applied":
                    applied += 1
                elif record.status == "failed":
                    failed += 1
        return self._notification(
            _("Odoo Sync Mapping"),
            _("Applied %(applied)s upload record(s); %(failed)s failed.")
            % {"applied": applied, "failed": failed},
            "success" if not failed else "warning",
        )

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
            },
        }


class AbOdooSyncFieldMapping(models.Model):
    _name = "ab_odoo_sync_field_mapping"
    _description = "AB Odoo Sync Field Mapping"
    _order = "sequence, source_field_name"

    profile_id = fields.Many2one(
        "ab_odoo_sync_apply_profile",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(default=10)
    source_field_name = fields.Char(string="Source Field", required=True)
    target_field_name = fields.Char(string="Target Field", required=True)
    mapping_type = fields.Selection(
        selection=[
            ("direct", "Direct Value"),
            ("sync_many2one", "Sync Many2one by Source ID"),
            ("sync_many2many", "Sync Many2many by Source ID"),
            ("stable_many2one", "Stable-key Many2one"),
            ("stable_many2many", "Stable-key Many2many"),
            ("ignore", "Ignore"),
        ],
        required=True,
        default="direct",
    )
    relation_source_key = fields.Char(
        string="Relation Source Key",
        help="Scalar field included in the relation snapshot, such as eplus_serial or code.",
    )
    relation_target_key = fields.Char(
        string="Relation Target Key",
        help="Field searched on the MAIN relation model.",
    )
    required = fields.Boolean(
        help="Fail the whole apply operation when this relation or value cannot be resolved.",
    )
    sync_enabled = fields.Boolean(string="Sync Enabled", default=False, index=True)

    _uniq_profile_field_pair = models.Constraint(
        "UNIQUE(profile_id, source_field_name, target_field_name)",
        "Field mapping must be unique per profile.",
    )

    @api.constrains(
        "source_field_name",
        "target_field_name",
        "mapping_type",
        "relation_source_key",
        "relation_target_key",
    )
    def _check_mapping(self):
        stable_types = {"stable_many2one", "stable_many2many"}
        for mapping in self:
            source_model = self.env[mapping.profile_id.source_model_name]
            target_model = self.env[mapping.profile_id.target_model_name]
            if mapping.source_field_name not in source_model._fields:
                raise ValidationError(
                    _("Source field %(field)s does not exist on %(model)s.")
                    % {
                        "field": mapping.source_field_name,
                        "model": mapping.profile_id.source_model_name,
                    }
                )
            if mapping.target_field_name not in target_model._fields:
                raise ValidationError(
                    _("Target field %(field)s does not exist on %(model)s.")
                    % {
                        "field": mapping.target_field_name,
                        "model": mapping.profile_id.target_model_name,
                    }
                )
            if mapping.mapping_type in stable_types and (
                not mapping.relation_source_key or not mapping.relation_target_key
            ):
                raise ValidationError(
                    _("Stable-key mappings require both relation key fields.")
                )
