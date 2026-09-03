from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.translate import _


class AbOdooSyncUploadFieldOverride(models.Model):
    _name = "ab_odoo_sync_upload_field_override"
    _description = "AB Odoo Sync Upload Field Override"
    _order = "sequence, source_field_name"

    upload_record_id = fields.Many2one(
        "ab_odoo_sync_upload_record",
        string="Received Upload",
        required=True,
        index=True,
        ondelete="cascade",
    )
    sequence = fields.Integer(default=10)
    sync_enabled = fields.Boolean(string="Sync Enabled", default=True, index=True)
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

    _uniq_upload_source_field = models.Constraint(
        "UNIQUE(upload_record_id, source_field_name)",
        "Only one field override is allowed per received upload and source field.",
    )

    @api.constrains(
        "upload_record_id",
        "source_field_name",
        "target_field_name",
        "mapping_type",
        "relation_source_key",
        "relation_target_key",
        "required",
    )
    def _check_override(self):
        stable_types = {"stable_many2one", "stable_many2many"}
        relation_types = {
            "sync_many2one": "many2one",
            "stable_many2one": "many2one",
            "sync_many2many": "many2many",
            "stable_many2many": "many2many",
        }
        for override in self:
            upload = override.upload_record_id
            payload_fields = upload._payload_fields()
            if override.source_field_name not in payload_fields:
                raise ValidationError(
                    _("Source field %(field)s does not exist in the received payload.")
                    % {"field": override.source_field_name}
                )
            if override.mapping_type == "ignore":
                if override.required:
                    raise ValidationError(_("Ignored fields cannot be required."))
                continue
            if upload.target_model_name not in self.env:
                raise ValidationError(
                    _("Target model %(model)s is not installed.")
                    % {"model": upload.target_model_name}
                )
            target_model = self.env[upload.target_model_name]
            target_field = target_model._fields.get(override.target_field_name)
            if not target_field:
                raise ValidationError(
                    _("Target field %(field)s does not exist on %(model)s.")
                    % {
                        "field": override.target_field_name,
                        "model": upload.target_model_name,
                    }
                )
            expected_type = relation_types.get(override.mapping_type)
            if expected_type and target_field.type != expected_type:
                raise ValidationError(
                    _("Mapping type %(mapping)s requires a %(field_type)s target field.")
                    % {
                        "mapping": override.mapping_type,
                        "field_type": expected_type,
                    }
                )
            if override.mapping_type == "direct" and target_field.type in {
                "many2one",
                "one2many",
                "many2many",
            }:
                raise ValidationError(
                    _("Relational target field %(field)s requires a relation mapping type.")
                    % {"field": override.target_field_name}
                )
            if override.mapping_type in stable_types and (
                not override.relation_source_key or not override.relation_target_key
            ):
                raise ValidationError(
                    _("Stable-key mappings require both relation key fields.")
                )

