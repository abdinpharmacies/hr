from datetime import date, datetime, timedelta
import pytz

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class EtaConfig(models.Model):
    _name = 'ab_tax_eta_archive_config'
    _description = 'ETA Archive Configuration'

    name = fields.Char(required=True, default='ETA Archive')
    active = fields.Boolean(default=True)
    environment = fields.Selection([('production', 'Production'), ('preproduction', 'Preproduction')],
                                   required=True, default='production')
    start_date = fields.Date(required=True, default='2026-10-01')
    telegram_start_date = fields.Date(
        default=lambda self: datetime.now(pytz.timezone('Africa/Cairo')).date() - timedelta(days=4))
    invoice_client_id = fields.Char(groups='ab_tax_eta_archive.group_eta_manager')
    invoice_client_secret = fields.Char(groups='ab_tax_eta_archive.group_eta_manager')
    receipt_client_id = fields.Char(groups='ab_tax_eta_archive.group_eta_manager')
    receipt_client_secret = fields.Char(groups='ab_tax_eta_archive.group_eta_manager')
    pos_serial = fields.Char(groups='ab_tax_eta_archive.group_eta_manager')
    pos_os_version = fields.Char(groups='ab_tax_eta_archive.group_eta_manager')
    pos_model_framework = fields.Char(groups='ab_tax_eta_archive.group_eta_manager')
    pos_preshared_key = fields.Char(groups='ab_tax_eta_archive.group_eta_manager')
    telegram_chat_id = fields.Char(groups='ab_tax_eta_archive.group_eta_manager')
    telegram_bot_token = fields.Char(groups='ab_tax_eta_archive.group_eta_manager')

    @api.constrains('start_date')
    def _check_start_date(self):
        for config in self:
            if config.start_date and config.start_date > date.today():
                raise ValidationError(_('The ETA start date cannot be in the future.'))

    def _base_urls(self):
        self.ensure_one()
        prefix = 'preprod.' if self.environment == 'preproduction' else ''
        return (f'https://id.{prefix}eta.gov.eg',
                f'https://api.{prefix}invoicing.eta.gov.eg')
