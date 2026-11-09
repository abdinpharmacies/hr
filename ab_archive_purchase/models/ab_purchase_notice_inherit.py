from odoo import api, fields, models, _


class AbPurchaseNoticeHeader(models.Model):
    _name = 'ab_purchase_notice_header'
    _inherit = 'ab_purchase_notice_header'

    att_file_ids = fields.Many2many(
        comodel_name='ab_archive',
        relation='ab_archive_ab_purchase_notice_header_rel',
        column1='notice_id',
        column2='archive_id',
        string='Notices')
