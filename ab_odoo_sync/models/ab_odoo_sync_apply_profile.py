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
    apply_mode = fields.Selection(
        selection=[
            ("raw_only", "Raw Only"),
            ("mirror_sync", "Mirror Sync Model"),
            ("business_model", "Business Model"),
            ("ignore", "Ignore"),
        ],
        string="Apply Mode",
        default="mirror_sync",
        required=True,
        index=True,
        help="Controls how MAIN handles accepted branch uploads for this source model.",
    )
    target_model_name = fields.Char(string="Target Model", index=True)
    allow_placeholder_creation = fields.Boolean(
        string="Allow Placeholder Creation",
        default=True,
        help="Create missing target records with the source ID when source-ID relations arrive out of order.",
    )
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

    @api.model
    def mirror_target_from_source(self, source_model_name):
        source_model_name = (source_model_name or "").strip()
        if not source_model_name:
            return False
        return "%s__sync" % source_model_name.replace(".", "_")

    @api.model
    def _default_target_model_name(self, source_model_name, apply_mode):
        if apply_mode == "mirror_sync":
            return self.mirror_target_from_source(source_model_name)
        if apply_mode == "business_model":
            return (source_model_name or "").strip() or False
        return False

    @api.onchange("source_model_name", "apply_mode")
    def _onchange_default_target_model_name(self):
        for profile in self:
            profile.target_model_name = profile._default_target_model_name(
                profile.source_model_name,
                profile.apply_mode,
            )

    @api.constrains("source_model_name", "target_model_name", "apply_mode")
    def _check_models(self):
        for profile in self:
            if profile.apply_mode in {"raw_only", "ignore"}:
                continue
            if not profile.target_model_name:
                raise ValidationError(_("Target model is required for this apply mode."))
            if profile.target_model_name not in self.env:
                raise ValidationError(
                    _("Target model %(model)s is not installed.")
                    % {"model": profile.target_model_name}
                )
            target_model = self.env[profile.target_model_name]
            if profile.apply_mode == "mirror_sync":
                missing = {"db_serial", "rec_id", "payload_json"} - set(target_model._fields)
                if missing:
                    raise ValidationError(
                        _("Target sync model %(model)s is missing required fields: %(fields)s")
                        % {
                            "model": profile.target_model_name,
                            "fields": ", ".join(sorted(missing)),
                        }
                    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            apply_mode = vals.get("apply_mode") or "mirror_sync"
            if not vals.get("target_model_name"):
                vals["target_model_name"] = self._default_target_model_name(
                    vals.get("source_model_name"),
                    apply_mode,
                )
        return super().create(vals_list)

    def write(self, vals):
        if "target_model_name" in vals:
            return super().write(vals)

        for profile in self:
            source_model_name = vals.get("source_model_name", profile.source_model_name)
            apply_mode = vals.get("apply_mode", profile.apply_mode)
            write_vals = dict(vals)
            if not profile.target_model_name or vals.get("source_model_name") or vals.get("apply_mode"):
                write_vals["target_model_name"] = profile._default_target_model_name(
                    source_model_name,
                    apply_mode,
                )
            super(AbOdooSyncApplyProfile, profile).write(write_vals)
        return True

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
    def _mapping_type_for_fields(self, source_field, target_field, apply_mode="mirror_sync"):
        if target_field.type == "one2many":
            return "ignore"
        if target_field.type == "many2one":
            if target_field.comodel_name.endswith("__sync") or apply_mode == "business_model":
                return "sync_many2one"
            return "stable_many2one"
        if target_field.type == "many2many":
            if target_field.comodel_name.endswith("__sync") or apply_mode == "business_model":
                return "sync_many2many"
            return "stable_many2many"
        source_type = source_field.type if source_field else False
        if source_type == target_field.type:
            return "direct"
        return "ignore"

    def _source_field_info(self):
        self.ensure_one()
        if self.source_model_name in self.env:
            return {
                field_name: field
                for field_name, field in self.env[self.source_model_name]._fields.items()
            }
        upload = self.env["ab_odoo_sync_upload_record"].sudo().search(
            [
                ("model_name", "=", self.source_model_name),
                ("payload_json", "!=", False),
            ],
            order="received_at desc, id desc",
            limit=1,
        )
        payload = upload.payload_json or {}
        field_types = payload.get("field_types") or {}
        fields_payload = payload.get("fields") or {}
        return {
            field_name: type(
                "PayloadField",
                (),
                {"type": field_types.get(field_name)},
            )()
            for field_name in fields_payload
        }

    def action_load_matching_fields(self):
        Mapping = self.env["ab_odoo_sync_field_mapping"].sudo()
        created = 0
        for profile in self:
            profile._check_models()
            if profile.apply_mode not in {"mirror_sync", "business_model"}:
                continue
            if profile.target_model_name not in self.env:
                raise ValidationError(
                    _("Install or upgrade target model %(model)s before loading field mappings.")
                    % {"model": profile.target_model_name}
                )
            source_fields = profile._source_field_info()
            target_model = self.env[profile.target_model_name]
            existing_pairs = {
                (mapping.source_field_name, mapping.target_field_name)
                for mapping in profile.mapping_ids
            }
            vals_list = []
            for field_name, target_field in sorted(target_model._fields.items()):
                if field_name in _TARGET_META_FIELDS or field_name not in source_fields:
                    continue
                pair = (field_name, field_name)
                if pair in existing_pairs:
                    continue
                source_field = source_fields[field_name]
                mapping_type = self._mapping_type_for_fields(
                    source_field,
                    target_field,
                    profile.apply_mode,
                )
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
                    ("status", "in", ["pending_mapping", "raw_only", "pending", "failed"]),
                    ("active", "=", True),
                ],
                order="source_revision, id",
            )
            for record in records:
                record._set_profile_handling(profile)
                if record.status in {"raw_only", "not_sync"}:
                    continue
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
                "next": {
                    "type": "ir.actions.client",
                    "tag": "reload",
                },
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

    @api.model
    def ensure_mappings(self, mapping_specs):
        Profile = self.env["ab_odoo_sync_apply_profile"].sudo()
        for spec in mapping_specs or []:
            profile = Profile.search(
                [
                    ("source_model_name", "=", spec.get("profile_source_model_name")),
                ],
                limit=1,
            )
            if not profile:
                continue
            source_field_name = spec.get("source_field_name")
            target_field_name = spec.get("target_field_name") or source_field_name
            if not source_field_name or not target_field_name:
                continue
            vals = {
                "profile_id": profile.id,
                "sequence": int(spec.get("sequence", 10)),
                "source_field_name": source_field_name,
                "target_field_name": target_field_name,
                "mapping_type": spec.get("mapping_type") or "direct",
                "relation_source_key": spec.get("relation_source_key") or False,
                "relation_target_key": spec.get("relation_target_key") or False,
                "required": bool(spec.get("required", False)),
                "sync_enabled": bool(spec.get("sync_enabled", True)),
            }
            mapping = self.sudo().search(
                [
                    ("profile_id", "=", profile.id),
                    ("source_field_name", "=", source_field_name),
                    ("target_field_name", "=", target_field_name),
                ],
                limit=1,
            )
            if mapping:
                mapping.write(vals)
            else:
                self.sudo().create(vals)
        return True

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
            profile = mapping.profile_id
            if profile.apply_mode not in {"mirror_sync", "business_model"}:
                continue
            source_model = self.env[profile.source_model_name] if profile.source_model_name in self.env else False
            target_model = self.env[profile.target_model_name]
            if source_model and mapping.source_field_name not in source_model._fields:
                raise ValidationError(
                    _("Source field %(field)s does not exist on %(model)s.")
                    % {
                        "field": mapping.source_field_name,
                        "model": profile.source_model_name,
                    }
                )
            if mapping.target_field_name not in target_model._fields:
                raise ValidationError(
                    _("Target field %(field)s does not exist on %(model)s.")
                    % {
                        "field": mapping.target_field_name,
                        "model": profile.target_model_name,
                    }
                )
            if mapping.mapping_type in stable_types and (
                not mapping.relation_source_key or not mapping.relation_target_key
            ):
                raise ValidationError(
                    _("Stable-key mappings require both relation key fields.")
                )
