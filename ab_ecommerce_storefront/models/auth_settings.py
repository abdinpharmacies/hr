from odoo import fields, models


class AuthSettings(models.TransientModel):
    _inherit = "res.config.settings"

    ab_auth_telegram_enabled = fields.Boolean(string="Enable Telegram authentication", config_parameter="ab_storefront_auth.telegram_enabled")
    ab_auth_bot_username = fields.Char(string="Telegram bot username", default="Abdin_Pharmacy_Bot", config_parameter="ab_storefront_auth.telegram_bot_username")
    ab_auth_webhook_url = fields.Char(string="Telegram webhook URL", config_parameter="ab_storefront_auth.telegram_webhook_url")
    ab_auth_base_url = fields.Char(string="Public authentication URL", config_parameter="ab_storefront_auth.base_url")
    ab_auth_otp_expiration = fields.Integer(string="OTP lifetime in seconds", default=300, config_parameter="ab_storefront_auth.otp_expiration")
    ab_auth_token_expiration = fields.Integer(string="Link lifetime in seconds", default=900, config_parameter="ab_storefront_auth.token_expiration")
    ab_auth_otp_attempts = fields.Integer(string="Maximum OTP attempts", default=5, config_parameter="ab_storefront_auth.otp_max_attempts")
    ab_auth_resend_cooldown = fields.Integer(string="Resend cooldown in seconds", default=60, config_parameter="ab_storefront_auth.resend_cooldown")
    ab_auth_rate_limit = fields.Integer(string="Requests per identity per hour", default=5, config_parameter="ab_storefront_auth.rate_limit")
    ab_auth_ip_rate_limit = fields.Integer(string="Requests per IP per hour", default=20, config_parameter="ab_storefront_auth.ip_rate_limit")
