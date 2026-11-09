from odoo import models

PARAM_STR = "%s"


class ReplicationStore(models.AbstractModel):
    _inherit = 'ab_eplus_replication'

    def replicate_ab_store(self, replicate_all=False, update_target=None, xrows=10000, commit=False, where_extra_and="",
                           eplus_serials=None, **kw):
        if eplus_serials:
            replicate_all = True

        if replicate_all:
            last_update_date = None
        else:
            last_update_date = self._get_last_update_date(model_name='ab_store')

        stores = self._get_stores_from_bconnect(last_update_date, xrows, where_extra_and=where_extra_and,
                                                eplus_serials=eplus_serials)

        for i, chunk_of_stores in enumerate(stores):
            msg = f"Replicating stores Part {i}"
            self._start_stores_replication(chunk_of_stores, msg=msg, update_target=update_target,
                                           replicate_all=replicate_all)
            if commit:
                self.env.cr.commit()

    def _get_stores_from_bconnect(self, last_update_date, xrows, where_extra_and="", eplus_serials=None):
        where_condition = self._get_where_condition(last_update_date)
        where_condition += where_extra_and
        if eplus_serials:
            serials_str = ','.join(map(str, eplus_serials))
            where_condition += f" and main.sto_id in ({serials_str}) "

        sql = f"""
            SET TRANSACTION ISOLATION LEVEL SNAPSHOT;
            Select main.sto_code,
            main.sto_name_ar,
            main.sto_ip1,
            main.sto_ip2,
            main.sto_ip3,
            main.sto_ip4,
            main.sto_tel,
            IIF(main.sec_update_date is NULL,main.sec_insert_date,main.sec_update_date) as last_update_date,
            main.sto_id as eplus_serial,
            main.activated
            from store main         
            {where_condition}
         order by last_update_date
         """

        yield from self._fetch_eplus_data(sql, last_update_date, xrows)

    def _start_stores_replication(self, stores, msg="Replicating Stores", replicate_all=False, **kw):
        for item in self.web_progress_iter(stores, msg=msg):
            active = True

            # store exists
            item_exists_by_code = self.env['ab_store'].sudo().with_context(active_test=False).search(
                [('code', '=', item['sto_code'])]
            )
            if item_exists_by_code:
                # Must set eplus_serial 'MANUALLY' if not set
                if not item_exists_by_code.eplus_serial:
                    continue
                else:
                    # keep store active value
                    active = item_exists_by_code.active
            # New Internal Store
            elif item['activated'] != '2':
                active = False

            store_dict = {
                "code": item['sto_code'],
                "name": item['sto_name_ar'],
                "ip1": item['sto_ip1'],
                "ip2": item['sto_ip2'],
                "ip3": item['sto_ip3'],
                "ip4": item['sto_ip4'],
                "location": item['sto_tel'],
                "last_update_date": item['last_update_date'],
                "eplus_serial": item['eplus_serial'],
                "active": active,
            }

            if replicate_all:
                store_dict.pop('last_update_date', None)

            self._get_or_create_record(store_dict, model_name='ab_store', **kw)
