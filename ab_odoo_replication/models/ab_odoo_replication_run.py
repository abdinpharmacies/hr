from odoo import api, fields, models
from odoo.tools.translate import _
from odoo.exceptions import UserError
from odoo.tools import config


class OdooReplicationRun(models.AbstractModel):
    _name = 'ab_odoo_replication'
    _inherit = 'ab_odoo_replication'

    def run_replication_schema(self):
        # Group (1)
        self.replicate_model('res.partner')
        self.replicate_model('res.users', extra_fields={'groups_id': 'many2many'})
        self.add_res_company_rel_for_all_users()
        # Group (2)
        self.replicate_model('ab_costcenter')
        self.replicate_model('ab_store')
        self.replicate_model('ab_hr_region')
        self.replicate_model('ab_hr_job')
        self.replicate_model('ab_hr_department')
        self.replicate_model('ab_hr_employee')
        self.replicate_model('ab_hr_job_occupied')

        self.replicate_model('ab_customer')

        # Group (3)
        self.replicate_model('ab_product_company')
        self.replicate_model('ab_product_origin')
        self.replicate_model('ab_product_group')
        self.replicate_model('ab_usage_causes')
        self.replicate_model('ab_usage_manner')

        # Group (4)
        self.replicate_model('ab_uom_type')
        self.replicate_model('ab_uom')

        # Group (5)
        self.replicate_model('ab_product_card')
        self.replicate_model('ab_product')
        self.replicate_model('ab_product_barcode', limit=10000,
                             extra_fields={'product_ids': 'many2many'})

        # self.replicate_model('ab_product_source', extra_domain=[('no_delete', '=', True)])
        # integer and store_id.id to not use odoo search_name method
        # repl_db = int(config.get('repl_db', 0))
        # if repl_db:
        #     self.replicate_model('ab_inventory_header', extra_domain=[('store_id.id', '=', repl_db)])
        #     self.replicate_model('ab_inventory', extra_domain=[('store_id.id', '=', repl_db)])
        #     self.replicate_model('ab_inventory_action')

    # Group (6)
    # self.replicate_model('ab_announcement', commit=True, limit=100, extra_fields={'attachment': 'binary'})
