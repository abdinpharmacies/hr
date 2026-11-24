from odoo import fields, models


class StorefrontOfferOverview(models.Model):
    _name = "ab_storefront_offer_overview"
    _description = "Storefront Offer Overview"
    _auto = False
    _order = "date_from desc nulls last, id"

    name = fields.Char(translate=True, readonly=True)
    website_id = fields.Many2one("website", readonly=True)
    company_id = fields.Many2one("res.company", readonly=True)
    date_from = fields.Date(readonly=True)
    date_to = fields.Date(readonly=True)
    source = fields.Selection([
        ("manual", "Storefront Offer"), ("sheet", "Imported Offer"), ("review", "Offer Draft"),
    ], readonly=True)
    state = fields.Selection([
        ("enabled", "Enabled"), ("archived", "Archived"), ("draft", "Draft"),
        ("skipped", "Set Aside"), ("applied", "Applied"),
    ], readonly=True)

    @property
    def _table_query(self):
        return """
            SELECT id::bigint * 3 AS id, name, website_id, company_id, date_from, date_to,
                   'manual' AS source, CASE WHEN active THEN 'enabled' ELSE 'archived' END AS state
              FROM ab_storefront_offer
             UNION ALL
            SELECT id::bigint * 3 + 1, name, website_id, company_id, date_from, date_to,
                   'sheet', CASE WHEN active THEN 'enabled' ELSE 'archived' END
              FROM loyalty_program p
             WHERE ab_sheet_key IS NOT NULL AND ab_storefront_offer_id IS NULL
               AND NOT starts_with(ab_sheet_key, 'storefront-')
               AND (p.active OR NOT EXISTS (
                   SELECT 1 FROM ab_storefront_offer_draft d
                    WHERE d.program_id = p.id AND d.stock_review AND d.state != 'applied'
               ))
             UNION ALL
            SELECT id::bigint * 3 + 2, jsonb_build_object('en_US', name), website_id,
                   company_id, date_from, date_to, 'review', state
              FROM ab_storefront_offer_draft
             WHERE state != 'applied' OR program_id IS NULL
        """

    def action_open_offer(self):
        self.ensure_one()
        self.check_access("read")
        model = {"manual": "ab_storefront_offer", "sheet": "loyalty.program",
                 "review": "ab_storefront_offer_draft"}[self.source]
        record = self.env[model].browse(self.id // 3)
        if not record.has_access("read"):
            record = self
        return {"type": "ir.actions.act_window", "res_model": record._name,
                "view_mode": "form", "res_id": record.id, "target": "current",
                "name": self.name}
