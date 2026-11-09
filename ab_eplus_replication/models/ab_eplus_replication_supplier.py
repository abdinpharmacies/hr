from odoo import api, fields, models, _

PARAM_STR = "%s"


class ReplicationSupplier(models.AbstractModel):
    _inherit = 'ab_eplus_replication'

    def replicate_ab_supplier(self, replicate_all=False, update_target=None, xrows=10000, commit=False,
                              where_extra_and="", eplus_serials=None, **kw):
        if eplus_serials:
            replicate_all = True

        if replicate_all:
            last_update_date = None
        else:
            last_update_date = self._get_last_update_date(model_name='ab_supplier')

        suppliers = self._get_suppliers_from_bconnect(last_update_date, xrows, where_extra_and=where_extra_and,
                                                      eplus_serials=eplus_serials)

        for i, chunk_of_suppliers in enumerate(suppliers):
            msg = f"Replicating Suppliers Part {i}"
            self._start_suppliers_replication(chunk_of_suppliers, msg=msg, update_target=update_target,
                                              replicate_all=replicate_all)
            if commit:
                self.env.cr.commit()

    def _get_suppliers_from_bconnect(self, last_update_date, xrows, where_extra_and="", eplus_serials=None):
        where_condition = self._get_where_condition(last_update_date)
        where_condition += where_extra_and
        if eplus_serials:
            serials_str = ','.join(map(str, eplus_serials))
            where_condition += f" and main.ven_id in ({serials_str}) "

        sql = f"""
        SET TRANSACTION ISOLATION LEVEL SNAPSHOT;
        Select main.ven_code ,
        main.ven_name_ar ,
        main.ven_active ,
        IIF(sec_update_date is NULL,sec_insert_date,sec_update_date) as last_update_date,
        main.ven_id 
        from vendor main
         {where_condition}
         order by last_update_date
         """

        yield from self._fetch_eplus_data(sql, last_update_date, xrows)

    def _start_suppliers_replication(self, products, msg="Replicating Products", replicate_all=False, **kw):
        for item in self.web_progress_iter(products, msg=msg):
            supplier_dict = {
                "code": item['ven_code'],
                "name": item['ven_name_ar'],
                "active": item['ven_active'] == "1",
                "last_update_date": item['last_update_date'],
                "eplus_serial": item['ven_id'],
            }
            if replicate_all:
                supplier_dict.pop('last_update_date', None)

            supplier = self._get_or_create_record(supplier_dict, model_name='ab_supplier', **kw)

            costcenter_mo = self.env['ab_costcenter'].sudo().with_context(active_test=False)
            costcenter = costcenter_mo.search([('code', '=', f"1-{supplier.code}")])
            # supplier_mo = self.env['ab_supplier'].sudo().with_context(active_test=False)

            if 'ibn' in supplier.name:

                costcenter_ibn = costcenter_mo.search([('code', '=', '1-1470')])
                if not costcenter_ibn:
                    costcenter.create({
                        'code': '1-1470',
                        'name': 'شركة ابن سينا فارما',
                    })

                supplier.costcenter_id = costcenter_ibn.id

            elif 'ucp' in supplier.name:
                costcenter_ucp = costcenter_mo.search([('code', '=', '1-1471')])
                if not costcenter_ucp:
                    costcenter.create({
                        'code': '1-1471',
                        'name': 'شركة المتحدة للصيادلة',
                    })
                supplier.costcenter_id = costcenter_ucp.id

            elif 'uctd' in supplier.name:
                costcenter_uctd = costcenter_mo.search([('code', '=', '1-1473')])
                if not costcenter_uctd:
                    costcenter.create({
                        'code': '1-1473',
                        'name': 'المتحدة للتجارة و التوزيع للسلع الاستهلاكية',
                    })
                supplier.costcenter_id = costcenter_uctd.id

            else:
                if costcenter:
                    costcenter.name = supplier.name
                else:
                    cc = costcenter.create({
                        'code': f"1-{supplier.code}",
                        'name': supplier.name,
                    })
                    supplier.costcenter_id = cc.id
