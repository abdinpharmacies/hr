from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    cr.execute("UPDATE ab_sales_cash_shift SET state = 'open' WHERE state = 'waiting'")
    shifts = env['ab_sales_cash_shift'].with_context(active_test=False).search([('state', '=', 'open')])
    shifts._recompute_recordset(['active_drawer_id'])
    if 'employee_id' in env['ab_sales_native_payment']._fields:
        cr.execute("""
            UPDATE ab_sales_native_payment AS payment
               SET employee_id = event.employee_id
              FROM ab_sales_cash_event AS event
             WHERE event.payment_id = payment.id
               AND payment.employee_id IS NULL
               AND event.employee_id IS NOT NULL
        """)
