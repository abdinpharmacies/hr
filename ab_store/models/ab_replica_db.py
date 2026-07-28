from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import config
from odoo.tools.translate import _

DB_SERIAL_SEQUENCE_CODE = "ab_replica_db.db_serial"


class AbReplicaDB(models.Model):
    _name = "ab_replica_db"
    _description = "Replica Database"
    _order = "name"

    name = fields.Char(required=True)
    db_serial = fields.Integer(
        string="DB Serial",
        required=True,
        index=True,
        readonly=True,
        copy=False,
    )
    active = fields.Boolean(default=True)
    return_allowed_days = fields.Integer(
        string="Return Allowed Days",
        default=14,
        required=True,
    )

    allowed_sales_store_ids = fields.Many2many(
        "ab_store",
        "ab_replica_db_store_rel",
        "replica_db_id",
        "store_id",
        string="Allowed Sales Stores",
        domain=[("allow_sale", "=", True)],
    )
    default_sales_store_id = fields.Many2one(
        "ab_store",
        string="Default Sales Store",
        domain=[("allow_sale", "=", True)],
    )

    _uniq_db_serial = models.Constraint(
        "UNIQUE(db_serial)",
        _("Replica DB serial must be unique."),
    )

    @api.model
    def _next_db_serial(self):
        next_value = self.env["ir.sequence"].sudo().next_by_code(DB_SERIAL_SEQUENCE_CODE)
        if not next_value:
            raise ValidationError(_("Replica DB serial sequence is not configured."))
        try:
            return int(next_value)
        except (TypeError, ValueError):
            raise ValidationError(_("Replica DB serial sequence must return a number."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("db_serial"):
                vals["db_serial"] = self._next_db_serial()
        return super().create(vals_list)

    @api.constrains("db_serial")
    def _check_db_serial_positive(self):
        for rec in self:
            if rec.db_serial <= 0:
                raise ValidationError(_("Replica DB serial must be a positive integer."))

    @api.constrains("return_allowed_days")
    def _check_return_allowed_days_non_negative(self):
        for rec in self:
            if rec.return_allowed_days < 1:
                raise ValidationError(_("Return allowed days must be at least 1 day."))

    @api.constrains("default_sales_store_id", "allowed_sales_store_ids")
    def _check_default_store_allowed(self):
        for rec in self:
            if (
                    rec.default_sales_store_id
                    and rec.allowed_sales_store_ids
                    and rec.default_sales_store_id not in rec.allowed_sales_store_ids
            ):
                raise ValidationError(
                    _("Default sales store must be one of the allowed sales stores.")
                )

    @api.model
    def get_current_from_config(self):
        serial = int(config.get("db_serial", 0) or 0)
        if not serial:
            return self.browse()
        return self.sudo().search([("db_serial", "=", serial)], limit=1)
