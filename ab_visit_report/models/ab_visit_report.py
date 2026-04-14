from odoo import _, fields, models, api
from odoo.exceptions import ValidationError


class AbVisitReport(models.Model):
    _name = "ab_visit_report_report"
    _description = "Visit Report"
    _order = "create_date desc"
    _inherit = ["abdin_telegram"]

    user_id = fields.Many2one(
        "res.users",
        string="User",
        default=lambda self: self.env.user,
        readonly=True,
    )

    client_ip = fields.Char(readonly=True)
    visit_date = fields.Date(string="Visit Date", default=fields.Date.today, readonly=True)
    region_id = fields.Many2one("ab_hr_region", string="Region")
    store_id = fields.Many2one("ab_store", string="Store")

    open_close_on_time = fields.Boolean(
        string="Branch complies with opening/closing times",
    )
    open_close_noncompliance_days = fields.Text(
        string="Days of non-compliance (if any)",
    )
    pharmacists_union_card = fields.Boolean(
        string="Pharmacists with union card on shifts",
    )
    pharmacists_union_card_notes = fields.Text(
        string="If not, mention shifts and actions",
    )
    reserve_drugs_compliance = fields.Selection(
        [('the_branch_complies_to_the_dispensing_rules', 'The branch complies to the dispensing rules'),
         ('there_are_violations_in_dispensing_operation',
          'There are violations in the dispensing operation')],
        string="Reserve drugs compliance review by branch manager",
    )
    sales_vs_last_year = fields.Text(
        string="Sales vs same month last year",
    )
    sales_vs_prev_month = fields.Text(
        string="Sales vs previous month", )

    delivery_orders_growth_last_year = fields.Text(
        string="Delivery orders growth vs same month last year", )

    delivery_orders_growth_prev_month = fields.Text(
        string="Delivery orders growth vs previous month",
    )
    offers_sales_last_year = fields.Text(
        string="Offers sales vs same month last year",
    )
    offers_sales_prev_month = fields.Text(
        string="Offers sales vs previous month",
    )
    avg_invoice_value_last_year = fields.Text(
        string="Average invoice value vs same month last year",
    )
    avg_invoice_value_prev_month = fields.Text(
        string="Average invoice value vs previous month",
    )
    manager_visit_details = fields.Text(
        string="Manager clinic visits (count and details)",
    )
    branch_maintenance_notes = fields.Text(
        string="Branch maintenance notes",
    )
    supplies_and_uniforms_notes = fields.Text(
        string="Monthly supplies and uniforms/boxes availability",
    )
    it_issues_notes = fields.Text(
        string="IT issues/maintenance notes",
    )
    transfer_request_regular = fields.Boolean(
        string="Transfer requests done regularly",
    )
    zero_drugs_3_months = fields.Text(
        string="Drug zero items (3 months sales)",
    )
    zero_cosmetics_3_months = fields.Text(
        string="Cosmetics zero items (3 months sales)",
    )
    monthly_inventory_commitment = fields.Boolean(
        string="Monthly inventory commitment",
    )
    opening_balances_notes = fields.Selection([('no_problem', 'There is no problem in the opening balances'),
                                               ('there_are_problems',
                                                'There are unrealistic opening balances and currently are under review')],
                                              string="Opening balances notes", )

    legal_documents_notes = fields.Selection([('eda_records', 'EDA records (drugs - toxins - formulations)'),
                                              ('required_seals', 'Required Seals (pharmacy seal - toxins - expired)'),
                                              ('license', 'License'), ('technical_drawing', 'Technical Drawing'),
                                              ('commercial_register', 'Commercial Register'),
                                              ('tax_card', 'Tax Card'), ('vat_certificate', 'Vat Certificate')],
                                             string="Legal documents availability")
    legal_document_notes = fields.Many2many(
        "ab_visit_report_legal_document_notes",
        string="Legal document notes",
    )

    returns_without_reason_notes = fields.Selection([('no_problem', 'Returns are in good order'),
                                                     ('there_are_problems',
                                                      'There are some unclear returns, and they are currently under review')],
                                                    string="Returns without clear reason")
    temporary_item_clearance_value = fields.Text(
        string="Temporary item clearance before visit (value if any)",
    )
    high_value_returns_match = fields.Text(
        string="High-value returns (500) match with system",
    )
    customer_data_commitment_percent = fields.Selection(
        [
            ("0", "0%"),
            ("50", "50%"),
            ("70", "70%"),
            ("100", "100%"),
        ],
        string="Customer data coding compliance",
    )
    customer_calls_response = fields.Boolean(string="Customer calls/WhatsApp response", )

    branches_response = fields.Boolean(string="Response to company branches", )

    transfer_refusals_notes = fields.Text(
        string="Branches refusing transfers (actions)",
    )
    new_codes_count_percent = fields.Text(
        string="New codes count and rate",
    )
    missing_job_ids = fields.Many2many(
        "ab_hr_job",
        string="Missing staff roles",
    )
    attendance_tampering_notes = fields.Text(
        string="Attendance manipulation notes",
    )
    cleanliness_floors_score = fields.Selection(
        [
            ("bad", "Bad"),
            ("good", "Good"),
            ("very_good", "Very Good"),
            ("excellent", "Excellent"),
        ],
        string="Floor cleanliness",
    )
    cleanliness_shelves_score = fields.Selection(
        [
            ("bad", "Bad"),
            ("good", "Good"),
            ("very_good", "Very Good"),
            ("excellent", "Excellent"),
        ],
        string="Shelves/display cleanliness and order",
    )
    stock_order_score = fields.Selection(
        [
            ("bad", "Bad"),
            ("good", "Good"),
            ("very_good", "Very Good"),
            ("excellent", "Excellent"),
        ],
        string="Stock orderliness",
    )
    bathroom_cleanliness_score = fields.Selection(
        [
            ("bad", "Bad"),
            ("good", "Good"),
            ("very_good", "Very Good"),
            ("excellent", "Excellent"),
        ],
        string="Bathroom cleanliness (if any)",
    )
    delivery_service_compliance = fields.Selection([('yes', 'The branch is compliant'),
                                                    ('no',
                                                     'The branch added extra services')])

    column_40 = fields.Text(string="Column 40")

    active = fields.Boolean(default=True)
    submitted = fields.Boolean(default=False)
    status = fields.Selection(
        [("entry", "Entry"), ("saved", "Saved"), ("submitted", "Submitted")],
        default="entry",
        required=True,
        index=True,
        readonly=True,
    )

    def btn_submit(self):
        required_fields = [
            "user_id",
            "region_id",
            "store_id",
            "open_close_on_time",
            "open_close_noncompliance_days",
            "pharmacists_union_card",
            "pharmacists_union_card_notes",
            "reserve_drugs_compliance",
            "sales_vs_last_year",
            "sales_vs_prev_month",
            "delivery_orders_growth_last_year",
            "delivery_orders_growth_prev_month",
            "offers_sales_last_year",
            "offers_sales_prev_month",
            "avg_invoice_value_last_year",
            "avg_invoice_value_prev_month",
            "manager_visit_details",
            "branch_maintenance_notes",
            "supplies_and_uniforms_notes",
            "it_issues_notes",
            "transfer_request_regular",
            "zero_drugs_3_months",
            "zero_cosmetics_3_months",
            "monthly_inventory_commitment",
            "opening_balances_notes",
            "legal_document_notes",
            "returns_without_reason_notes",
            "temporary_item_clearance_value",
            "high_value_returns_match",
            "customer_data_commitment_percent",
            "customer_calls_response",
            "branches_response",
            "transfer_refusals_notes",
            "new_codes_count_percent",
            "attendance_tampering_notes",
            "cleanliness_floors_score",
            "cleanliness_shelves_score",
            "stock_order_score",
            "bathroom_cleanliness_score",
            "delivery_service_compliance",
            "column_40",
        ]
        field_meta = self.fields_get(required_fields)
        fields_str = {key: meta.get("string", key) for key, meta in field_meta.items()}

        title = "Visit Report"
        before = f"""<b>##### {title} #####</b>\n\n"""

        conf_mo = self.env["ir.config_parameter"].sudo()
        base_url = conf_mo.get_param("web.base.url")
        action = None
        for rec in self:
            missing = []
            for field_name in required_fields:
                field = rec._fields[field_name]
                if field.type == "boolean":
                    continue
                if not rec[field_name]:
                    missing.append(fields_str.get(field_name, field_name))
            if missing:
                raise ValidationError(
                    _("Please fill in the following fields before posting: %s")
                    % ", ".join(missing)
                )

            client_ip = ""
            if hasattr(self.env.user, "_client_ip"):
                client_ip = self.env.user._client_ip()
            if client_ip and not rec.client_ip:
                rec.with_context(allow_submit_write=True).write({"client_ip": client_ip})

            subject = f"""<div>{fields_str['user_id']}: {rec.user_id.name}</div>
            <div>{fields_str['region_id']}: {rec.region_id.name or ''}</div>
            <div>{fields_str['store_id']}: {rec.store_id.name or ''}</div>
            """

            link = f"{base_url}/web#id={rec.id}&model={rec._name}&view_type=form"
            after = f"\n\nBy {self.env.user.name}\n<a href='{link}'>Goto Link -></a>"

            rec.send_by_bot(
                rec.get_chat_id("telegram_visit_report_group_chat_id"),
                msg=subject,
                before=before,
                after=after,
                attachment=None,
            )
            rec.with_context(allow_submit_write=True).write(
                {"submitted": True, "status": "submitted"}
            )

            title = _("Report submitted successfully.")
            status = "success"

            action = {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": title,
                    "type": status,
                    "sticky": False,
                    "next": {"type": "ir.actions.act_window_close"},
                },
            }
        return action

    def write(self, vals):
        if not self.env.context.get("allow_submit_write"):
            submitted_records = self.filtered("submitted")
            if submitted_records:
                is_admin = self.env.user.has_group("ab_visit_report.group_ab_visit_report_admin")
                if is_admin and set(vals.keys()) == {"submitted"} and not vals.get("submitted"):
                    return super().write(vals)
                raise ValidationError(_("You cannot edit a submitted report."))
            if "submitted" in vals:
                vals["status"] = "submitted" if vals.get("submitted") else "saved"
            elif "status" not in vals:
                vals["status"] = "saved"
        return super().write(vals)

    def btn_reopen(self):
        if not self.env.user.has_group("ab_visit_report.group_ab_visit_report_admin"):
            raise ValidationError(_("Only admins can reopen submitted reports."))
        self.with_context(allow_submit_write=True).write(
            {"submitted": False, "status": "saved"}
        )
        return True

    @api.depends("store_id", "region_id")
    def _compute_display_name(self):
        for rec in self:
            display_name = f"Visit - {rec.store_id.name} - {rec.visit_date}"
            rec.display_name = display_name or _("Visit Report")

    @api.model_create_multi
    def create(self, vals_list):
        if isinstance(vals_list, dict):
            vals_list = [vals_list]
        client_ip = ""
        if hasattr(self.env.user, "_client_ip"):
            client_ip = self.env.user._client_ip()
        if client_ip:
            for vals in vals_list:
                vals.setdefault("client_ip", client_ip)
        for vals in vals_list:
            if vals.get("submitted"):
                vals.setdefault("status", "submitted")
            else:
                vals.setdefault("status", "saved")
        return super().create(vals_list)
