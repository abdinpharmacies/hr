from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class PayrollExcelSheet(models.Model):
    _name = "payroll.excel.sheet"
    _description = "Payroll Sheet (Excel Mirror)"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_from desc, employee_id"

    SHEET_TYPE_SELECTION = [
        ("daily_hours", "Daily Hours"),
        ("fixed_att", "Fixed Attendance"),
        ("monthly_hours", "Monthly Hours"),
        ("days_att", "Attendance Days"),
        ("fixed_salary", "Fixed Salary"),
    ]

    name = fields.Char(string="Name", tracking=True)
    employee_id = fields.Many2one(
        "ab_hr_employee",
        string="Employee",
        required=True,
        tracking=True,
        ondelete="restrict",
    )
    date_from = fields.Date(string="From", required=True, tracking=True)
    date_to = fields.Date(string="To", required=True, tracking=True)

    sheet_type = fields.Selection(
        SHEET_TYPE_SELECTION,
        string="Sheet Type (J70)",
        required=True,
        tracking=True,
    )

    e2_basic = fields.Float(string="E2 (Basic Agreement)", digits=(16, 6), tracking=True)
    f2_allowance = fields.Float(string="F2 (Allowances)", digits=(16, 6), tracking=True)
    h2_hours = fields.Float(string="H2 (Agreed Hours/Month)", digits=(16, 6), tracking=True)
    i53_factor = fields.Float(
        string="I53 (Days/Month Factor)",
        digits=(16, 6),
        default=1.0,
        help="In Excel appears as a divisor for days or month factor. Adjust to match the sheet.",
        tracking=True,
    )

    e70 = fields.Float(string="E70 Daily Hour Rate (Basic)", compute="_compute_core_block", store=True, digits=(16, 6))
    e72 = fields.Float(
        string="E72 Daily Hour Rate on Basic Allowances",
        compute="_compute_core_block",
        store=True,
        digits=(16, 6),
    )
    e74 = fields.Float(string="E74 Total Salary", compute="_compute_core_block", store=True, digits=(16, 6))
    f70 = fields.Float(string="F70 Daily Value on Basic", compute="_compute_core_block", store=True, digits=(16, 6))
    g70 = fields.Float(string="G70 Daily Value on Allowances", compute="_compute_core_block", store=True, digits=(16, 6))
    h70 = fields.Float(string="H70 Agreement Salary", compute="_compute_core_block", store=True, digits=(16, 6))

    adjustment_line_ids = fields.One2many(
        "payroll.excel.sheet.adjustment",
        "sheet_id",
        string="Adjustments A80:A89 (SUM in H70)",
    )
    adjustment_sum = fields.Float(
        string="Adjustment Total",
        compute="_compute_adjustment_sum",
        store=True,
        digits=(16, 6),
    )

    earning_line_ids = fields.One2many(
        "payroll.excel.sheet.component",
        "sheet_id",
        string="Earning Items (E44:E68)",
        domain=[("side", "=", "earning")],
    )
    deduction_line_ids = fields.One2many(
        "payroll.excel.sheet.component",
        "sheet_id",
        string="Deduction Items (G44:G68)",
        domain=[("side", "=", "deduction")],
    )

    fingerprint_ids = fields.One2many(
        "payroll.excel.sheet.fingerprint",
        "sheet_id",
        string="Fingerprints (Attendance Area)",
    )

    fingerprint_overlap_count = fields.Integer(
        string="Overlap/Duplicate Alerts",
        compute="_compute_fingerprint_flags",
    )

    state = fields.Selection(
        [("draft", "Draft"), ("confirmed", "Confirmed"), ("locked", "Locked")],
        default="draft",
        tracking=True,
    )

    notes = fields.Html(string="Notes")

    @api.constrains("date_from", "date_to")
    def _check_dates(self):
        for rec in self:
            if rec.date_from and rec.date_to and rec.date_from > rec.date_to:
                raise ValidationError(_("Start date must be before or equal to end date."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name"):
                emp = self.env["hr.employee"].browse(vals.get("employee_id"))
                vals["name"] = f"{emp.name or ''} — {vals.get('date_from', '')}"
        return super().create(vals_list)

    @api.depends("adjustment_line_ids.amount")
    def _compute_adjustment_sum(self):
        for rec in self:
            rec.adjustment_sum = sum(rec.adjustment_line_ids.mapped("amount"))

    @api.depends(
        "e2_basic",
        "f2_allowance",
        "h2_hours",
        "i53_factor",
        "sheet_type",
        "adjustment_sum",
    )
    def _compute_core_block(self):
        TypeConfig = self.env["payroll.excel.type.config"]
        for rec in self:
            i53 = rec.i53_factor or 1.0
            cfg = TypeConfig.search([("sheet_type", "=", rec.sheet_type)], limit=1)
            rec.e70 = (rec.e2_basic or 0.0) / i53
            if cfg and cfg.e72_zero:
                rec.e72 = 0.0
            else:
                rec.e72 = (rec.f2_allowance or 0.0) / i53
            rec.e74 = rec.e70 + rec.e72
            rec.f70 = (rec.h2_hours or 0.0) * rec.e70
            rec.g70 = cfg.g70_daily_allowance if cfg else 0.0
            rec.h70 = (rec.f70 + rec.g70) * i53 + (rec.adjustment_sum or 0.0)

    @api.depends("fingerprint_ids", "fingerprint_ids.has_issue")
    def _compute_fingerprint_flags(self):
        for rec in self:
            rec.fingerprint_overlap_count = len(rec.fingerprint_ids.filtered(lambda r: r.has_issue))

    def action_confirm(self):
        self.write({"state": "confirmed"})

    def action_draft(self):
        self.write({"state": "draft"})

    def action_lock(self):
        self.write({"state": "locked"})

    def action_seed_lines(self):
        Component = self.env["payroll.excel.sheet.component"]
        for sheet in self:
            if sheet.earning_line_ids or sheet.deduction_line_ids:
                continue
            for i in range(44, 69):
                Component.create(
                    {
                        "sheet_id": sheet.id,
                        "excel_row": i,
                        "side": "earning",
                        "name": _("Earning Item E%s") % i,
                    }
                )
                Component.create(
                    {
                        "sheet_id": sheet.id,
                        "excel_row": i,
                        "side": "deduction",
                        "name": _("Deduction Item G%s") % i,
                    }
                )
        return True


class PayrollExcelSheetAdjustment(models.Model):
    _name = "payroll.excel.sheet.adjustment"
    _description = "Sheet Adjustment (A80:A89)"

    sheet_id = fields.Many2one("payroll.excel.sheet", required=True, ondelete="cascade")
    sequence = fields.Integer(default=10)
    name = fields.Char(string="Item", required=True)
    amount = fields.Float(string="Amount", digits=(16, 6))


class PayrollExcelSheetComponent(models.Model):
    _name = "payroll.excel.sheet.component"
    _description = "Payroll Sheet Item"
    _order = "excel_row, side"

    sheet_id = fields.Many2one("payroll.excel.sheet", required=True, ondelete="cascade")
    excel_row = fields.Integer(string="Excel Row", required=True)
    side = fields.Selection(
        [("earning", "Earning"), ("deduction", "Deduction")],
        required=True,
    )
    name = fields.Char(string="Item Name", required=True)
    amount = fields.Float(string="Value", digits=(16, 6), default=0.0)
    source = fields.Selection(
        [
            ("manual", "Manual / Fixed Periodic"),
            ("computed", "Computed (linked to engine)"),
        ],
        default="manual",
    )
    excel_formula_trace = fields.Text(string="Excel Formula Trace (Reference)")


class PayrollExcelSheetFingerprint(models.Model):
    _name = "payroll.excel.sheet.fingerprint"
    _description = "Payroll Sheet Fingerprint"
    _order = "day_date, id"

    sheet_id = fields.Many2one("payroll.excel.sheet", required=True, ondelete="cascade")
    day_date = fields.Date(string="Day", required=True)
    check_in = fields.Datetime(string="Check In (M)")
    check_out = fields.Datetime(string="Check Out (N)")
    note = fields.Char(string="Note")

    has_issue = fields.Boolean(
        string="Overlap/Duplicate Issue",
        compute="_compute_issues",
        store=True,
    )
    issue_detail = fields.Char(string="Details", compute="_compute_issues", store=True)

    @api.constrains("sheet_id", "day_date")
    def _check_unique_day(self):
        for rec in self:
            dup = self.search_count(
                [
                    ("sheet_id", "=", rec.sheet_id.id),
                    ("day_date", "=", rec.day_date),
                    ("id", "!=", rec.id),
                ]
            )
            if dup:
                raise ValidationError(_("Only one fingerprint record per day per sheet is allowed."))

    @api.depends("check_in", "check_out", "day_date")
    def _compute_issues(self):
        for rec in self:
            rec.has_issue = False
            rec.issue_detail = False
            if rec.check_in and rec.check_out and rec.check_out < rec.check_in:
                rec.has_issue = True
                rec.issue_detail = _("Check out before check in")
            elif rec.check_in and not rec.check_out:
                rec.has_issue = True
                rec.issue_detail = _("Missing check out")
            elif rec.check_out and not rec.check_in:
                rec.has_issue = True
                rec.issue_detail = _("Missing check in")
