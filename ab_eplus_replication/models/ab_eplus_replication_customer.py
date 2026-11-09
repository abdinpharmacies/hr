from contextlib import nullcontext
from odoo import models

PARAM_STR = "%s"


class ReplicationStore(models.AbstractModel):
    _inherit = 'ab_eplus_replication'

    def replicate_ab_customer(self, replicate_all=False, update_target=None, xrows=10000, commit=False,
                              where_extra_and="",
                              eplus_serials=None, **kw):
        if eplus_serials:
            replicate_all = True

        if replicate_all:
            last_update_date = None
        else:
            last_update_date = self._get_last_update_date(model_name='ab_customer')

        customers = self._get_customers_from_bconnect(last_update_date, xrows, where_extra_and=where_extra_and,
                                                      eplus_serials=eplus_serials)

        for i, chunk_of_customers in enumerate(customers, 1):
            msg = f"Replicating Customers Part {i}"
            self._start_customers_replication(chunk_of_customers, msg=msg, update_target=update_target,
                                              replicate_all=replicate_all)
            if commit:
                self.env.cr.commit()

    def _get_customers_from_bconnect(self, last_update_date, xrows, where_extra_and="", eplus_serials=None):
        where_condition = self._get_where_condition(last_update_date)
        where_condition += where_extra_and
        if eplus_serials:
            serials_str = ','.join(map(str, eplus_serials))
            where_condition += f" and main.cust_id in ({serials_str}) "

        sql = f"""
            SET TRANSACTION ISOLATION LEVEL SNAPSHOT;
            Select main.cust_code,
            main.cust_name_ar,
            main.cust_mobile,
            main.cust_tel,
            cd.cd_tel,
            main.cust_address,
            main.cust_def_sell_store,
            IIF(main.sec_update_date is NULL,main.sec_insert_date,main.sec_update_date) as last_update_date,
            main.sec_insert_date,
            main.cust_id as eplus_serial,
            IIF(main.cust_active = '1',1,0) as active  
            from customer main
            left join Customer_Delivery cd on cd.cd_cust_id = main.cust_id and cd_id=1        
            {where_condition}
         order by last_update_date
         """

        yield from self._fetch_eplus_data(sql, last_update_date, xrows)

    def _start_customers_replication(self, customers, msg="Replicating Customers", replicate_all=False, **kw):
        with nullcontext():  # Odoo 15 norecompute was already a no-op.
            for item in self.web_progress_iter(customers, msg=msg):
                store_eplus_serial = item['cust_def_sell_store']
                default_store_id = store_eplus_serial and self.get_store(store_eplus_serial).id or False
                customer_dict = {
                    "code": item['cust_code'],
                    "name": item['cust_name_ar'],
                    "address": item['cust_address'],
                    "default_store_id": default_store_id,
                    "mobile_phone": item['cust_mobile'],
                    "work_phone": item['cust_tel'],
                    "delivery_phone": item['cd_tel'],
                    "last_update_date": item['last_update_date'],
                    "eplus_serial": item['eplus_serial'],
                    "active": item['active'],
                    "eplus_create_date": item['sec_insert_date'],
                }

                update = True
                if str(customer_dict['code']).lower().startswith('spare'):
                    update = False

                if replicate_all:
                    customer_dict.pop('last_update_date', None)

                self._get_or_create_record(customer_dict, model_name='ab_customer', update=update, **kw)
