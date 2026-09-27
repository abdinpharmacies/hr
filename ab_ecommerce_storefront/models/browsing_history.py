from datetime import timedelta

from odoo import fields, models


AB_BROWSING_HISTORY_LIMIT = 30


class AbEcommerceBrowsingHistory(models.Model):
    _name = "ab.ecommerce.browsing.history"
    _description = "Storefront Browsing History"
    _order = "last_viewed_at desc, id desc"

    partner_id = fields.Many2one(
        "res.partner",
        required=True,
        index=True,
        ondelete="cascade",
    )
    website_id = fields.Many2one(
        "website",
        required=True,
        index=True,
        ondelete="cascade",
    )
    product_template_id = fields.Many2one(
        "product.template",
        required=True,
        index=True,
        ondelete="cascade",
    )
    last_viewed_at = fields.Datetime(
        required=True,
        default=fields.Datetime.now,
        index=True,
    )

    _uniq_partner_website_product = models.Constraint(
        "UNIQUE(partner_id, website_id, product_template_id)",
        "This product is already in the customer's browsing history.",
    )

    def _ab_history_partner(self, user):
        partner = user.partner_id
        return partner.commercial_partner_id or partner

    def _ab_record_view(self, partner, website, product):
        self = self.sudo()
        if not partner or not website or not product:
            return False
        values = {
            "partner_id": partner.id,
            "website_id": website.id,
            "product_template_id": product.id,
        }
        history = self.search([
            ("partner_id", "=", partner.id),
            ("website_id", "=", website.id),
            ("product_template_id", "=", product.id),
        ], limit=1)
        if history:
            history.write({"last_viewed_at": fields.Datetime.now()})
        else:
            values["last_viewed_at"] = fields.Datetime.now()
            history = self.create(values)
        self._ab_trim_partner_history(partner, website)
        return history

    def _ab_partner_product_ids(self, partner, website, limit=AB_BROWSING_HISTORY_LIMIT):
        records = self.sudo().search([
            ("partner_id", "=", partner.id),
            ("website_id", "=", website.id),
        ], order="last_viewed_at desc, id desc", limit=limit)
        return records.product_template_id.ids

    def _ab_merge_product_ids(self, partner, website, product_ids):
        self = self.sudo()
        incoming_ids = self._ab_normalize_product_ids(product_ids)
        server_ids = self._ab_partner_product_ids(partner, website, limit=AB_BROWSING_HISTORY_LIMIT)
        merged_ids = [*incoming_ids]
        merged_ids.extend(product_id for product_id in server_ids if product_id not in set(merged_ids))
        merged_ids = merged_ids[:AB_BROWSING_HISTORY_LIMIT]

        now = fields.Datetime.now()
        for index, product_id in enumerate(merged_ids):
            viewed_at = now - timedelta(seconds=index)
            history = self.search([
                ("partner_id", "=", partner.id),
                ("website_id", "=", website.id),
                ("product_template_id", "=", product_id),
            ], limit=1)
            if history:
                history.write({"last_viewed_at": viewed_at})
            else:
                self.create({
                    "partner_id": partner.id,
                    "website_id": website.id,
                    "product_template_id": product_id,
                    "last_viewed_at": viewed_at,
                })
        self._ab_trim_partner_history(partner, website)
        return merged_ids

    def _ab_clear_partner_history(self, partner, website):
        self.sudo().search([
            ("partner_id", "=", partner.id),
            ("website_id", "=", website.id),
        ]).unlink()

    def _ab_remove_partner_product(self, partner, website, product):
        if not partner or not website or not product:
            return False
        records = self.sudo().search([
            ("partner_id", "=", partner.id),
            ("website_id", "=", website.id),
            ("product_template_id", "=", product.id),
        ])
        removed = bool(records)
        records.unlink()
        return removed

    def _ab_trim_partner_history(self, partner, website):
        extra_records = self.sudo().search([
            ("partner_id", "=", partner.id),
            ("website_id", "=", website.id),
        ], order="last_viewed_at desc, id desc", offset=AB_BROWSING_HISTORY_LIMIT)
        if extra_records:
            extra_records.unlink()

    @staticmethod
    def _ab_normalize_product_ids(product_ids):
        normalized = []
        seen = set()
        for product_id in product_ids or []:
            try:
                product_id = int(product_id)
            except (TypeError, ValueError):
                continue
            if product_id <= 0 or product_id in seen:
                continue
            seen.add(product_id)
            normalized.append(product_id)
            if len(normalized) >= AB_BROWSING_HISTORY_LIMIT:
                break
        return normalized
