import secrets

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class AbEmployeeAccess(models.Model):
    _name = "ab_employee_access"
    _description = "Employee Access Profile"
    _order = "employee_id, id"
    _rec_name = "employee_id"

    costcenter_id = fields.Many2one("ab_costcenter")
    employee_id = fields.Many2one("ab_hr_employee", compute='_compute_employee_id', store=True, index=True,
                                  readonly=False, ondelete="restrict")

    employee_name = fields.Char(related="employee_id.name", string="Employee Name", readonly=True)
    department_id = fields.Many2one(related="employee_id.department_id", readonly=True)
    job_id = fields.Many2one(related="employee_id.job_id", readonly=True)

    pos_pin = fields.Char(
        string="POS PIN",
        copy=False,
        default=lambda self: self._generate_pos_pin(),
    )
    pos_pin_last_changed = fields.Datetime(copy=False, default=fields.Datetime.now)
    pos_pin_note = fields.Char(copy=False)
    pos_allow_login = fields.Boolean(default=True)

    pos_use_custom_permissions = fields.Boolean(
        string="Use Custom POS Permissions",
        help="When enabled, this employee uses custom permissions instead of the role defaults.",
    )
    pos_allow_pos_screen = fields.Boolean(default=True)
    pos_allow_cashier_screen = fields.Boolean(default=False)
    pos_allow_return_screen = fields.Boolean(default=False)
    pos_allow_sale = fields.Boolean(default=True)
    pos_allow_return = fields.Boolean(default=False)
    pos_allow_discount = fields.Boolean(default=False)
    pos_allow_cancel = fields.Boolean(default=False)
    pos_allow_change_price = fields.Boolean(default=False)
    pos_allow_manager_approval = fields.Boolean(default=False)
    pos_require_manager_for_return = fields.Boolean(default=True)
    pos_require_manager_for_cancel = fields.Boolean(default=True)
    pos_require_manager_for_price_change = fields.Boolean(default=False)
    pos_discount_percent_limit = fields.Float(default=0.0)
    pos_discount_percent_with_manager_limit = fields.Float(default=0.0)
    pos_idle_lock_seconds = fields.Integer(default=600)
    pos_pin_rotation_days = fields.Integer(default=90)

    pos_allowed_store_ids = fields.Many2many(
        "ab_store",
        "ab_sales_hr_profile_store_rel",
        "profile_id",
        "store_id",
        string="Allowed POS Stores",
    )
    pos_pin_expired = fields.Boolean(compute="_compute_pos_pin_expired")

    _employee_key = models.Constraint(
        "UNIQUE(employee_id)",
        "Each employee can only have one POS HR profile.",
    )

    pos_role_id = fields.Many2one("ab_employee_access_sales_role", string="POS Role")

    @api.depends('costcenter_id')
    def _compute_employee_id(self):
        for rec in self:
            if rec.costcenter_id:
                rec.employee_id = self.env['ab_hr_employee'].search([('costcenter_id', '=', rec.costcenter_id.id)],
                                                                    limit=1).id

    @api.model
    def _generate_pos_pin(self):
        return f"{secrets.randbelow(10000):04d}"

    @api.depends("pos_pin_last_changed", "pos_pin_rotation_days")
    def _compute_pos_pin_expired(self):
        now = fields.Datetime.now()
        for rec in self:
            rotation_days = int(rec.pos_pin_rotation_days or 90)
            changed_at = rec.pos_pin_last_changed or rec.write_date or rec.create_date or now
            deadline = fields.Datetime.add(changed_at, days=rotation_days)
            rec.pos_pin_expired = bool(deadline and deadline < now)

    @api.constrains("pos_pin")
    def _check_pos_pin(self):
        for rec in self:
            if rec.pos_pin and (len(rec.pos_pin) != 4 or not rec.pos_pin.isdigit()):
                raise ValidationError("POS PIN must contain exactly 4 digits.")

    @api.constrains(
        "pos_discount_percent_limit",
        "pos_discount_percent_with_manager_limit",
        "pos_pin_rotation_days",
    )
    def _check_pos_security_numbers(self):
        for rec in self:
            if rec.pos_discount_percent_limit < 0:
                raise ValidationError("POS discount percent limit must be zero or greater.")
            if rec.pos_discount_percent_with_manager_limit < rec.pos_discount_percent_limit:
                raise ValidationError("POS manager discount limit must be greater than or equal to direct limit.")
            if rec.pos_pin_rotation_days < 1:
                raise ValidationError("POS PIN rotation days must be at least 1.")

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for vals in vals_list:
            values = dict(vals or {})
            if not values.get("pos_pin"):
                values["pos_pin"] = self._generate_pos_pin()
            if not values.get("pos_pin_last_changed"):
                values["pos_pin_last_changed"] = fields.Datetime.now()
            prepared.append(values)
        return super().create(prepared)

    def write(self, vals):
        values = dict(vals or {})
        if "pos_pin" in values and values.get("pos_pin"):
            values.setdefault("pos_pin_last_changed", fields.Datetime.now())
        return super().write(values)

    def _effective_pos_permissions(self):
        self.ensure_one()
        if self.pos_use_custom_permissions:
            return {
                "allow_pos_screen": bool(self.pos_allow_pos_screen),
                "allow_cashier_screen": bool(self.pos_allow_cashier_screen),
                "allow_return_screen": bool(self.pos_allow_return_screen),
                "allow_sale": bool(self.pos_allow_sale),
                "allow_return": bool(self.pos_allow_return),
                "allow_discount": bool(self.pos_allow_discount),
                "allow_cancel": bool(self.pos_allow_cancel),
                "allow_change_price": bool(self.pos_allow_change_price),
                "allow_manager_approval": bool(self.pos_allow_manager_approval),
                "require_manager_for_return": bool(self.pos_require_manager_for_return),
                "require_manager_for_cancel": bool(self.pos_require_manager_for_cancel),
                "require_manager_for_price_change": bool(self.pos_require_manager_for_price_change),
                "discount_percent_limit": float(self.pos_discount_percent_limit or 0.0),
                "discount_percent_with_manager_limit": float(self.pos_discount_percent_with_manager_limit or 0.0),
                "pin_rotation_days": int(self.pos_pin_rotation_days or 90),
            }
        return {
            "allow_pos_screen": True,
            "allow_cashier_screen": False,
            "allow_return_screen": False,
            "allow_sale": True,
            "allow_return": False,
            "allow_discount": False,
            "allow_cancel": False,
            "allow_change_price": False,
            "allow_manager_approval": False,
            "require_manager_for_return": True,
            "require_manager_for_cancel": True,
            "require_manager_for_price_change": False,
            "discount_percent_limit": 0.0,
            "discount_percent_with_manager_limit": 0.0,
            "pin_rotation_days": 90,
        }

    def pos_permission_payload(self):
        self.ensure_one()
        permissions = self._effective_pos_permissions()
        return {
            "role_id": False,
            "role_name": "",
            "permissions": permissions,
            "pin_expired": bool(self.pos_pin_expired),
            "allowed_store_ids": self.pos_allowed_store_ids.ids,
        }

    def check_pos_pin(self, pin):
        self.ensure_one()
        return bool(self.pos_pin and str(self.pos_pin) == str(pin or "").strip())

    @api.model
    def _find_by_employee_code(self, code):
        code_value = (code or "").strip()
        if not code_value:
            return self.browse()
        return self.search(
            [("employee_id.costcenter_id.code", "=ilike", code_value)], limit=1,
        )

    def _is_store_allowed_for_pos(self, store):
        self.ensure_one()
        store = store.exists()
        if not store:
            return False
        if not self.pos_allowed_store_ids:
            return bool(store.allow_sale)
        return store.id in self.pos_allowed_store_ids.ids

    def action_generate_pos_pin(self):
        for rec in self:
            rec.write({
                "pos_pin": rec._generate_pos_pin(),
                "pos_pin_last_changed": fields.Datetime.now(),
                "pos_pin_note": "PIN regenerated from POS HR profile.",
            })
        return True
