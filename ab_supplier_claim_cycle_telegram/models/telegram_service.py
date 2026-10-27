from odoo import api, models


TOKEN_PARAMETER = 'telegram.bot.token'
SUPPLIER_CONTEXT = 'supplier_claim_cycle_telegram'


class AbTelegramBot(models.AbstractModel):
    _inherit = 'ab_telegram_bot'

    @api.model
    def _get_bot_token(self):
        if self.env.context.get(SUPPLIER_CONTEXT):
            return (self.env['ir.config_parameter'].sudo().get_param(TOKEN_PARAMETER) or '').strip()
        return super()._get_bot_token()
