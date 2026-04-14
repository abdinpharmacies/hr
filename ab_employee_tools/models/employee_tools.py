from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class EmployeeTools(models.Model):
    _name = "ab_employee_tools_employee_tools"
    _description = "Employee Tools"

    user_id = fields.Many2one(
        "res.users",
        string="User",
        default=lambda self: self.env.user,
        readonly=True,
        required=True,
    )
    employee_id = fields.Many2one(
        "ab_hr_employee",
        string="Employee",
        required=True,
    )
    employee_code = fields.Char(
        related="employee_id.costcenter_id.code",
        string="Employee Code",
        store=True,
    )
    department_id = fields.Many2one(
        related="employee_id.department_id",
        string="Department",
        store=True,
    )
    job_id = fields.Many2one(
        related="employee_id.job_id",
        string="Job Title",
        store=True,
    )
    status = fields.Selection(
        [
            ("delivered", "Delivered"),
            ("not_delivered", "Not Delivered"),
        ],
        default="not_delivered",
        required=True,
    )
    delivery_date = fields.Date(string="Delivery Date")
    receipt_date_from_company = fields.Date(string="Receipt Date From Company")
    line_ids = fields.One2many(
        "ab_employee_tools_employee_tools_line",
        "employee_tools_id",
        string="Tools",
    )
    termination_date = fields.Date(
        string="Termination Date",
        compute="_compute_termination_date",
        store=True,
        compute_sudo=True,
    )
    termination_notified = fields.Boolean(default=False)
    notes = fields.Text()

    @api.depends("employee_id", "delivery_date")
    def _compute_display_name(self):
        for rec in self:
            employee_name = rec.employee_id.name or ""
            delivery_date = rec.delivery_date or ""
            display_name = f"{employee_name} - {delivery_date}".strip(" -")
            rec.display_name = display_name or _("Employee Tools")

    @api.depends("employee_id", "employee_id.termination_date")
    def _compute_termination_date(self):
        for rec in self:
            if rec.employee_id and rec.employee_id.termination_date:
                rec.termination_date = rec.employee_id.termination_date

                # rec._notify_termination_if_needed()
            else:
                rec.termination_date = False

    def action_submit(self):
        self._check_delivery_allowed()
        move_model = self.env["ab_employee_tools.inventory_move"]
        for rec in self:
            for line in rec.line_ids:
                qty = line.no_of_units or 0
                if qty:
                    move_model.create(
                        {
                            "movement_type": "issue",
                            "type_id": line.type_id.id,
                            "quantity": qty,
                        }
                    )
            rec.status = "delivered"

    def _check_delivery_allowed(self):
        terminated = self.filtered(lambda r: r.termination_date)
        if terminated:
            raise ValidationError(
                _("Cannot deliver tools to an employee with a termination date set.")
            )


# class AbHrEmployee(models.Model):
#     _name = 'ab_hr_employee'
#     _inherit = 'ab_hr_employee'
#
#     notify_termination = fields.Boolean(compute='_compute_notify_termination')
#
#     @api.depends('termination_date')
#     def _compute_notify_termination(self):
#         for rec in self:
#             if rec.termination_date:
#                 Tools = self.env['ab_employee_tools_employee_tools'].sudo()
#

class AbHrJobOccupied(models.Model):
    _name = 'ab_hr_job_occupied'
    _inherit = ['ab_hr_job_occupied', 'abdin_telegram']

    def simulate_termination(self):
        if self.termination_date:
            self.termination_date = False
        else:
            self.termination_date = fields.Date.today()

    def write(self, values):
        res = super().write(values)
        if 'termination_date' in values and values['termination_date']:
            Tools = self.env['ab_employee_tools_employee_tools'].sudo()

            for rec in self:
                recs = Tools.search([('employee_id', 'in', self.employee_id.ids)])
                if recs:
                    self._notify_termination_if_needed(tools=', '.join(recs.mapped('line_ids.display_name')))
        return res

    @api.model
    def _notify_termination_if_needed(self, tools=''):
        before = "<b>##### Employee Termination #####</b>\n\n"
        msg = (
            f"<div>Employee: {self.employee_id.name}</div>"
            f"<div>Termination Date: {self.termination_date}</div>"
            f"<div>Employee Tools: {tools}</div>"
        )
        after = f"\n\nBy {self.env.user.name}"
        self.send_by_bot(
            self.get_chat_id("telegram_employee_tools_group_chat_id"),
            msg=msg,
            before=before,
            after=after,
            attachment=None,
        )
