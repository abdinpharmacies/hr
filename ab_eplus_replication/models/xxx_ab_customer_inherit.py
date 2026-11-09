# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.addons.queue_job.exception import RetryableJobError

PARAM_STR = "?"
sql_replicate_cust = f"""                                                
        INSERT INTO Replication_Trans (
            trans_typ_1,
            trans_typ_2,
            store_id,
            general_id,
            general_name,
            trans_qry,
            sec_insert_uid,
            form_nm,
            ePlusVersion
        )
        VALUES( 
            7,
            2,
            0,
            {PARAM_STR},
            'Edit Customer',
            NULL,
            1,
            'Add_edit_customer_ar',
            NULL
        )

"""

sql_update_cust = f"""
            UPDATE c
                SET c.cust_mobile         = {PARAM_STR},
                   c.cust_tel        = {PARAM_STR},
                   c.cust_name_ar        = {PARAM_STR},
                   c.cust_address        = {PARAM_STR},
                   c.cust_def_sell_store = {PARAM_STR},
                   c.cust_active         = 1,
                   c.cust_code           = {PARAM_STR},
                   c.cust_payment        = 4,
                   c.cust_rec_name       = 1,
                   c.sec_update_date     = getdate()
                FROM dbo.Customer AS c
                WHERE c.cust_id = {PARAM_STR};
        """


##########################################################
class Customer(models.Model):
    _name = 'ab_customer'
    _inherit = ['ab_customer', 'ab_eplus_connect']

    def write(self, values):
        res = super().write(values)
        for rec in self:
            ctx = self.env.context
            if ctx.get('eplus_replication'):
                continue

            # rec.action_update_customer_insert_replication_on_main()
            # return res
            if {'name', 'address', 'mobile_phone', 'work_phone'} & set(values):
                # job 1 for main server update and replication
                id_key = f"{self._name}_{rec.id}_1"
                curr_job = (
                    rec.delayable(identity_key=id_key)
                    .action_update_customer_insert_replication_on_main()
                )
                curr_job.delay()

                # job 2 for branch server update only
                if rec.default_store_id.ip1:
                    id_key = f"{self._name}_{rec.id}_2"
                    curr_job = (
                        rec.delayable(identity_key=id_key)
                        .action_update_customer_on_branch()
                    )
                    curr_job.delay()

        return res

    @api.model_create_multi
    def create(self, vals_list):
        records = self.browse()
        for values in vals_list:
            records |= self._create_one_ab_eplus_replication_customer(values)
        return records

    def _create_one_ab_eplus_replication_customer(self, values):
        res = super().create(values)

        return res

    def action_update_customer_on_branch(self):
        try:
            default_store_ip = self.default_store_id.ip1
            # default_store_ip = '192.168.1.152'
            if default_store_ip:
                with self.connect_eplus(param_str=PARAM_STR, server=default_store_ip, charset='CP1256',
                                        propagate_error=True) as conn:
                    with conn.cursor() as cr:
                        cr.execute(
                            sql_update_cust,
                            (self.mobile_phone,
                             self.work_phone or self.mobile_phone,
                             self.name,
                             self.address,
                             self.default_store_id.eplus_serial,
                             self.code,
                             self.eplus_serial)
                        )
        except Exception as e:
            raise RetryableJobError(str(e), seconds=300)

    def action_update_customer_insert_replication_on_main(self):
        try:
            with self.connect_eplus(param_str=PARAM_STR, charset='UTF-8', propagate_error=True) as conn:
                with conn.cursor() as crx:
                    # يحدث العميل - على السرفر الرئيسي - بواسطة جوب
                    crx.execute(
                        sql_update_cust,
                        (self.mobile_phone,
                         self.work_phone or self.mobile_phone,
                         self.name,
                         self.address,
                         self.default_store_id.eplus_serial,
                         self.code,
                         self.eplus_serial)
                    )
                    # يضبط الربليكاشن
                    crx.execute(sql_replicate_cust, (self.eplus_serial,))
        except Exception as e:
            raise RetryableJobError(str(e), seconds=300)

    def btn_update_from_bconnect(self):
        with self.connect_eplus(param_str=PARAM_STR, charset='CP1256') as conn:
            with conn.cursor(as_dict=True) as cr:
                # يحدث العميل فورا من السرفر الرئيسي

                sql_select = f"""
                    SELECT 
                        cust_code as code, 
                        cust_mobile as mobile_phone, 
                        cust_tel as work_phone, 
                        cust_name_ar as name, 
                        cust_address as address, 
                        cust_def_sell_store as store_eplus_serial, 
                        IIF(cust_active = '1',1,0) as active  
                    FROM customer where cust_id={PARAM_STR}
                """
                cr.execute(
                    sql_select,
                    (self.eplus_serial,))

                data = cr.fetchall()
                if data:
                    cust_dict = data[0]
                    store_eplus_serial = cust_dict['store_eplus_serial']
                    get_store = self.env['ab_eplus_replication'].get_store
                    default_store_id = store_eplus_serial and get_store(store_eplus_serial) or False

                    odoo_dict = {
                        'code': self.code,
                        'name': self.name,
                        'mobile_phone': self.mobile_phone,
                        'work_phone': self.work_phone,
                        'address': self.address,
                        'default_store_id': self.default_store_id.id,
                        'active': self.active,
                    }
                    cust_dict = {
                        'code': cust_dict['code'],
                        'name': cust_dict['name'],
                        'mobile_phone': cust_dict['mobile_phone'],
                        'work_phone': cust_dict['work_phone'],
                        'address': cust_dict['address'],
                        'default_store_id': default_store_id,
                        'active': cust_dict['active'],
                    }
                    values_to_write = {
                        k: v for k, v in cust_dict.items()
                        if odoo_dict.get(k) != v
                    }
                    if values_to_write:
                        # do not create queue_job jobs for this write method
                        self = self.with_context(eplus_replication=True)

                        # write if different
                        self.write(values_to_write)
