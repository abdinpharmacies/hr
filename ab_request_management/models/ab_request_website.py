import re

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools import single_email_re
from odoo.tools.translate import _


EXTERNAL_REQUEST_SEQUENCE_CODE = "ab_request_website.request_number"
EXTERNAL_REVIEWER_GROUP = "ab_request_management.group_ab_request_management_viewer"
EXTERNAL_MANAGER_GROUP = "ab_request_management.group_ab_request_management_manager"
EXTERNAL_ADMIN_GROUP = "ab_request_management.group_ab_request_management_admin"
_EXTERNAL_STATE_WRITE_TOKEN = object()
_PHONE_PATTERN = re.compile(r"^[0-9+().\-\s]+$")
_NATIONAL_ID_PATTERN = re.compile(r"^[0-9]{14}$")


class AbRequestWebsite(models.Model):
    _name = "ab_request_website"
    _description = "External Request or Complaint"
    _order = "create_date desc, id desc"
    _rec_name = "name"

    name = fields.Char(
        string="External Reference",
        required=True,
        readonly=True,
        copy=False,
        index=True,
        default="New",
    )
    active = fields.Boolean(default=True)
    customer_name = fields.Char(required=True)
    customer_phone = fields.Char(required=True)
    customer_email = fields.Char()
    requester_type = fields.Selection(
        [
            ("employee", "Employee"),
            ("supplier", "Supplier"),
        ],
        string="Requester Type",
        required=True,
        default="employee",
    )
    employee_code = fields.Char(string="Employee Code")
    commercial_register_number = fields.Char(string="Commercial Register Number")
    national_id = fields.Char(string="National ID")
    followup_ids = fields.One2many(
        "ab_request_website_followup",
        "request_id",
        string="Follow-ups",
    )
    request_category_id = fields.Many2one(
        "ab_request_category",
        string="Category",
        ondelete="restrict",
    )
    request_type_id = fields.Many2one(
        "ab_request_type",
        string="Request/Complaint Type",
        required=True,
        ondelete="restrict",
    )
    subject = fields.Char(required=True)
    description = fields.Text(required=True)
    source = fields.Selection(
        [
            ("website", "Website"),
            ("embed", "Embedded Website Form"),
        ],
        default="embed",
        required=True,
        readonly=True,
    )
    state = fields.Selection(
        [
            ("new", "New"),
            ("reviewed", "Under Review"),
            ("converted", "Converted"),
            ("closed", "Closed"),
        ],
        default="new",
        required=True,
        readonly=True,
        copy=False,
        index=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        prepared_vals_list = [self._prepare_create_vals(vals) for vals in vals_list]
        return super().create(prepared_vals_list)

    def write(self, vals):
        prepared_vals = self._prepare_text_vals(vals)
        if "state" in prepared_vals and self.env.context.get("_external_state_write_token") is not _EXTERNAL_STATE_WRITE_TOKEN:
            raise UserError(_("Use the external request workflow actions to change the state."))
        return super().write(prepared_vals)

    @api.model
    def _prepare_create_vals(self, vals):
        prepared_vals = self._prepare_text_vals(vals)
        prepared_vals["state"] = "new"
        if not prepared_vals.get("requester_type"):
            prepared_vals["requester_type"] = (
                "supplier"
                if prepared_vals.get("commercial_register_number") and not prepared_vals.get("employee_code")
                else "employee"
            )
        if not prepared_vals.get("name") or prepared_vals.get("name") == "New":
            prepared_vals["name"] = (
                self.env["ir.sequence"].sudo().next_by_code(EXTERNAL_REQUEST_SEQUENCE_CODE) or "New"
            )
        return prepared_vals

    @api.model
    def _prepare_text_vals(self, vals):
        prepared_vals = dict(vals or {})
        for field_name in (
                "customer_name",
                "customer_phone",
                "customer_email",
                "requester_type",
                "employee_code",
                "commercial_register_number",
                "national_id",
                "subject",
                "description",
        ):
            if field_name in prepared_vals and isinstance(prepared_vals[field_name], str):
                prepared_vals[field_name] = prepared_vals[field_name].strip()
        return prepared_vals

    @api.constrains("request_category_id", "request_type_id")
    def _check_public_routing(self):
        for record in self:
            category = record.request_category_id
            request_type = record.request_type_id
            if not category:
                raise ValidationError(_("Category is required."))
            if not request_type:
                raise ValidationError(_("Request/complaint type is required."))
            if request_type.category_id != category:
                raise ValidationError(_("The selected request type must belong to the selected category."))
            if not category.is_public or not request_type.is_public:
                raise ValidationError(_("The selected category and request type are not available for public requests."))

    @api.constrains(
        "customer_name",
        "customer_phone",
        "customer_email",
        "requester_type",
        "employee_code",
        "commercial_register_number",
        "national_id",
        "subject",
        "description",
    )
    def _check_external_content(self):
        for record in self:
            values = {
                "customer_name": (record.customer_name or "").strip(),
                "customer_phone": (record.customer_phone or "").strip(),
                "customer_email": (record.customer_email or "").strip(),
                "requester_type": record.requester_type,
                "employee_code": (record.employee_code or "").strip(),
                "commercial_register_number": (record.commercial_register_number or "").strip(),
                "national_id": (record.national_id or "").strip(),
                "subject": (record.subject or "").strip(),
                "description": (record.description or "").strip(),
            }
            required_labels = {
                "customer_name": _("Customer name"),
                "customer_phone": _("Customer phone"),
                "subject": _("Subject"),
                "description": _("Details"),
            }
            for field_name, label in required_labels.items():
                if not values[field_name]:
                    raise ValidationError(_("%s is required.") % label)
            if values["requester_type"] == "employee":
                if not values["employee_code"]:
                    raise ValidationError(_("Employee code is required."))
                if not values["national_id"]:
                    raise ValidationError(_("National ID is required."))
                if values["commercial_register_number"]:
                    raise ValidationError(_("Commercial register number is only available for supplier requests."))
            elif values["requester_type"] == "supplier":
                if not values["commercial_register_number"]:
                    raise ValidationError(_("Commercial register number is required."))
                if values["employee_code"]:
                    raise ValidationError(_("Employee code is only available for employee requests."))
            else:
                raise ValidationError(_("Requester type is required."))

            length_limits = {
                "customer_name": (120, _("Customer name")),
                "customer_phone": (30, _("Customer phone")),
                "customer_email": (254, _("Customer email")),
                "employee_code": (50, _("Employee code")),
                "commercial_register_number": (50, _("Commercial register number")),
                "national_id": (14, _("National ID")),
                "subject": (200, _("Subject")),
                "description": (3000, _("Details")),
            }
            for field_name, (maximum, label) in length_limits.items():
                if len(values[field_name]) > maximum:
                    raise ValidationError(_("%(field)s must not exceed %(maximum)s characters.") % {
                        "field": label,
                        "maximum": maximum,
                    })

            for field_name, label in (("customer_name", _("Customer name")), ("subject", _("Subject")),
                                      ("description", _("Details"))):
                if not any(character.isalpha() for character in values[field_name]):
                    raise ValidationError(_("%s must contain letters and cannot be only numbers or symbols.") % label)

            phone = values["customer_phone"]
            phone_digits = sum(character.isdigit() for character in phone)
            if not _PHONE_PATTERN.fullmatch(phone) or not 7 <= phone_digits <= 15:
                raise ValidationError(_("Enter a valid phone number containing between 7 and 15 digits."))
            if values["customer_email"] and not single_email_re.fullmatch(values["customer_email"]):
                raise ValidationError(_("Enter a valid email address."))
            if values["national_id"] and not _NATIONAL_ID_PATTERN.fullmatch(values["national_id"]):
                raise ValidationError(_("National ID must contain exactly 14 digits."))

    def _check_external_workflow_access(self):
        """Authorize both the role and the record scope before a state transition."""
        current_user = self.env.user
        if current_user.has_group(EXTERNAL_ADMIN_GROUP):
            return

        is_manager = current_user.has_group(EXTERNAL_MANAGER_GROUP)
        is_complaint_reviewer = current_user.has_group(EXTERNAL_REVIEWER_GROUP)
        unauthorized = self.filtered(
            lambda record: not (
                (is_manager and record.request_type_id.manager_id.user_id == current_user)
                or (is_complaint_reviewer and record.request_category_id.type == "complaint")
            )
        )
        if unauthorized:
            raise AccessError(_("You are not allowed to process these external requests."))

    def action_mark_under_review(self):
        self._check_external_workflow_access()
        if self.filtered(lambda record: record.state != "new"):
            raise UserError(_("Only new external requests can be moved under review."))
        self.with_context(_external_state_write_token=_EXTERNAL_STATE_WRITE_TOKEN).write({"state": "reviewed"})
        return True

    def action_close(self):
        self._check_external_workflow_access()
        if self.filtered(lambda record: record.state != "reviewed"):
            raise UserError(_("Only external requests under review can be closed."))
        self.with_context(_external_state_write_token=_EXTERNAL_STATE_WRITE_TOKEN).write({"state": "closed"})
        return True
