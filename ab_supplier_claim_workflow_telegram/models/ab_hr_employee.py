from odoo import fields, models


class AbHrEmployee(models.Model):
    _inherit = 'ab_hr_employee'

    telegram_chat_id = fields.Char(
        string='Telegram Chat ID',
        groups='ab_hr.group_ab_hr_co,ab_hr.group_ab_hr_payroll_entry',
        copy=False,
    )
    telegram_user_id = fields.Char(
        string='Telegram User ID',
        groups='ab_hr.group_ab_hr_co,ab_hr.group_ab_hr_payroll_entry',
        copy=False,
    )
    telegram_username = fields.Char(
        string='Telegram Username',
        groups='ab_hr.group_ab_hr_co,ab_hr.group_ab_hr_payroll_entry',
        copy=False,
    )
    telegram_linked_at = fields.Datetime(
        string='Telegram Linked At',
        groups='ab_hr.group_ab_hr_co,ab_hr.group_ab_hr_payroll_entry',
        readonly=True,
        copy=False,
    )
