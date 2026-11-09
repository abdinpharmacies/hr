from odoo import models

PARAM_STR = "%s"


class ReplicationProductBarcode(models.AbstractModel):
    _inherit = 'ab_eplus_replication'

    def replicate_ab_product_barcode(self, replicate_all=False, update_target=None, xrows=10000, commit=False,
                                     where_extra_and="",
                                     eplus_serials=None, **kw):
        if eplus_serials:
            replicate_all = True

        if replicate_all:
            last_update_date = None
        else:
            last_update_date = self._get_last_update_date(model_name='ab_product_barcode')

        barcodes = self._get_barcodes_from_bconnect(last_update_date, xrows, where_extra_and=where_extra_and,
                                                    eplus_serials=eplus_serials)

        for i, chunk_of_barcodes in enumerate(barcodes):
            msg = f"Replicating barcodes Part {i}"
            self._start_barcodes_replication(chunk_of_barcodes, msg=msg, update_target=update_target,
                                             replicate_all=replicate_all)
            if commit:
                self.env.cr.commit()

    def _get_barcodes_from_bconnect(self, last_update_date, xrows, where_extra_and="", eplus_serials=None):
        where_condition = self._get_where_condition(last_update_date)
        where_condition += where_extra_and
        if eplus_serials:
            serials_str = ','.join(map(str, eplus_serials))
            where_condition += f" and main.io_id in ({serials_str}) "

        sql = f"""
            SET TRANSACTION ISOLATION LEVEL SNAPSHOT;
            SELECT 
                    main.io_id AS eplus_serial , 
                    main.io_itm_id AS product_eplus_serial,
                    main.io_itm_int AS name,
                    main.sec_update_date AS last_update_date
                FROM item_objects main
            {where_condition}
            ORDER BY last_update_date
         """

        yield from self._fetch_eplus_data(sql, last_update_date, xrows)

    def _start_barcodes_replication(self, barcodes, msg="Replicating Barcodes", replicate_all=False, **kw):
        for item in self.web_progress_iter(barcodes, msg=msg):
            barcode_dict = {
                "name": item['name'],
                "eplus_serial": item['eplus_serial'],
                "last_update_date": item['last_update_date'],
            }

            if replicate_all:
                barcode_dict.pop('last_update_date', None)

            barcode = self._get_or_create_record(barcode_dict, model_name='ab_product_barcode', **kw)
            product = self._get_product(eplus_serial=item['product_eplus_serial'])
            if product and product.id not in barcode.product_ids.ids:
                barcode.write({'product_ids': [(4, product.id)]})

    def _get_product(self, eplus_serial):
        product = self.env['ab_product'].with_context(active_test=False).search([
            ('eplus_serial', '=', eplus_serial)
        ])
        if not product:
            self.replicate_ab_product(commit=True)
            product = self.env['ab_product'].with_context(active_test=False).search([
                ('eplus_serial', '=', eplus_serial)
            ])

        return product
