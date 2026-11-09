"""Do not let Odoo 15 delete old payroll records on an HR-only upgrade."""


def migrate(cr, installed_version):
    cr.execute(
        """SELECT 1 FROM ir_model_data
           WHERE module = 'ab_hr' AND name = 'model_ab_hr_payroll'"""
    )
    if not cr.fetchone():
        return
    cr.execute(
        """SELECT state FROM ir_module_module
           WHERE name = 'ab_hr_payroll'"""
    )
    row = cr.fetchone()
    if not row or row[0] not in ('to install', 'to upgrade', 'installed'):
        raise RuntimeError(
            "Upgrade ab_hr and install ab_hr_payroll together; "
            "an HR-only upgrade would remove existing payroll data."
        )
