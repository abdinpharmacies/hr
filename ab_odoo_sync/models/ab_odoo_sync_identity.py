from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _


_RELATIONAL_FIELD_TYPES = {"many2one", "one2many", "many2many"}
_PLACEHOLDER_SKIP_FIELDS = {
    "id",
    "create_uid",
    "create_date",
    "write_uid",
    "write_date",
    "display_name",
}


class AbOdooSyncIdentity(models.Model):
    _name = "ab_odoo_sync_identity"
    _description = "AB Odoo Sync Identity"
    _order = "target_model_name, target_res_id, db_serial, source_model_name"

    db_serial = fields.Integer(string="DB Serial", required=True, readonly=True, index=True)
    source_model_name = fields.Char(string="Source Model", required=True, readonly=True, index=True)
    source_rec_id = fields.Integer(string="Source Record ID", required=True, readonly=True, index=True)
    target_model_name = fields.Char(string="Target Model", required=True, readonly=True, index=True)
    target_res_id = fields.Integer(string="Target Record ID", required=True, readonly=True, index=True)
    state = fields.Selection(
        selection=[
            ("placeholder", "Placeholder"),
            ("resolved", "Resolved"),
            ("conflict", "Conflict"),
        ],
        default="placeholder",
        required=True,
        readonly=True,
        index=True,
    )
    stable_key_json = fields.Json(string="Stable Keys", default=dict, readonly=True)
    last_upload_record_id = fields.Many2one(
        "ab_odoo_sync_upload_record",
        string="Last Upload Record",
        readonly=True,
        ondelete="set null",
    )
    note = fields.Text(string="Note", readonly=True)
    active = fields.Boolean(default=True, index=True)

    _uniq_source_identity = models.Constraint(
        "UNIQUE(db_serial, source_model_name, source_rec_id, target_model_name)",
        "Source identity must be unique per branch, source model, source ID, and target model.",
    )

    @api.model
    def _ensure_positive_int(self, value, field_name):
        try:
            parsed = int(value or 0)
        except (TypeError, ValueError) as ex:
            raise ValueError(_("%s must be a positive integer.") % field_name) from ex
        if parsed <= 0:
            raise ValueError(_("%s must be a positive integer.") % field_name)
        return parsed

    @api.model
    def _target_model(self, target_model_name):
        try:
            return self.env[target_model_name].with_context(
                active_test=False,
                skip_ab_odoo_sync_event=True,
            ).sudo()
        except KeyError as ex:
            raise ValueError(_("Target model %(model)s does not exist.") % {"model": target_model_name}) from ex

    @api.model
    def _force_next_id(self, target_model, target_res_id):
        self.env.cr.execute("SELECT pg_get_serial_sequence(%s, 'id')", (target_model._table,))
        row = self.env.cr.fetchone()
        seq_name = row and row[0]
        if not seq_name:
            raise ValueError(_("No sequence found for model %(model)s.") % {"model": target_model._name})
        self.env.cr.execute("SELECT setval(%s::regclass, %s, false)", (seq_name, target_res_id))

    @api.model
    def _can_write_placeholder_field(self, field):
        return (
            field.store
            and field.type not in _RELATIONAL_FIELD_TYPES
            and not (field.compute and not field.inverse)
        )

    @api.model
    def _placeholder_fallback_value(self, field, display_name, source_rec_id):
        if not self._can_write_placeholder_field(field):
            return None
        if field.type in {"char", "text", "html"}:
            return display_name or "SYNC-%s" % source_rec_id
        if field.type == "selection":
            selection = field.selection
            if isinstance(selection, (list, tuple)) and selection:
                return selection[0][0]
            return None
        if field.type in {"integer", "float", "monetary"}:
            return 0
        if field.type == "boolean":
            return False
        if field.type == "json":
            return {}
        if field.type == "date":
            return fields.Date.context_today(self)
        if field.type == "datetime":
            return fields.Datetime.now()
        return None

    @api.model
    def _prepare_placeholder_vals(self, target_model, source_rec_id, reference=None):
        reference = reference or {}
        rules = self.env["ab_odoo_sync_rules"].sudo()
        if rules.is_never_mirror_model(target_model._name) or target_model._name == rules.user_mirror_model():
            reference = {}
        identity_values = reference.get("values") if isinstance(reference, dict) else {}
        identity_values = identity_values if isinstance(identity_values, dict) else {}
        display_name = reference.get("display_name") if isinstance(reference, dict) else False

        vals = {}
        for field_name, value in identity_values.items():
            field = target_model._fields.get(field_name)
            if field and self._can_write_placeholder_field(field):
                vals[field_name] = value

        name_field = target_model._fields.get("name")
        if (
            display_name
            and "name" not in vals
            and name_field
            and self._can_write_placeholder_field(name_field)
        ):
            vals["name"] = display_name

        required_fields = [
            field_name
            for field_name, field in target_model._fields.items()
            if (
                field.required
                and field_name not in vals
                and field_name not in _PLACEHOLDER_SKIP_FIELDS
            )
        ]
        defaults = target_model.default_get(required_fields) if required_fields else {}
        for field_name in required_fields:
            default_value = defaults.get(field_name)
            if default_value not in (None, False, ""):
                vals[field_name] = default_value
                continue
            fallback = self._placeholder_fallback_value(
                target_model._fields[field_name],
                display_name,
                source_rec_id,
            )
            if fallback is not None:
                vals[field_name] = fallback

        return vals

    @api.model
    def _stable_key_values(self, reference=None):
        if not isinstance(reference, dict):
            return {}
        rules = self.env["ab_odoo_sync_rules"].sudo()
        model_name = reference.get("model")
        if rules.is_id_only_relation_model(model_name):
            return {}
        values = reference.get("values") or {}
        if not isinstance(values, dict):
            return {}
        return {
            key: values[key]
            for key in ("eplus_serial", "code", "barcode", "reference", "external_id", "name")
            if values.get(key) not in (None, False, "")
        }

    @api.model
    def get_or_create_business_record(
        self,
        db_serial,
        source_model_name,
        source_rec_id,
        target_model_name,
        reference=None,
        upload_record=False,
        create_placeholder=True,
    ):
        db_serial = self._ensure_positive_int(db_serial, "db_serial")
        source_rec_id = self._ensure_positive_int(source_rec_id, "source_rec_id")
        target_model = self._target_model(target_model_name)
        target_res_id = source_rec_id
        stable_keys = self._stable_key_values(reference)

        identity = self.sudo().search(
            [
                ("db_serial", "=", db_serial),
                ("source_model_name", "=", source_model_name),
                ("source_rec_id", "=", source_rec_id),
                ("target_model_name", "=", target_model_name),
            ],
            limit=1,
        )
        if identity and identity.target_res_id != target_res_id:
            identity.write(
                {
                    "state": "conflict",
                    "note": _("Expected target ID %(expected)s but identity points to %(actual)s.")
                    % {
                        "expected": target_res_id,
                        "actual": identity.target_res_id,
                    },
                    "last_upload_record_id": upload_record.id if upload_record else False,
                }
            )
            raise ValueError(_("Sync identity points to a different target record."))

        created_placeholder = False
        record = target_model.browse(target_res_id)
        if not record.exists():
            if not create_placeholder:
                return target_model.browse()
            vals = self._prepare_placeholder_vals(target_model, source_rec_id, reference)
            with self.env.cr.savepoint():
                self._force_next_id(target_model, target_res_id)
                record = target_model.create(vals)
                created_placeholder = True

        vals = {
            "target_res_id": target_res_id,
            "state": "placeholder" if created_placeholder or (identity and identity.state == "placeholder") else "resolved",
            "stable_key_json": stable_keys,
            "last_upload_record_id": upload_record.id if upload_record else False,
            "active": True,
            "note": False,
        }
        if identity:
            identity.write(vals)
        else:
            vals.update(
                {
                    "db_serial": db_serial,
                    "source_model_name": source_model_name,
                    "source_rec_id": source_rec_id,
                    "target_model_name": target_model_name,
                }
            )
            identity = self.sudo().create(vals)
        return record

    @api.model
    def mark_resolved(self, upload_record, target_model_name, target_res_id):
        target_res_id = self._ensure_positive_int(target_res_id, "target_res_id")
        payload = upload_record.payload_json or {}
        payload_fields = payload.get("fields") if isinstance(payload, dict) else {}
        payload_fields = payload_fields if isinstance(payload_fields, dict) else {}
        stable_keys = {
            key: payload_fields[key]
            for key in ("eplus_serial", "code", "barcode", "reference", "external_id", "name")
            if payload_fields.get(key) not in (None, False, "")
        }
        identity = self.sudo().search(
            [
                ("db_serial", "=", upload_record.db_serial),
                ("source_model_name", "=", upload_record.model_name),
                ("source_rec_id", "=", upload_record.rec_id),
                ("target_model_name", "=", target_model_name),
            ],
            limit=1,
        )
        vals = {
            "target_res_id": target_res_id,
            "state": "resolved",
            "stable_key_json": stable_keys,
            "last_upload_record_id": upload_record.id,
            "active": True,
            "note": False,
        }
        if identity:
            identity.write(vals)
            return identity
        vals.update(
            {
                "db_serial": upload_record.db_serial,
                "source_model_name": upload_record.model_name,
                "source_rec_id": upload_record.rec_id,
                "target_model_name": target_model_name,
            }
        )
        return self.sudo().create(vals)

    def unlink(self):
        raise UserError(_("Sync identities are audit records and cannot be deleted."))
