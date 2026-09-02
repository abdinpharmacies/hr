from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.translate import _


_APPLY_CAPABLE_MODES = {"mirror_sync", "business_model"}
_AUTO_FEEDER_PROFILE_FIELDS = {
    "active",
    "allow_placeholder_creation",
    "apply_mode",
    "auto_apply",
    "source_model_name",
    "target_model_name",
}
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
        help="Controls how the report server handles accepted branch uploads for this source model.",
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
        """Deprecated compatibility helper; mirror targets are same-name models."""
        source_model_name = (source_model_name or "").strip()
        return source_model_name or False

    @api.model
    def _default_target_model_name(self, source_model_name, apply_mode):
        if apply_mode in {"mirror_sync", "business_model"}:
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
            rules = self.env["ab_odoo_sync_rules"].sudo()
            if rules.is_upload_source_forbidden(profile.source_model_name):
                raise ValidationError(
                    _("Source model %(model)s is protected by sync-rules.md and cannot be uploaded from branches.")
                    % {"model": profile.source_model_name}
                )
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
                if profile.source_model_name != profile.target_model_name:
                    raise ValidationError(
                        _("Mirror Sync Model profiles must use the same source and target model.")
                    )
                if rules.is_never_mirror_model(profile.source_model_name):
                    raise ValidationError(
                        _("Source model %(model)s is report-owned and must use Business Model apply mode.")
                        % {"model": profile.source_model_name}
                    )
                missing = self._missing_mirror_sync_fields(target_model)
                if missing:
                    raise ValidationError(
                        _("Target sync model %(model)s is missing required fields: %(fields)s")
                        % {
                            "model": profile.target_model_name,
                            "fields": ", ".join(sorted(missing)),
                        }
                    )
                if not profile._target_has_unique_identity_constraint(target_model):
                    raise ValidationError(
                        _(
                            "Target sync model %(model)s must define a unique database constraint on db_serial and rec_id."
                        )
                        % {"model": profile.target_model_name}
                    )
                required_fields = sorted(
                    field_name
                    for field_name, field in target_model._fields.items()
                    if field.required
                )
                if required_fields:
                    raise ValidationError(
                        _(
                            "Target sync model %(model)s must not define required fields. "
                            "Use apply profile field mappings to mark required values instead: %(fields)s"
                        )
                        % {
                            "model": profile.target_model_name,
                            "fields": ", ".join(required_fields),
                        }
                    )
            source_model = self.env[profile.source_model_name] if profile.source_model_name in self.env else False
            user_target = rules.user_mirror_model()
            if source_model and profile.apply_mode == "mirror_sync":
                for field_name, source_field in source_model._fields.items():
                    if (
                        source_field.type == "many2one"
                        and source_field.store
                        and source_field.comodel_name == "res.users"
                        and field_name in target_model._fields
                    ):
                        target_field = target_model._fields[field_name]
                        if target_field.type != "many2one" or target_field.comodel_name != user_target:
                            raise ValidationError(
                                _(
                                    "Target field %(field)s on %(target)s must point to %(user_model)s because "
                                    "%(source)s points to res.users."
                                )
                                % {
                                    "field": field_name,
                                    "target": profile.target_model_name,
                                    "user_model": user_target,
                                    "source": "%s.%s" % (profile.source_model_name, field_name),
                                }
                            )

    @api.model
    def _missing_mirror_sync_fields(self, target_model):
        return {"db_serial", "rec_id", "payload_json"} - set(target_model._fields)

    @api.model
    def _has_mirror_sync_metadata(self, model_name):
        if not model_name or model_name not in self.env:
            return False
        target_model = self.env[model_name]
        return not self._missing_mirror_sync_fields(target_model) and self._target_has_unique_identity_constraint(
            target_model
        )

    @api.model
    def _target_has_unique_identity_constraint(self, target_model):
        self.env.cr.execute(
            """
            SELECT array_agg(att.attname ORDER BY keys.ordinality)
              FROM pg_constraint con
              JOIN pg_class cls ON cls.oid = con.conrelid
              JOIN pg_namespace nsp ON nsp.oid = cls.relnamespace
              JOIN unnest(con.conkey) WITH ORDINALITY AS keys(attnum, ordinality)
                ON true
              JOIN pg_attribute att
                ON att.attrelid = con.conrelid
               AND att.attnum = keys.attnum
             WHERE con.contype = 'u'
               AND cls.relname = %s
               AND nsp.nspname = current_schema()
             GROUP BY con.oid
            """,
            (target_model._table,),
        )
        return any(set(row[0] or []) == {"db_serial", "rec_id"} for row in self.env.cr.fetchall())

    def _queue_auto_upload_apply_feeders(self):
        service = self.env["ab_odoo_sync_service"].sudo()
        queued = 0
        for profile in self.sudo():
            queued += service.queue_upload_apply_feeder(profile)
        return queued

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            apply_mode = vals.get("apply_mode") or "mirror_sync"
            if not vals.get("target_model_name"):
                vals["target_model_name"] = self._default_target_model_name(
                    vals.get("source_model_name"),
                    apply_mode,
                )
        profiles = super().create(vals_list)
        profiles._queue_auto_upload_apply_feeders()
        return profiles

    def write(self, vals):
        should_queue = bool(_AUTO_FEEDER_PROFILE_FIELDS.intersection(vals))
        if "target_model_name" in vals:
            result = super().write(vals)
            if should_queue:
                self._queue_auto_upload_apply_feeders()
            return result

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
        if should_queue:
            self._queue_auto_upload_apply_feeders()
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
        rules = self.env["ab_odoo_sync_rules"].sudo()
        source_comodel = getattr(source_field, "comodel_name", False)
        if target_field.type == "many2one":
            if source_comodel == rules.user_source_model():
                if target_field.comodel_name == rules.user_mirror_model():
                    return "sync_many2one"
                return "ignore"
            if (
                apply_mode == "business_model"
                or target_field.comodel_name == rules.user_mirror_model()
                or target_field.comodel_name.endswith("__sync")
                or rules.is_id_only_relation_model(source_comodel)
                or self._has_mirror_sync_metadata(target_field.comodel_name)
            ):
                return "sync_many2one"
            return "ignore"
        if target_field.type == "many2many":
            if source_comodel == rules.user_source_model():
                if target_field.comodel_name == rules.user_mirror_model():
                    return "sync_many2many"
                return "ignore"
            if (
                apply_mode == "business_model"
                or target_field.comodel_name.endswith("__sync")
                or rules.is_id_only_relation_model(source_comodel)
                or self._has_mirror_sync_metadata(target_field.comodel_name)
            ):
                return "sync_many2many"
            return "ignore"
        source_type = source_field.type if source_field else False
        if source_type == target_field.type:
            return "direct"
        return "ignore"

    @api.model
    def _is_auto_sync_safe_field(self, source_field, target_field, mapping_type):
        if mapping_type not in {"direct", "sync_many2one", "sync_many2many"}:
            return False
        if not getattr(source_field, "store", False) or not target_field.store:
            return False
        return not (target_field.compute and not target_field.inverse)

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

    def _load_matching_fields(self, default_sync_enabled=False, stored_only=False):
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
                if stored_only and (
                    not getattr(source_field, "store", False) or not target_field.store
                ):
                    continue
                mapping_type = self._mapping_type_for_fields(
                    source_field,
                    target_field,
                    profile.apply_mode,
                )
                sync_enabled = default_sync_enabled and profile._is_auto_sync_safe_field(
                    source_field,
                    target_field,
                    mapping_type,
                )
                vals_list.append(
                    {
                        "profile_id": profile.id,
                        "source_field_name": field_name,
                        "target_field_name": field_name,
                        "mapping_type": mapping_type,
                        "sync_enabled": sync_enabled,
                    }
                )
            if vals_list:
                created += len(Mapping.create(vals_list))
                profile.invalidate_recordset(["mapping_ids"])

        return created

    def action_load_matching_fields(self):
        created = self._load_matching_fields(default_sync_enabled=False)
        return self._notification(
            _("Odoo Sync Mapping"),
            _(
                "Loaded %(count)s matching field mapping(s). Enable only the "
                "fields that the report server should apply."
            )
            % {"count": created},
            "success" if created else "warning",
        )

    def action_queue_pending_uploads(self):
        queued = 0
        service = self.env["ab_odoo_sync_service"].sudo()
        for profile in self.sorted("sequence"):
            queued += service.queue_upload_apply_feeder(profile, manual=True)
        return self._notification(
            _("Odoo Sync Mapping"),
            _("Queued pending upload feeder(s) for %(count)s profile(s).")
            % {"count": queued},
            "success" if queued else "warning",
        )

    def action_apply_pending(self):
        return self.action_queue_pending_uploads()

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
        help="Field searched on the report relation model.",
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

    def _queue_auto_upload_apply_feeders_for_profiles(self, profiles):
        profiles.filtered(
            lambda profile: (
                profile.active
                and profile.auto_apply
                and profile.apply_mode in _APPLY_CAPABLE_MODES
            )
        )._queue_auto_upload_apply_feeders()

    @api.model_create_multi
    def create(self, vals_list):
        mappings = super().create(vals_list)
        self._queue_auto_upload_apply_feeders_for_profiles(mappings.mapped("profile_id"))
        return mappings

    def write(self, vals):
        profiles = self.mapped("profile_id")
        result = super().write(vals)
        profiles |= self.mapped("profile_id")
        self._queue_auto_upload_apply_feeders_for_profiles(profiles)
        return result

    def unlink(self):
        profiles = self.mapped("profile_id")
        result = super().unlink()
        self._queue_auto_upload_apply_feeders_for_profiles(profiles)
        return result

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
            source_field = source_model._fields.get(mapping.source_field_name) if source_model else False
            target_field = target_model._fields[mapping.target_field_name]
            if (
                source_field
                and source_field.type == "many2one"
                and source_field.comodel_name == self.env["ab_odoo_sync_rules"].sudo().user_source_model()
            ):
                if mapping.mapping_type == "ignore":
                    continue
                user_target = self.env["ab_odoo_sync_rules"].sudo().user_mirror_model()
                if (
                    mapping.mapping_type != "sync_many2one"
                    or target_field.type != "many2one"
                    or target_field.comodel_name != user_target
                ):
                    raise ValidationError(
                        _(
                            "Source user field %(source)s must map with sync_many2one to a %(user_model)s field."
                        )
                        % {
                            "source": "%s.%s" % (profile.source_model_name, mapping.source_field_name),
                            "user_model": user_target,
                        }
                    )
            if mapping.mapping_type in stable_types and (
                not mapping.relation_source_key or not mapping.relation_target_key
            ):
                raise ValidationError(
                    _("Stable-key mappings require both relation key fields.")
                )
            if mapping.mapping_type in {"stable_many2one", "stable_many2many"}:
                if self.env["ab_odoo_sync_rules"].sudo().is_never_mirror_model(target_field.comodel_name):
                    raise ValidationError(
                        _("Relations to %(model)s must use source-ID sync mapping according to sync-rules.md.")
                        % {"model": target_field.comodel_name}
                    )
