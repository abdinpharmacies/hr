from odoo import fields, models


class AbPromoProgramCompensation(models.Model):
    _inherit = 'ab_promo_program'

    promotion_ownership = fields.Selection(
        [
            ("company_promotion", "Company Promotion"),
            ("abdin_promotion", "Abdin Promotion"),
        ],
        string="Promotion Ownership",
    )
    compensation_company_id = fields.Many2one(
        'ab_product_company',
        string="Compensation Company",
        help="The manufacturing or supplier company responsible for compensating the pharmacy for this promotion.",
    )
    compensation_timing = fields.Selection(
        [
            ('before', 'Before'),
            ('later', 'Later'),
        ],
        string="Compensation Way",
    )
    compensation_type = fields.Selection(
        [
            ('cash', 'Cash'),
            ('products', 'Products'),
        ],
        string="Compensation Type",
    )
    approval_email_attachment = fields.Binary(
        string="Approval Email Attachment",
        attachment=True,
        help="Upload the approval email from the compensation company. It must confirm activation of this promotion and show the approved promotion duration.",
    )
    approval_email_attachment_filename = fields.Char(
        string="Approval Email Filename",
    )


class AbSalesHeader(models.Model):
    _name = 'ab_sales_header'
    _inherit = 'ab_sales_header'

    # Totals (untaxed math)
    currency_id = fields.Many2one('res.currency', default=lambda s: s.env.company.currency_id.id, required=True)
    amount_untaxed = fields.Monetary(store=True)
    amount_tax = fields.Monetary(store=True)
    amount_total = fields.Monetary(store=True)

    # Attach programs *manually or via your own logic* (no validation layer here)
    applied_program_ids = fields.Many2many(
        comodel_name='ab_promo_program',
        relation='ab_sales_header_promo_program_validated_rel',
        column1='sales_header_id',
        column2='validated_promo_id',
        string="Applied Programs",
        copy=False,
    )

    promo_manual_override = fields.Boolean(default=False, copy=False)

    # Results
    promo_discount_amount = fields.Monetary(
        string="Promotion Discount",
        store=True
    )
    amount_total_after_promo = fields.Monetary(
        string="Total After Promotion",
        store=True
    )
