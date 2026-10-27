from odoo import api, models


class AbOdooSyncMappingToggleMixin(models.AbstractModel):
    _name = "ab_odoo_sync_mapping_toggle_mixin"
    _description = "Sync Mapping Toggle Behavior"

    def _infer_toggle_mapping_type(self, vals):
        Profile = self.env["ab_odoo_sync_apply_profile"]
        if self._name == "ab_odoo_sync_field_mapping":
            profile = Profile.browse(vals["profile_id"]) if "profile_id" in vals else self.profile_id
            target_model_name = profile.target_model_name
            payload = None
        else:
            Upload = self.env["ab_odoo_sync_upload_record"]
            upload = Upload.browse(vals["upload_record_id"]) if "upload_record_id" in vals else self.upload_record_id
            profile = upload.apply_profile_id
            target_model_name = upload.target_model_name
            payload = upload.payload_json
        if not profile or target_model_name not in self.env:
            return "ignore"
        source_name = vals.get("source_field_name", self.source_field_name)
        target_name = vals.get("target_field_name", self.target_field_name)
        source_fields = profile._source_field_info(payload=payload)
        source_field = source_fields.get(source_name)
        if not getattr(source_field, "type", False) and profile.source_model_name in self.env:
            source_field = self.env[profile.source_model_name]._fields.get(source_name)
        target_field = self.env[target_model_name]._fields.get(target_name)
        if not target_field or not Profile._is_writable_sync_target_field(target_field):
            return "ignore"
        if getattr(source_field, "type", False) != target_field.type:
            return "ignore"
        if target_field.type in {"many2one", "many2many"}:
            rules = self.env["ab_odoo_sync_rules"]
            source_key = vals.get("relation_source_key", self.relation_source_key)
            target_key = vals.get("relation_target_key", self.relation_target_key)
            relation = self.env[target_field.comodel_name]
            key_field = relation._fields.get(target_key)
            if (source_key and key_field and key_field.store
                    and key_field.type not in {"many2one", "many2many", "one2many", "json", "binary"}
                    and not rules.is_id_only_relation_model(getattr(source_field, "comodel_name", False))
                    and not rules.is_id_only_relation_model(target_field.comodel_name)
                    and target_field.comodel_name != rules.user_mirror_model()):
                return "stable_many2one" if target_field.type == "many2one" else "stable_many2many"
        mapping_type = Profile._mapping_type_for_fields(source_field, target_field, profile.apply_mode)
        return mapping_type if mapping_type in {"direct", "sync_many2one", "sync_many2many"} else "ignore"

    def _normalize_toggle_values(self, vals, creating=False):
        vals = dict(vals)
        defaults = self.default_get(["sync_enabled", "mapping_type"]) if creating else {}
        enabled = vals.get("sync_enabled", defaults.get("sync_enabled", False) if creating else self.sync_enabled)
        if not enabled:
            vals.update(mapping_type="ignore", required=False)
        elif "mapping_type" not in vals and (creating or not self.sync_enabled):
            vals["mapping_type"] = self._infer_toggle_mapping_type(vals)
            if vals["mapping_type"] == "ignore":
                vals["required"] = False
            elif not creating:
                vals.setdefault("required", False)
        return vals

    @api.onchange("sync_enabled")
    def _onchange_sync_enabled(self):
        for record in self:
            if not record.sync_enabled:
                record.mapping_type = "ignore"
                record.required = False
            elif record.mapping_type == "ignore":
                record.mapping_type = record._infer_toggle_mapping_type({})
                record.required = False

    @api.model_create_multi
    def create(self, vals_list):
        return super().create([self._normalize_toggle_values(vals, creating=True) for vals in vals_list])

    def write(self, vals):
        for record in self:
            super(AbOdooSyncMappingToggleMixin, record).write(record._normalize_toggle_values(vals))
        return True
