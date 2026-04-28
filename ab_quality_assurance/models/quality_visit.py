from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from uuid import uuid4

VISIT_SEQUENCE_CODE = "ab_quality_assurance.visit"
BRANCH_PREFIX = "فرع"


class AbQualityAssuranceVisit(models.Model):
    _name = "ab_quality_assurance_visit"
    _description = "Quality Assurance Visit"
    _order = "visit_date desc, id desc"

    name = fields.Char(required=True, readonly=True, copy=False, default="New")
    user_id = fields.Many2one("res.users", default=lambda self: self.env.user, readonly=True)
    employee_id = fields.Many2one("ab_hr_employee", required=False, ondelete="restrict", string="Visited By")
    department_id = fields.Many2one("ab_hr_department", required=False, ondelete="restrict", index=True)
    department_manager_id = fields.Many2one(
        "ab_hr_employee",
        related="department_id.manager_id",
        store=True,
        readonly=True,
    )
    visit_date = fields.Date(required=True, default=fields.Date.today)
    state = fields.Selection(
        [("draft", "Draft"), ("submitted", "Submitted")],
        default="draft",
        required=True,
        readonly=True,
        copy=False,
    )
    submitted_at = fields.Datetime(readonly=True, copy=False)
    visit_section_ids = fields.One2many("ab_quality_assurance_visit_section", "visit_id", string="Sections")
    max_total_score = fields.Float(compute="_compute_totals", store=True)
    earned_total_score = fields.Float(compute="_compute_totals", store=True)
    total_percentage = fields.Float(compute="_compute_totals", store=True)
    line_count = fields.Integer(compute="_compute_totals", store=True)
    section_count = fields.Integer(compute="_compute_totals", store=True)

    _ab_quality_assurance_visit_name_uniq = models.Constraint(
        "UNIQUE(name)",
        "Visit reference must be unique.",
    )

    @api.depends(
        "visit_section_ids",
        "visit_section_ids.visit_line_ids",
        "visit_section_ids.visit_line_ids.max_score",
        "visit_section_ids.visit_line_ids.score",
    )
    def _compute_totals(self):
        for record in self:
            lines = record.visit_section_ids.mapped("visit_line_ids")
            record.max_total_score = sum(lines.mapped("max_score"))
            record.earned_total_score = sum(lines.mapped("score"))
            record.total_percentage = (
                (record.earned_total_score / record.max_total_score) * 100 if record.max_total_score else 0.0
            )
            record.line_count = len(lines)
            record.section_count = len(record.visit_section_ids)

    @api.model
    def _default_employee_id(self):
        employee = self.env["ab_hr_employee"].sudo().search([("user_id", "=", self.env.user.id)], limit=1)
        return employee.id

    @api.model
    def default_get(self, fields_list):
        defaults = super().default_get(fields_list)
        if "employee_id" in fields_list and not defaults.get("employee_id"):
            defaults["employee_id"] = self._default_employee_id()
        if "user_id" in fields_list and not defaults.get("user_id"):
            defaults["user_id"] = self.env.user.id
        return defaults

    @api.onchange("department_id")
    def _onchange_department_id(self):
        if self.state == "submitted":
            return

        self.visit_section_ids = False
        if not self.department_id:
            return

        sections = self._get_active_sections()
        self.visit_section_ids = self._build_section_commands(sections)
        if not sections:
            return {
                "warning": {
                    "title": _("No Sections Found"),
                    "message": _("There are no active review sections configured yet."),
                }
            }

    @api.constrains("employee_id", "user_id")
    def _check_user_employee_link(self):
        for record in self:
            if (
                record.user_id
                and record.user_id.ab_employee_ids
                and record.employee_id
                and not record.user_id.has_group("ab_quality_assurance.group_ab_quality_assurance_admin")
            ):
                if record.user_id == self.env.user and record.employee_id.user_id != record.user_id:
                    raise ValidationError(_("The visit performer must match the current user's employee."))

    @api.constrains("department_id")
    def _check_branch_department(self):
        for record in self:
            if record.department_id and not (record.department_id.name or "").startswith(BRANCH_PREFIX):
                raise ValidationError(_("Visits can only evaluate branch departments whose names start with '%s'.") % BRANCH_PREFIX)

    @api.model_create_multi
    def create(self, vals_list):
        prepared_vals_list = [self._prepare_create_or_write_vals(vals, for_create=True) for vals in vals_list]
        records = super().create(prepared_vals_list)
        records._validate_visit_sections()
        return records

    def write(self, vals):
        if any(record.state == "submitted" for record in self) and not self.env.context.get("allow_submitted_visit_write"):
            raise UserError(_("Submitted visits cannot be modified."))

        prepared_vals = self._prepare_create_or_write_vals(vals, for_create=False)
        if prepared_vals.get("department_id") and "visit_section_ids" not in prepared_vals:
            sections = self._get_active_sections()
            prepared_vals["visit_section_ids"] = [fields.Command.clear(), *self._build_section_commands(sections)]
        result = super().write(prepared_vals)
        self._validate_visit_sections()
        return result

    def unlink(self):
        if any(record.state == "submitted" for record in self):
            raise UserError(_("Submitted visits cannot be deleted."))
        return super().unlink()

    def action_submit_visit(self):
        for record in self:
            if record.state != "draft":
                raise UserError(_("Only draft visits can be submitted."))
            if not record.department_id:
                raise ValidationError(_("Please select a department before submitting the visit."))
            if not record.employee_id:
                raise ValidationError(_("Please set the performer before submitting the visit."))
            if not record.visit_section_ids:
                raise ValidationError(_("There are no configured sections to evaluate in this visit."))
            visit_lines = record.visit_section_ids.mapped("visit_line_ids")
            if not visit_lines:
                raise ValidationError(_("The configured sections do not contain active standards yet."))
            if any(line.score is False or line.score <= 0 or line.score > 10 for line in visit_lines):
                raise ValidationError(_("You must add value only between 1 and 10."))
            record._validate_visit_sections()
            record.with_context(allow_submitted_visit_write=True).write(
                {
                    "state": "submitted",
                    "submitted_at": fields.Datetime.now(),
                }
            )
        return True

    def action_export_pdf(self):
        self.ensure_one()
        action = self.env.ref("ab_quality_assurance.action_report_ab_quality_assurance_visit").report_action(
            self, config=False
        )
        action["close_on_report_download"] = True
        return action

    def action_export_xlsx(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": "/ab_quality_assurance/visit/%s/xlsx" % self.id,
            "target": "self",
        }

    @api.model
    def _next_visit_name(self):
        sequence_value = self.env["ir.sequence"].next_by_code(VISIT_SEQUENCE_CODE)
        if sequence_value:
            return sequence_value
        return "QA-VISIT-%s" % uuid4().hex[:8].upper()

    @api.model
    def _prepare_create_or_write_vals(self, vals, for_create=False):
        prepared_vals = dict(vals or {})
        if for_create and prepared_vals.get("name", "New") == "New":
            prepared_vals["name"] = self._next_visit_name()
        if for_create and not prepared_vals.get("user_id"):
            prepared_vals["user_id"] = self.env.user.id
        if for_create and not prepared_vals.get("employee_id"):
            default_employee_id = self._default_employee_id()
            if default_employee_id:
                prepared_vals["employee_id"] = default_employee_id
        if for_create and prepared_vals.get("department_id") and "visit_section_ids" not in prepared_vals:
            sections = self._get_active_sections()
            prepared_vals["visit_section_ids"] = self._build_section_commands(sections)
        return prepared_vals

    @api.model
    def _get_active_sections(self):
        return self.env["ab_quality_assurance_section"].search(
            [("active", "=", True)],
            order="sequence, id",
        )

    @api.model
    def _build_line_commands(self, standards):
        return [
            fields.Command.create(
                {
                    "sequence": standard.sequence,
                    "standard_id": standard.id,
                    "score": False,
                }
            )
            for standard in standards
        ]

    @api.model
    def _build_section_commands(self, sections):
        commands = []
        for section in sections:
            standards = section.standard_ids.filtered("active").sorted(lambda record: (record.sequence, record.id))
            commands.append(
                fields.Command.create(
                    {
                        "sequence": section.sequence,
                        "section_id": section.id,
                        "visit_line_ids": self._build_line_commands(standards),
                    }
                )
            )
        return commands

    def _validate_visit_sections(self):
        for record in self:
            invalid_sections = record.visit_section_ids.filtered(
                lambda section: section.visit_line_ids.filtered(
                    lambda line: line.standard_id.section_id != section.section_id
                )
            )
            if invalid_sections:
                raise ValidationError(_("Each review block must only contain standards from its own section."))

    def _get_export_basename(self):
        self.ensure_one()
        name = (self.name or "quality_visit").replace("/", "_").replace("\\", "_").strip()
        return name or "quality_visit"

    def _generate_xlsx_workbook(self, workbook):
        self.ensure_one()

        sheet = workbook.add_worksheet(_("Quality Visit Report"))
        
        # Color Palette
        color_navy = "#16324f"
        color_white = "#ffffff"
        color_bg_light = "#f8f9fa"
        color_header_bg = "#eef4fb"
        color_success = "#28a745"
        color_danger = "#dc3545"
        color_warning = "#ffc107"

        # Formats
        title_format = workbook.add_format({
            "bold": True, "font_size": 18, "align": "center", "valign": "vcenter",
            "bg_color": color_navy, "font_color": color_white, "border": 1
        })
        
        label_format = workbook.add_format({
            "bold": True, "bg_color": color_header_bg, "font_color": color_navy,
            "border": 1, "font_size": 10
        })
        
        value_format = workbook.add_format({
            "border": 1, "font_size": 10, "valign": "vcenter"
        })
        
        header_format = workbook.add_format({
            "bold": True, "bg_color": color_navy, "font_color": color_white,
            "border": 1, "align": "center", "valign": "vcenter", "font_size": 11
        })
        
        section_format = workbook.add_format({
            "bold": True, "bg_color": "#d9e2f3", "font_color": color_navy,
            "border": 1, "valign": "vcenter", "font_size": 11
        })
        
        percent_format = workbook.add_format({
            "border": 1, "num_format": "0.00%", "align": "center", "valign": "vcenter"
        })
        
        number_format = workbook.add_format({
            "border": 1, "num_format": "0.00", "align": "center", "valign": "vcenter"
        })

        score_card_format = workbook.add_format({
            "bold": True, "font_size": 14, "align": "center", "valign": "vcenter",
            "bg_color": "#f1f4f7", "font_color": color_navy, "border": 2
        })

        # Header Title
        sheet.merge_range("A1:F2", _("QUALITY ASSURANCE VISIT REPORT"), title_format)

        # Summary Grid (2 columns)
        summary_left = [
            (_("Reference"), self.name or ""),
            (_("Branch"), self.department_id.name or ""),
            (_("Manager"), self.department_manager_id.name or ""),
            (_("Visit Date"), fields.Date.to_string(self.visit_date) or ""),
        ]
        
        summary_right = [
            (_("Visited By"), self.employee_id.name or ""),
            (_("Status"), dict(self._fields["state"].selection).get(self.state, "")),
            (_("Earned Total"), self.earned_total_score),
            (_("Max Total"), self.max_total_score),
        ]

        row = 3
        for i in range(len(summary_left)):
            # Left Column
            sheet.write(row, 0, summary_left[i][0], label_format)
            sheet.write(row, 1, summary_left[i][1], value_format)
            
            # Right Column
            sheet.write(row, 3, summary_right[i][0], label_format)
            sheet.write(row, 4, summary_right[i][1], number_format if isinstance(summary_right[i][1], (int, float)) else value_format)
            row += 1

        # Final Percentage Score Card
        sheet.merge_range(row, 0, row + 1, 1, _("TOTAL PERFORMANCE SCORE"), score_card_format)
        sheet.merge_range(row, 2, row + 1, 4, self.total_percentage / 100.0, workbook.add_format({
            "bold": True, "font_size": 20, "num_format": "0.00%", "align": "center", 
            "valign": "vcenter", "border": 2, "font_color": color_success if self.total_percentage >= 85 else (color_warning if self.total_percentage >= 70 else color_danger)
        }))
        
        row += 3
        
        # Table Headers
        headers = [
            _("Section"),
            _("Standard Title"),
            _("Max Score"),
            _("Earned Score"),
            _("Percentage"),
            _("Evidence"),
        ]
        for column, header in enumerate(headers):
            sheet.write(row, column, header, header_format)
        row += 1

        # Data Rows
        for section in self.visit_section_ids.sorted(lambda record: (record.sequence, record.id)):
            sheet.merge_range(row, 0, row, 5, section.name or "", section_format)
            row += 1
            for line in section.visit_line_ids.sorted(lambda record: (record.sequence, record.id)):
                sheet.write(row, 0, section.name or "", value_format)
                sheet.write(row, 1, line.title or "", value_format)
                sheet.write(row, 2, line.max_score or 0.0, number_format)
                sheet.write(row, 3, line.score or 0.0, number_format)
                
                # Percentage with color coding logic (simplified for xlsxwriter)
                p_val = line.percentage / 100.0
                sheet.write(row, 4, p_val, percent_format)
                
                sheet.write(row, 5, line.attachment_name or "-", value_format)
                row += 1

        # Column Widths
        sheet.set_column("A:A", 20)
        sheet.set_column("B:B", 45)
        sheet.set_column("C:E", 15)
        sheet.set_column("F:F", 25)
        
        # Freeze panes
        sheet.freeze_panes(row - (row - 8), 0)
