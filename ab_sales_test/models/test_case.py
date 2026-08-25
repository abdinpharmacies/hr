from odoo import api, fields, models, _
from odoo.exceptions import UserError

from ..services.json_loader import SalesTestJSONError, SalesTestJSONLoader
from ..services.test_runner import SalesTestRunner


class AbSalesTestCase(models.Model):
    _name = "ab_sales_test.case"
    _description = "Sales Regression Test Case"
    _order = "scenario_code"
    _rec_name = "scenario_code"

    scenario_code = fields.Char(required=True, index=True, readonly=True)
    scenario_name = fields.Char(readonly=True)
    workflow_type = fields.Selection(
        [
            ("cash", "Cash"),
            ("contract", "Contract"),
            ("promo", "Promotion"),
            ("doctor", "Doctor"),
            ("mixed", "Mixed"),
            ("other", "Other"),
        ],
        default="other",
        readonly=True,
    )
    enabled = fields.Boolean(default=True)
    active = fields.Boolean(default=True)

    source_sth_id = fields.Integer(readonly=True)
    source_sto_id = fields.Integer(readonly=True)
    source_cust_id = fields.Integer(readonly=True)
    json_line_count = fields.Integer(readonly=True)

    expected_total_bill = fields.Float(readonly=True)
    expected_total_bill_after_disc = fields.Float(readonly=True)
    expected_total_bill_net = fields.Float(readonly=True)

    configuration_state = fields.Selection(
        [
            ("not_validated", "Not Validated"),
            ("ready", "Ready"),
            ("blocked", "Blocked"),
        ],
        default="not_validated",
        readonly=True,
    )
    last_status = fields.Selection(
        [
            ("not_run", "Not Run"),
            ("pass", "PASS"),
            ("fail", "FAIL"),
            ("blocked", "BLOCKED"),
        ],
        default="not_run",
        readonly=True,
    )
    last_run_date = fields.Datetime(readonly=True)
    last_result_summary = fields.Char(readonly=True)
    last_result_details = fields.Text(readonly=True)

    _uniq_scenario_code = models.Constraint(
        "UNIQUE(scenario_code)",
        "Scenario code must be unique.",
    )

    @api.model
    def action_sync_json(self):
        try:
            cases = SalesTestJSONLoader.sync_cases(self.env)
        except SalesTestJSONError as error:
            raise UserError(str(error)) from error
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Sales Regression Cases"),
                "message": _("Synchronized %s scenario(s) from JSON.") % len(cases),
                "type": "success",
                "sticky": False,
            },
        }

    def action_sync_json_button(self):
        return self.env["ab_sales_test.case"].action_sync_json()

    def action_run_case(self):
        for case in self:
            SalesTestRunner(self.env, case).run()
        return True

    def action_run_all_enabled(self):
        cases = self.env["ab_sales_test.case"].search([("enabled", "=", True), ("active", "=", True)])
        for case in cases:
            SalesTestRunner(self.env, case).run()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Sales Regression Cases"),
                "message": _("Executed %s enabled scenario(s).") % len(cases),
                "type": "info",
                "sticky": False,
            },
        }
