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
