from contextlib import nullcontext
from odoo import models

PARAM_STR = "%s"


class ReplicationStore(models.AbstractModel):
    _inherit = 'ab_eplus_replication'

    def replicate_ab_costcenter(self, replicate_all=False, update_target=None, xrows=10000, commit=False,
                                where_extra_and="",
                                eplus_serials=None, **kw):
        if eplus_serials:
            replicate_all = True

        if replicate_all:
            last_update_date = None
        else:
            last_update_date = self._get_last_update_date(model_name='ab_costcenter')

        costcenters = self._get_costcenters_from_bconnect(last_update_date, xrows, where_extra_and=where_extra_and,
                                                          eplus_serials=eplus_serials)

        for i, chunk_of_costcenters in enumerate(costcenters, 1):
            msg = f"Replicating Costcenters Part {i}"
            self._start_costcenters_replication(chunk_of_costcenters, msg=msg, update_target=update_target,
                                                replicate_all=replicate_all)
            if commit:
                self.env.cr.commit()

    def _get_costcenters_from_bconnect(self, last_update_date, xrows, where_extra_and="", eplus_serials=None):
        where_condition = self._get_where_condition(last_update_date)
        where_condition += where_extra_and
        if eplus_serials:
            serials_str = ','.join(map(str, eplus_serials))
            where_condition += f" and main.cust_id in ({serials_str}) "
        sql = f"""
            --SET TRANSACTION ISOLATION LEVEL SNAPSHOT;
            Select 
                main.e_id,
                main.e_name,
                users.usr_password,
                IIF(main.sec_update_date is NULL,main.sec_insert_date,main.sec_update_date) as last_update_date
            FROM employee main
            LEFT JOIN users ON users.usr_e_id = main.e_id         
            {where_condition}
         order by last_update_date
         """

        yield from self._fetch_eplus_data(sql, last_update_date, xrows)

    def _start_costcenters_replication(self, costcenters, msg="Replicating Costcenters", replicate_all=False, **kw):
        with nullcontext():  # Odoo 15 norecompute was already a no-op.
            for item in self.web_progress_iter(costcenters, msg=msg):
                costcenter_dict = {
                    "eplus_serial": item['e_id'],
                    "name": item['e_name'],
                    "bc_id": item['e_id'],
                    "password": item['usr_password'],
                    "last_update_date": item['last_update_date'],
                }

                if replicate_all:
                    costcenter_dict.pop('last_update_date', None)

                # update_target to just update (no create)
                self._get_or_create_record(
                    costcenter_dict,
                    model_name='ab_costcenter',
                    update_target=["name", "password", "bc_id", "last_update_date"])
