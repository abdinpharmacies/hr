from odoo import api, SUPERUSER_ID


# source is:
# https://www.cybrosys.com/blog/how-to-use-hooks-in-odoo-development

def test_pre_init_hook(cr):
    env = api.Environment(cr, SUPERUSER_ID, {})
    # ----------------------- EXAMPLE ------------------------
    env['ir.model.data'].search([
        ('model', 'like', '%test.hook%')
    ]).unlink()


def test_post_init_hook(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    # env.cr.execute("""
    #     alter table abdin_eplus_r_sales_trans_h drop constraint IF EXISTS  abdin_eplus_r_sales_trans_h_cust_id_fkey;
    #     alter table abdin_eplus_r_sales_trans_h drop constraint IF EXISTS  abdin_eplus_r_sales_trans_h_employee_fkey;
    #     alter table abdin_eplus_r_sales_trans_h drop constraint IF EXISTS  abdin_eplus_r_sales_trans_h_sto_id_fkey;
    # """)
    #
    # env.cr.commit()


def test_uninstall_hook(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})

    # env.cr.execute("""
    #     alter table abdin_eplus_r_sales_trans_h drop constraint IF EXISTS  abdin_eplus_r_sales_trans_h_cust_id_fkey;
    #     alter table abdin_eplus_r_sales_trans_h drop constraint IF EXISTS  abdin_eplus_r_sales_trans_h_employee_fkey;
    #     alter table abdin_eplus_r_sales_trans_h drop constraint IF EXISTS  abdin_eplus_r_sales_trans_h_sto_id_fkey;
    # """)
    #
    # env.cr.commit()
