from odoo import fields, models


class AbPromoProgramCompensation(models.Model):
    _inherit = 'ab_promo_program'

    compensation_company_id = fields.Many2one(
        'ab_product_company',
        string="Compensation Company",
        help="The manufacturing or supplier company responsible for compensating the pharmacy for this promotion.",
    )
    compensation_timing = fields.Selection(
        [
            ('advance', 'مسبق'),
            ('subsequent', 'لاحق'),
        ],
        string="Compensation Timing",
    )
    compensation_type = fields.Selection(
        [
            ('cash', 'Cash'),
            ('goods', 'Goods'),
        ],
        string="Compensation Type",
    )
    approval_email_attachment = fields.Binary(
        string="Approval Email Attachment",
        required=True,
        attachment=True,
        help="Upload the approval email from the compensation company. It must confirm activation of this promotion and show the approved promotion duration.",
    )
    approval_email_attachment_filename = fields.Char(
        string="Approval Email Filename",
    )
