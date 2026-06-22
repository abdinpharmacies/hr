from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class InternalShipment(models.Model):
    _name = "ab_internal_shipment"
    _description = "Internal Shipment"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "shipment_date desc, id desc"

    name = fields.Char(
        string="Shipment Reference",
        required=True,
        copy=False,
        default="/",
        readonly=True,
        tracking=True,
    )
    shipment_date = fields.Date(
        default=fields.Date.context_today,
        required=True,
        tracking=True,
    )
    shipment_type = fields.Selection(
        [
            ("documents", "Documents"),
            ("devices", "Devices"),
            ("mixed", "Mixed"),
            ("other", "Other"),
        ],
        required=True,
        default="documents",
        tracking=True,
    )
    subject = fields.Char(required=True, tracking=True)
    description = fields.Text()
    notes = fields.Text(tracking=True)
    delivery_method = fields.Selection(
        [
            ("company_vehicle", "Internal Company Vehicle"),
            ("external_company", "External Shipping Company"),
            ("hand_delivery", "Hand Delivery"),
            ("other", "Other"),
        ],
        required=True,
        default="hand_delivery",
        tracking=True,
    )
    expected_delivery_date = fields.Date(tracking=True)
    is_delayed = fields.Boolean(compute="_compute_is_delayed", store=True)
    shipment_count = fields.Integer(
        string="Shipment Count",
        default=1,
        readonly=True,
        aggregator="sum",
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("sent", "Sent"),
            ("in_transit", "In Transit"),
            ("delivered", "Delivered"),
            ("received", "Received"),
            ("closed", "Closed"),
        ],
        required=True,
        default="draft",
        tracking=True,
        index=True,
    )

    sender_type = fields.Selection(
        [("branch", "Branch"), ("department", "Department"), ("employee", "Employee")],
        required=True,
        default="department",
        tracking=True,
    )
    sender_store_id = fields.Many2one(
        "ab_store",
        string="Sender Branch",
        domain=[("store_type", "=", "branch")],
        tracking=True,
    )
    sender_department_id = fields.Many2one(
        "ab_hr_department",
        string="Sender Department",
        tracking=True,
    )
    sender_employee_id = fields.Many2one(
        "ab_hr_employee",
        string="Sender Employee",
        tracking=True,
    )
    sender_user_id = fields.Many2one(
        "res.users",
        compute="_compute_party_users",
        store=True,
        index=True,
    )
    sender_display = fields.Char(compute="_compute_party_displays", store=True)

    recipient_type = fields.Selection(
        [("branch", "Branch"), ("department", "Department"), ("employee", "Employee")],
        required=True,
        default="department",
        tracking=True,
    )
    recipient_store_id = fields.Many2one(
        "ab_store",
        string="Recipient Branch",
        domain=[("store_type", "=", "branch")],
        tracking=True,
    )
    recipient_department_id = fields.Many2one(
        "ab_hr_department",
        string="Recipient Department",
        tracking=True,
    )
    recipient_employee_id = fields.Many2one(
        "ab_hr_employee",
        string="Recipient Employee",
        tracking=True,
    )
    recipient_user_id = fields.Many2one(
        "res.users",
        compute="_compute_party_users",
        store=True,
        index=True,
    )
    recipient_display = fields.Char(compute="_compute_party_displays", store=True)

    created_by_id = fields.Many2one(
        "res.users",
        string="Created By",
        default=lambda self: self.env.user,
        readonly=True,
        index=True,
    )
    sent_by_id = fields.Many2one("res.users", readonly=True, index=True)
    sent_date = fields.Datetime(readonly=True)
    delivered_by_id = fields.Many2one("res.users", readonly=True, index=True)
    delivered_date = fields.Datetime(readonly=True)
    received_by_id = fields.Many2one("res.users", readonly=True, index=True)
    received_date = fields.Datetime(readonly=True)
    closed_by_id = fields.Many2one("res.users", readonly=True, index=True)
    closed_date = fields.Datetime(readonly=True)

    current_holder_type = fields.Selection(
        [("branch", "Branch"), ("department", "Department"), ("employee", "Employee")],
        readonly=True,
        tracking=True,
    )
    current_holder_store_id = fields.Many2one("ab_store", readonly=True, tracking=True)
    current_holder_department_id = fields.Many2one("ab_hr_department", readonly=True, tracking=True)
    current_holder_employee_id = fields.Many2one("ab_hr_employee", readonly=True, tracking=True)
    current_holder_user_id = fields.Many2one(
        "res.users",
        readonly=True,
        tracking=True,
        index=True,
    )
    current_holder_display = fields.Char(
        compute="_compute_current_holder_display",
        store=True,
    )

    line_ids = fields.One2many(
        "ab_internal_shipment.line",
        "shipment_id",
        string="Shipment Contents",
    )
    history_ids = fields.One2many(
        "ab_internal_shipment.history",
        "shipment_id",
        string="Movement History",
        readonly=True,
    )
    delivery_proof_attachment_ids = fields.Many2many(
        "ir.attachment",
        "ab_internal_shipment_delivery_proof_rel",
        "shipment_id",
        "attachment_id",
        string="Delivery Proof",
        help="Signed receipt, delivery image, or confirmation document.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        sequence = self.env["ir.sequence"].sudo()
        for vals in vals_list:
            if vals.get("name", "/") == "/":
                vals["name"] = sequence.next_by_code("ab.internal.shipment") or "/"
            vals.setdefault("created_by_id", self.env.uid)
        records = super().create(vals_list)
        records._set_current_holder_from_sender()
        for record in records:
            record._create_history("created", False, record.state, _("Shipment created."))
        return records

    def write(self, vals):
        res = super().write(vals)
        party_fields = {
            "sender_type",
            "sender_store_id",
            "sender_department_id",
            "sender_employee_id",
        }
        draft_records = self.filtered(lambda record: record.state == "draft")
        if draft_records and party_fields.intersection(vals):
            draft_records._set_current_holder_from_sender()
        return res

    @api.onchange("sender_type")
    def _onchange_sender_type(self):
        self.sender_store_id = False
        self.sender_department_id = False
        self.sender_employee_id = False

    @api.onchange("recipient_type")
    def _onchange_recipient_type(self):
        self.recipient_store_id = False
        self.recipient_department_id = False
        self.recipient_employee_id = False

    @api.constrains(
        "sender_type",
        "sender_store_id",
        "sender_department_id",
        "sender_employee_id",
        "recipient_type",
        "recipient_store_id",
        "recipient_department_id",
        "recipient_employee_id",
        "line_ids",
    )
    def _check_required_entities(self):
        for record in self:
            record._validate_party("sender")
            record._validate_party("recipient")
            if not record.line_ids:
                raise ValidationError(_("Add at least one shipment content line."))

    @api.depends("state", "expected_delivery_date")
    def _compute_is_delayed(self):
        today = fields.Date.context_today(self)
        for record in self:
            record.is_delayed = (
                bool(record.expected_delivery_date)
                and record.expected_delivery_date < today
                and record.state not in ("received", "closed")
            )

    @api.depends(
        "sender_employee_id.user_id",
        "sender_department_id.manager_id.user_id",
        "recipient_employee_id.user_id",
        "recipient_department_id.manager_id.user_id",
    )
    def _compute_party_users(self):
        for record in self:
            record.sender_user_id = record._get_party_user("sender")
            record.recipient_user_id = record._get_party_user("recipient")

    @api.depends(
        "sender_type",
        "sender_store_id",
        "sender_department_id",
        "sender_employee_id",
        "recipient_type",
        "recipient_store_id",
        "recipient_department_id",
        "recipient_employee_id",
    )
    def _compute_party_displays(self):
        for record in self:
            record.sender_display = record._get_party_display("sender")
            record.recipient_display = record._get_party_display("recipient")

    @api.depends(
        "current_holder_type",
        "current_holder_store_id",
        "current_holder_department_id",
        "current_holder_employee_id",
    )
    def _compute_current_holder_display(self):
        for record in self:
            if record.current_holder_type == "branch":
                record.current_holder_display = record.current_holder_store_id.display_name
            elif record.current_holder_type == "department":
                record.current_holder_display = record.current_holder_department_id.display_name
            elif record.current_holder_type == "employee":
                record.current_holder_display = record.current_holder_employee_id.display_name
            else:
                record.current_holder_display = False

    def action_send(self):
        self._move_state("draft", "sent", "sent_by_id", "sent_date", "sent")

    def action_mark_in_transit(self):
        self._move_state(("sent",), "in_transit", False, False, "in_transit")

    def action_deliver(self):
        self._move_state(("sent", "in_transit"), "delivered", "delivered_by_id", "delivered_date", "delivered")
        for record in self:
            record._schedule_receipt_activity()

    def action_receive(self):
        self._move_state("delivered", "received", "received_by_id", "received_date", "received")

    def action_close(self):
        self._move_state("received", "closed", "closed_by_id", "closed_date", "closed")

    def action_add_tracking_note(self):
        for record in self:
            record._create_history("note", record.state, record.state, record.notes or _("Tracking note added."))

    def _move_state(self, allowed_from, target_state, user_field, date_field, action):
        allowed = {allowed_from} if isinstance(allowed_from, str) else set(allowed_from)
        now = fields.Datetime.now()
        for record in self:
            if record.state not in allowed:
                raise UserError(
                    _("Shipment %(name)s cannot move from %(current)s to %(target)s.")
                    % {
                        "name": record.display_name,
                        "current": record.state,
                        "target": target_state,
                    }
                )
            old_state = record.state
            old_holder = record.current_holder_display
            vals = {"state": target_state}
            if user_field:
                vals[user_field] = self.env.uid
            if date_field:
                vals[date_field] = now
            vals.update(record._holder_values_for_state(target_state))
            record.write(vals)
            record._create_history(action, old_state, target_state, _("State changed."), old_holder=old_holder)

    def _holder_values_for_state(self, state):
        self.ensure_one()
        if state in ("draft", "sent", "in_transit"):
            return self._holder_values_from_party("sender")
        return self._holder_values_from_party("recipient")

    def _set_current_holder_from_sender(self):
        for record in self:
            record.write(record._holder_values_from_party("sender"))

    def _holder_values_from_party(self, party):
        self.ensure_one()
        party_type = self[f"{party}_type"]
        values = {
            "current_holder_type": party_type,
            "current_holder_store_id": False,
            "current_holder_department_id": False,
            "current_holder_employee_id": False,
            "current_holder_user_id": self._get_party_user(party).id,
        }
        if party_type == "branch":
            values["current_holder_store_id"] = self[f"{party}_store_id"].id
        elif party_type == "department":
            values["current_holder_department_id"] = self[f"{party}_department_id"].id
        elif party_type == "employee":
            values["current_holder_employee_id"] = self[f"{party}_employee_id"].id
        return values

    def _get_party_display(self, party):
        self.ensure_one()
        party_type = self[f"{party}_type"]
        if party_type == "branch":
            return self[f"{party}_store_id"].display_name
        if party_type == "department":
            return self[f"{party}_department_id"].display_name
        if party_type == "employee":
            return self[f"{party}_employee_id"].display_name
        return False

    def _get_party_user(self, party):
        self.ensure_one()
        party_type = self[f"{party}_type"]
        if party_type == "employee":
            return self[f"{party}_employee_id"].user_id
        if party_type == "department":
            return self[f"{party}_department_id"].manager_id.user_id
        return self.env["res.users"]

    def _validate_party(self, party):
        self.ensure_one()
        party_type = self[f"{party}_type"]
        fields_by_type = {
            "branch": f"{party}_store_id",
            "department": f"{party}_department_id",
            "employee": f"{party}_employee_id",
        }
        required_field = fields_by_type[party_type]
        if not self[required_field]:
            raise ValidationError(_("Select the %(party)s %(type)s.") % {"party": party, "type": party_type})
        for field_name in fields_by_type.values():
            if field_name != required_field and self[field_name]:
                raise ValidationError(
                    _("Only the selected %(party)s entity type can be filled.") % {"party": party}
                )

    def _create_history(self, action, state_from, state_to, notes=False, old_holder=False):
        History = self.env["ab_internal_shipment.history"].sudo()
        for record in self:
            History.create(
                {
                    "shipment_id": record.id,
                    "action": action,
                    "action_by_id": self.env.uid,
                    "action_date": fields.Datetime.now(),
                    "state_to": state_to or "",
                    "state_from": state_from or "",
                    "from_holder_display": old_holder or "",
                    "to_holder_display": record.current_holder_display or "",
                    "notes": notes,
                }
            )

    def _schedule_receipt_activity(self):
        self.ensure_one()
        if not self.recipient_user_id:
            return
        activity_type = self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)
        if not activity_type:
            return
        self.activity_schedule(
            activity_type_id=activity_type.id,
            user_id=self.recipient_user_id.id,
            summary=_("Shipment delivered, confirm receipt"),
            note=_("Shipment %s has been delivered and is awaiting receipt confirmation.") % self.name,
        )
