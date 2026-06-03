from odoo import api, fields, models


class PayrollExcelTypeConfig(models.Model):
    _name = "payroll.excel.type.config"
    _description = "Excel Sheet Type Config (J70)"
    _order = "sequence, id"

    sequence = fields.Integer(default=10)
    name = fields.Char(string="Name", required=True, translate=True)
    sheet_type = fields.Selection(
        selection="_selection_sheet_type",
        string="Sheet Type J70",
        required=True,
    )
    e72_zero = fields.Boolean(
        string="Zero E72 (IF I70=Q64 branch)",
        help="When enabled, E72 is set to 0 as in the Excel formula.",
    )
    g70_daily_allowance = fields.Float(
        string="G70 (VLOOKUP result)",
        digits=(16, 6),
        help="Daily allowance value per sheet type from the Excel lookup table.",
    )

    @api.model
    def _selection_sheet_type(self):
        return [
            ("daily_hours", "Daily Hours"),
            ("fixed_att", "Fixed Attendance"),
            ("monthly_hours", "Monthly Hours"),
            ("days_att", "Attendance Days"),
            ("fixed_salary", "Fixed Salary"),
        ]

    _uniq_sheet_type = models.Constraint(
        "UNIQUE(sheet_type)",
        "Sheet type must be unique.",
    )
