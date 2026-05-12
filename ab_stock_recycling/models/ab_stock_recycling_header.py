import datetime
import re
import logging
from odoo.http import request
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from .ab_stock_recycling_overstock_sql import build_overstock_sql

PLACEHOLDER = '?'

_logger = logging.getLogger(__name__)


class StockRecycling(models.Model):
    _name = 'ab_stock_recycling_header'
    _description = 'ab_stock_recycling_header'
    _inherit = ['ab_eplus_connect', 'ab_data_from_excel', 'abdin_et.extra_tools']
    _rec_name = 'name'
    _order = 'id DESC'

    name = fields.Char(required=True)
    need_per_x_day = fields.Integer(compute='_compute_need_per_x_day')
    last_sales_x_days = fields.Integer(default=90)
    start_date = fields.Date(default=lambda self: datetime.date.today() - datetime.timedelta(days=90), required=True)
    end_date = fields.Date(default=lambda self: datetime.date.today(), required=True)
    from_excel = fields.Text()
    collection_count = fields.Integer(compute='_compute_counts')
    need_count = fields.Integer(compute='_compute_counts')
    distribution_count = fields.Integer(compute='_compute_counts')
    apply_source_store_need_first = fields.Boolean(default=True)
    excluded_items_codes = fields.Text()
    get_pending_transfer = fields.Boolean()
    use_last_trans_date_logic = fields.Boolean(default=False)

    excluded_item_temp_ids = fields.Many2many(
        comodel_name='ab_product',
        relation='ab_stock_recycling_item_cat_rel',
        column1='header_id',
        column2='item_id',
        string='Temp Excluded Items')
    only_item_ids = fields.Many2many(
        comodel_name='ab_product',
        relation='ab_stcok_recycle_header_item_catalog_rel',
        column1='header_id',
        column2='item_id',
        string='Need Only For Items')

    excluded_item_perm_ids = fields.Many2many(comodel_name='ab_stock_recycling_excluded_item',
                                              compute='_compute_excluded_item_perm_ids')

    count_of_excluded_items = fields.Integer(compute='_compute_count_of_excluded_items')
    show_advanced = fields.Boolean(default=True, string='Show Hidden Settings')

    process_type = fields.Selection(
        selection=[
            ('over', 'Overstock and Stagnant Recycling'),
            ('near', 'Nearly Exp Recycling'),
            ('need', 'Stock Need'),
        ], default='near')

    item_type = fields.Selection(
        selection=[
            ('all', 'All'),
            ('medicine', 'Medicine'),
            ('not_medicine', 'Cosmo'),
            ('service', 'Service'),
        ], default='all')

    store_ids = fields.Many2many(
        comodel_name='ab_store',
        relation='ab_stock_recycling_header_store_rel',
        column1='stock_recycling_id',
        column2='store_id',
        string='Receiving Stores',
        domain=[('active', '=', True), ('eplus_serial', '>', 0)]
    )

    overstock_store_ids = fields.Many2many(
        comodel_name='ab_store',
        relation='ab_stock_recycling_header_overstock_store_rel',
        column1='stock_recycling_id',
        column2='store_id',
        string='Sending Stores',
        domain=[('active', '=', True), ('eplus_serial', '>', 0)],
        default=lambda self: self._default_overstock_store_ids(),
    )

    collection_ids = fields.One2many(
        comodel_name='ab_stock_recycling_line',
        inverse_name='header_id',
        string='Collection Lines',
        required=False)

    need_ids = fields.One2many(
        comodel_name='ab_stock_recycling_need',
        inverse_name='header_id',
        string='Need Lines',
        required=False)

    dist_ids = fields.One2many(
        comodel_name='ab_stock_recycling_dist',
        inverse_name='header_id',
        string='Distribution Lines',
        required=False)

    def _default_overstock_store_ids(self):
        user = self.env.user
        if user.has_group('ab_stock_recycling.group_ab_stock_recycling_branch_role'):
            return self._get_branch_store_for_user(user)
        return self.env['ab_store']

    def _get_branch_store_for_user(self, user):
        if user.ab_stock_recycling_branch_store_id:
            return user.ab_stock_recycling_branch_store_id
        if user.name:
            store_model = self.env['ab_store']
            user_name = (user.name or '').strip()
            candidates = [user_name]
            if '-' in user_name:
                suffix = user_name.split('-', 1)[1].strip()
                if suffix:
                    candidates.append(suffix)
            for candidate in candidates:
                store = store_model.search([
                    ('name', '=', candidate),
                    ('active', '=', True),
                ], limit=1)
                if store:
                    user.sudo().write({'ab_stock_recycling_branch_store_id': store.id})
                    return store
            for candidate in candidates:
                store = store_model.search([
                    ('name', 'ilike', candidate),
                    ('active', '=', True),
                ], limit=1)
                if store:
                    user.sudo().write({'ab_stock_recycling_branch_store_id': store.id})
                    return store
        return self.env['ab_store']

    @api.constrains('overstock_store_ids')
    def _check_branch_role_sending_store(self):
        for rec in self:
            user = rec.env.user
            if not user.has_group('ab_stock_recycling.group_ab_stock_recycling_branch_role'):
                continue
            user_store = rec._get_branch_store_for_user(user)
            if not user_store:
                raise ValidationError(_("Set Stock Recycling Branch Store on the user before using branch_role."))
            if len(rec.overstock_store_ids) != 1 or rec.overstock_store_ids != user_store:
                raise ValidationError(_("Branch role users can only use their own sending store."))

    @api.depends('start_date', 'end_date')
    def _compute_need_per_x_day(self):
        for rec in self:
            rec.need_per_x_day = (rec.end_date - rec.start_date).days if rec.start_date and rec.end_date else 0

    @api.depends('collection_ids', 'need_ids', 'dist_ids')
    def _compute_counts(self):
        stock_line_mo = self.env['ab_stock_recycling_line']
        stock_need_mo = self.env['ab_stock_recycling_need']
        stock_dist_mo = self.env['ab_stock_recycling_dist']
        for rec in self:
            rec.collection_count = stock_line_mo.search_count([('header_id', '=', rec.id)])
            rec.need_count = stock_need_mo.search_count([('header_id', '=', rec.id)])
            rec.distribution_count = stock_dist_mo.search_count([('header_id', '=', rec.id)])

    def _compute_count_of_excluded_items(self):
        for rec in self:
            rec.count_of_excluded_items = self.env['ab_stock_recycling_excluded_item'].sudo().search_count([])

    def _compute_excluded_item_perm_ids(self):
        for rec in self:
            rec.excluded_item_perm_ids = self.env['ab_stock_recycling_excluded_item'].search([])

    def _get_eplus_serial_tuple(self, records):
        return tuple(int(serial) for serial in records.mapped('eplus_serial') if serial)

    def _records_by_eplus_serial(self, model_name, serials):
        serials = {int(serial) for serial in serials if serial}
        if not serials:
            return {}
        records = self.env[model_name].sudo().search([('eplus_serial', 'in', list(serials))])
        return {int(record.eplus_serial): record for record in records if record.eplus_serial}

    def _replicate_master_data(self):
        replication_model = self.env.get('ab_odoo_replication')
        if not replication_model:
            return
        replication_model = replication_model.sudo()
        replication_model.replicate_model('ab_store')
        replication_model.replicate_model('ab_product_company')
        replication_model.replicate_model('ab_product_card')
        replication_model.replicate_model('ab_product')

    def _prepare_stock_rows(self, rows):
        store_by_serial = self._records_by_eplus_serial('ab_store', [row[0] for row in rows])
        product_by_serial = self._records_by_eplus_serial('ab_product', [row[1] for row in rows])
        for row in rows:
            store = store_by_serial.get(int(row[0] or 0))
            product = product_by_serial.get(int(row[1] or 0))
            if not store or not product:
                continue
            yield row, store, product

    def btn_show_view(self):
        res_model = self.env.context.get('recycling_model')
        title = self.env.context.get('title') or '.'
        if res_model:
            return {
                "name": title,
                "type": "ir.actions.act_window",
                "res_model": res_model,
                "views": [[False, "list"], [False, "pivot"], [False, "form"], ],
                "target": "current",
                "domain": [('header_id', '=', self.id)],
            }

    def btn_get_need_for_specific_stores(self):
        fn_balance_sales = (
            'fn_balance_sales_with_trans_odoo'
            if self.get_pending_transfer
            else 'fn_balance_sales_odoo')

        if self.need_ids:
            raise ValidationError(_("There are old need lines, please do reset need. "))

        # if item_type='all' then remove item_type condition from sql
        and_item_type_str, item_type_tuple = self._get_item_type()

        only_item_serials = self._get_eplus_serial_tuple(self.only_item_ids)
        only_items_placeholders = ','.join([PLACEHOLDER] * len(only_item_serials))
        and_only_items_str = only_item_serials and f" and item_id in ({only_items_placeholders}) " or ''

        # get a list of
        store_ids = tuple(str(serial) for serial in self._get_eplus_serial_tuple(self.store_ids))
        store_ids_str = ",".join(store_ids)
        and_store_ids_str = f" and store_id in ({store_ids_str}) " if store_ids else ''
        excluded_item_ids = self._get_eplus_serial_tuple(self.excluded_item_temp_ids)
        excluded_items_placeholders = ','.join([PLACEHOLDER] * len(excluded_item_ids))
        and_excluded_items_str = excluded_item_ids and f" and item_id not in ({excluded_items_placeholders}) " or ''
        stores_type_store = tuple(
            str(serial)
            for serial in self._get_eplus_serial_tuple(self.store_ids.filtered(lambda sto: sto.store_type == 'store'))
        )
        store_type_store_str = ",".join(stores_type_store)
        or_store_id_in_stores = f" or (store_id in ({store_type_store_str}) and balance>0.09)  " if stores_type_store else ''
        try:
            with self.connect_eplus(param_str=PLACEHOLDER, autocommit=True) as conn:
                with conn.cursor() as cr:
                    cr.execute("""
                            SET TRANSACTION ISOLATION LEVEL SNAPSHOT;
                    """)

                    sql = f"""
                            SELECT store_id,item_id,isnull(qty_sales,0) - balance, qty_sales, balance 
                            from {fn_balance_sales}({PLACEHOLDER},{PLACEHOLDER}) 
                            where  (1=1)
                            {and_item_type_str} {and_store_ids_str} {and_excluded_items_str} {and_only_items_str}
                    """
                    cr.execute(sql, (
                            (self.start_date.isoformat(), self.end_date.isoformat())
                            + item_type_tuple
                            + excluded_item_ids
                            + only_item_serials))

                    rows = cr.fetchall()
                    need_dicts_list = []
                    for row, store, product in  self._prepare_stock_rows(rows):
                        need_dicts_list.append({
                            "store_id": store.id,
                            "item_id": product.id,
                            "qty": row[2],
                            "sales_qty": row[3],
                            "balance": row[4],
                        })
                    self.write({'need_ids': [(0, 0, need_dict) for need_dict in need_dicts_list]})
            self.env.cr.commit()
        except Exception as ex:
            raise UserError(_(str(ex)))

    def btn_distribute_stock(self):
        if self.dist_ids:
            raise ValidationError(_("There are old distribution lines, please do reset distribution. "))
        dist_line_dicts_list = []
        self.env['ab_stock_recycling_line'].flush_model(['qty', 'distributed_qty', 'header_id'])
        self.env.cr.execute(
            """select id
               from ab_stock_recycling_line
               where qty != distributed_qty
                 and header_id = %s""",
            (self.id,))
        overstock_ids = [row[0] for row in self.env.cr.fetchall()]

        overstock_lines = self.collection_ids.browse(overstock_ids)
        i = 0
        for over_line in overstock_lines:
            i += 1

            total_transferred = 0
            current_branch_need = self.need_ids.search([('header_id', '=', self.id),
                                                        ('item_id', '=', over_line.item_id.id),
                                                        ('store_id', '=', over_line.store_id.id),
                                                        ])
            rest_over_qty = over_line.qty
            if self.apply_source_store_need_first:
                transferred_qty = min(rest_over_qty, current_branch_need.qty)
                if transferred_qty:
                    dist_line_dicts_list.append(
                        {
                            'item_id': current_branch_need.item_id.id,
                            'stock_line_id': over_line.id,
                            'need_line_id': current_branch_need.id,
                            'from_store_id': over_line.store_id.id,
                            'to_store_id': current_branch_need.store_id.id,
                            'file_source': over_line.file_source,
                            'qty': transferred_qty,
                        }
                    )

                    rest_over_qty -= transferred_qty
                    total_transferred += transferred_qty
                    current_branch_need.given_qty += transferred_qty

            # THEN distribute qty for rest of branchs needs
            self.env.cr.execute(
                """select need.id
                   from ab_stock_recycling_need need
                            left join ab_store sto on need.store_id = sto.id
                   where need.item_id = %s
                     and need.store_id != %s
                     and header_id = %s
                   order by sto.name, sales_qty desc, need.qty desc
                """,
                (over_line.item_id.id, over_line.store_id.id, self.id))
            need_ids = [row[0] for row in self.env.cr.fetchall()]
            need_ids_lines = self.need_ids.browse(need_ids)
            for need in need_ids_lines:
                transferred_qty = min(rest_over_qty, need.qty - need.given_qty)
                total_transferred += transferred_qty
                rest_over_qty -= transferred_qty
                if transferred_qty > 0:
                    need.given_qty += transferred_qty
                    dist_line_dicts_list.append(
                        {
                            'item_id': need.item_id.id,
                            'stock_line_id': over_line.id,
                            'need_line_id': need.id,
                            'from_store_id': over_line.store_id.id,
                            'to_store_id': need.store_id.id,
                            'file_source': over_line.file_source,
                            'qty': transferred_qty,
                        }
                    )
                else:
                    break
            over_line.distributed_qty = total_transferred
        self.write({'dist_ids': [(0, 0, dist_line_dict) for dist_line_dict in dist_line_dicts_list]})
        # dist_line_dicts_list.clear()
        self.invalidate_recordset()
        self.env.cr.commit()

    def btn_reset_dist(self):
        self.dist_ids.unlink()
        self.collection_ids.distributed_qty = 0
        self.need_ids.given_qty = 0

    def btn_reset_need(self):
        self.write({'need_ids': [(6, False, [])]})

    def btn_reset_collection(self):
        self.collection_ids.unlink()

    def btn_get_overstock_for_stores(self):
        if self.env.user.has_group('ab_stock_recycling.group_ab_stock_recycling_branch_role'):
            branch_store = self._get_branch_store_for_user(self.env.user)
            if not branch_store:
                raise ValidationError(_("Set Stock Recycling Branch Store on the user before using branch_role."))
            if self.overstock_store_ids != branch_store:
                self.overstock_store_ids = [(6, 0, [branch_store.id])]

        fn_balance_sales = (
            'fn_balance_sales_with_trans_odoo'
            if self.get_pending_transfer
            else 'fn_balance_sales_odoo')

        if self.collection_ids:
            raise ValidationError(_("There are old stock lines, please do reset stock. "))

        # make replication in case of new items or stores
        self._replicate_master_data()

        # if item_type is false then remove item_type condition from sql
        and_item_type_str, item_type_tuple = self._get_item_type()

        store_ids = tuple(str(serial) for serial in self._get_eplus_serial_tuple(self.overstock_store_ids))
        store_ids_str = ",".join(store_ids)
        and_store_ids_str = f" and store_id in ({store_ids_str}) " if store_ids else ''
        excluded_item_ids = self._get_eplus_serial_tuple(
            self.env['ab_stock_recycling_excluded_item'].search([]).mapped('item_id')
        )
        excluded_item_ids += self._get_eplus_serial_tuple(self.excluded_item_temp_ids)
        excluded_items_placeholders = ','.join([PLACEHOLDER] * len(excluded_item_ids))
        and_excluded_items_str = (
            f" and item_id not in ({excluded_items_placeholders}) "
            if excluded_item_ids
            else ''
        )

        with self.connect_eplus(param_str=PLACEHOLDER, autocommit=True) as conn:
            with conn.cursor() as cr:
                cr.execute("""
                        SET TRANSACTION ISOLATION LEVEL SNAPSHOT;
                """)

                sql, has_last_trans_date = build_overstock_sql(
                    fn_balance_sales=fn_balance_sales,
                    placeholder=PLACEHOLDER,
                    and_store_ids_str=and_store_ids_str,
                    and_item_type_str=and_item_type_str,
                    and_excluded_items_str=and_excluded_items_str,
                    include_last_trans_date=self.use_last_trans_date_logic,
                )
                today = datetime.date.today()
                cr.execute(sql,
                           (self.start_date, self.end_date,)
                           + item_type_tuple
                           + excluded_item_ids
                           + ((today - datetime.timedelta(days=self.last_sales_x_days)).isoformat(), today.isoformat())
                           + item_type_tuple
                           + excluded_item_ids
                           )

                rows = cr.fetchall()
                overstock_dicts_list = []
                for row, store, product in  self._prepare_stock_rows(rows):
                    last_trans_date = row[6] if has_last_trans_date else False
                    overstock_dicts_list.append({
                        "store_id": store.id,
                        "item_id": product.id,
                        "qty": row[2],
                        "sales_qty": row[3],
                        "balance": row[4],
                        "sales_x_qty": row[5],
                        "last_trans_date": last_trans_date,
                        "file_source": store.name,
                    })

                self.write({'collection_ids': [(0, 0, overstock_dict) for overstock_dict in overstock_dicts_list]})
            self.env.cr.commit()

    def btn_get_need_for_stock(self):
        fn_balance_sales = (
            'fn_balance_sales_with_trans_odoo'
            if self.get_pending_transfer
            else 'fn_balance_sales_odoo')

        if self.need_ids:
            raise ValidationError(_("There are old need lines, please do reset need. "))

        # get a list of
        items_tuple = self._get_eplus_serial_tuple(self.collection_ids.mapped('item_id'))
        if not items_tuple:
            raise ValidationError(_("There are no stock lines with ePlus product serials."))
        store_ids = tuple(str(serial) for serial in self._get_eplus_serial_tuple(self.store_ids))
        store_ids_str = ",".join(store_ids)
        and_store_ids_str = f" and store_id in ({store_ids_str}) " if store_ids else ''

        placeholders = ','.join([PLACEHOLDER] * len(items_tuple))
        try:
            with self.connect_eplus(param_str=PLACEHOLDER, autocommit=True) as conn:
                with conn.cursor() as cr:
                    cr.execute("""
                            SET TRANSACTION ISOLATION LEVEL SNAPSHOT;
                    """)

                    sql = f"""
                            SELECT store_id,item_id,qty_sales - balance,qty_sales,balance 
                            from {fn_balance_sales}({PLACEHOLDER},{PLACEHOLDER}) 
                            where item_id in ({placeholders}) and  (isnull(qty_sales,0) - balance)>0 
                            {and_store_ids_str} 
                    """
                    cr.execute(sql, (self.start_date.isoformat(), self.end_date.isoformat()) + items_tuple)

                    rows = cr.fetchall()
                    need_dicts_list = []
                    for row, store, product in self._prepare_stock_rows(rows):
                        need_dicts_list.append({
                            "store_id": store.id,
                            "item_id": product.id,
                            "qty": row[2],
                            "sales_qty": row[3],
                            "balance": row[4],
                        })
                    self.write({'need_ids': [(0, 0, need_dict) for need_dict in need_dicts_list]})
            self.env.cr.commit()
        except Exception as ex:
            raise UserError(_(str(ex)))

    def btn_one_click_distribute(self):
        if self.overstock_store_ids and self.from_excel:
            raise ValidationError(
                _("You should either (STAGNANT AND OVERSTOCK RECYCLING) or (NEARLY EXP STOCK RECYCLING) "))

        if self.overstock_store_ids:
            self.btn_get_overstock_for_stores()
        elif self.from_excel:
            self._add_data_from_excel()
        else:
            raise ValidationError(
                _("You should either (STAGNANT AND OVERSTOCK RECYCLING) or (NEARLY EXP STOCK RECYCLING) "))

        self.btn_get_need_for_stock()
        self.btn_distribute_stock()
        message = _(f"""  
        <div class='h4 text-success'>Process completed successfully</div>  
        <div class='h6 text-info w-50'>
            <table class='table table-striped'>
                <tr>
                    <th>Number of Target Stock lines</th>
                    <td>{len(self.collection_ids)}</td>
                </tr>
                <tr>
                    <th>Number of Need Stock lines</th>
                    <td>{len(self.need_ids)}</td>
                </tr>
                <tr>
                    <th>Number of Distributed Stock lines</th>
                    <td>{len(self.dist_ids)}</td>
                </tr>
            </table>
        </div>
        """)
        return self.ab_msg(message=message)

    def btn_add_data_from_excel(self):
        number_of_lines = self._add_data_from_excel()

        message = _(f"""<span class='h4 text-success'>{number_of_lines}</span> lines added  
        <span class='h4 text-success'>successfully</span>  
        by user <span class='h4 font-italic text-muted'>{self.env.user.name}</span>""")
        return self.ab_msg(message=message)

    def _add_data_from_excel(self):
        if not self.from_excel:
            raise ValidationError(_("You must paste excel data into the box"))
        number_of_lines = len(self.from_excel.strip().split('\n')) - 1
        self.data_from_excel(model_name='ab_stock_recycling_line',
                             x2many_field='collection_ids',
                             excel_data=self.from_excel.strip('\n'), update_only=False)
        self.from_excel = ""
        return number_of_lines

    def _modify_excluded_items(self, item_ids, modify_type):
        excluded_items_model = self.env['ab_stock_recycling_excluded_item'].sudo()
        if modify_type == 'add':
            items_to_add = set(item_ids).difference(excluded_items_model.search([]).mapped('item_id.id'))
            for item_id in items_to_add:
                excluded_items_model.create({'item_id': item_id})
        elif modify_type == 'remove':
            self.env['ab_stock_recycling_excluded_item'].sudo().search([('item_id', 'in', item_ids)]).unlink()
        elif modify_type == 'add_temp':
            self.write({'excluded_item_temp_ids': [(6, 0, item_ids)]})
            print(item_ids)
        elif modify_type == 'remove_temp':
            self.write({'excluded_item_temp_ids': [(3, item_id) for item_id in item_ids]})

    def btn_modify_excluded_items_codes(self):
        modify_type = self.env.context.get('modify_type')
        item_codes = [item.strip() for item in re.split(',|\n', self.excluded_items_codes or '') if item.strip()]

        item_ids = self.env['ab_product'].search(
            [('code', 'in', item_codes)]).ids

        if item_ids:
            self._modify_excluded_items(item_ids, modify_type)

    def btn_show_excluded_items(self):
        return {
            "name": 'Excluded Items',
            "type": "ir.actions.act_window",
            "res_model": 'ab_stock_recycling_excluded_item',
            "views": [[False, "list"], [False, "pivot"], [False, "form"], ],
            "target": "current",
        }

    # refresh excluded_items list
    def btn_refresh_excluded_items_list(self):
        ex_items_model = self.env['ab_stock_recycling_excluded_item'].sudo()
        self._replicate_master_data()
        with self.connect_eplus(param_str=PLACEHOLDER, autocommit=True) as conn:
            with conn.cursor() as cr:
                cr.execute("""
                        SET TRANSACTION ISOLATION LEVEL SNAPSHOT;
                """)

                cr.execute("""
                           select itm_id,
                                  case
                                      when sec_insert_date >= GETDATE() - 3 * 30 then 'new_item'
                                      when itm_name_ar like '%%@%%' then '@'
                                      when itm_name_ar like '%%XXX%%' and itm_ismedicine = 1 then 'xxx'
                                      end

                           from item_catalog
                           where (sec_insert_date >= GETDATE() - 3 * 30)
                              OR (itm_name_ar like '%%@%%')
                              OR (itm_name_ar like '%%XXX%%' and itm_ismedicine = 1)
                           """)

                item_list = cr.fetchall()
                product_by_serial = self._records_by_eplus_serial('ab_product', [item[0] for item in item_list])
                item_values = [
                    (product_by_serial[int(item[0])].id, item[1])
                    for item in item_list
                    if int(item[0] or 0) in product_by_serial
                ]
                curr_item_ids = set(ex_items_model.search([]).mapped('item_id.id'))
                if item_values:
                    for item_id, exclusion_reason in item_values:
                        if item_id not in curr_item_ids:
                            ex_items_model.create({'item_id': item_id, 'exclusion_reason': exclusion_reason})

                # Remove Items that - now - does not fulfill 'exclusion policy'
                not_custom_items = set(ex_items_model.search(['|',
                                                              ('exclusion_reason', '!=', 'custom'),
                                                              ('exclusion_reason', '!=', False)]).mapped('item_id.id'))
                ex_items_model.search([('item_id', 'in', list(not_custom_items - set(it[0] for it in item_values)))]
                                      ).unlink()

    def btn_export_excel_over_need(self):
        action = self.env.ref("ab_stock_recycling.action_export_overstock_no_need")
        action.sudo().name = "Overstock without need"
        return action.report_action(self)

    def get_overstock_no_need_data(self):
        sql = """
              select product.code,
                     product.name,
                     product.default_price,
                     sum(stock.qty)                              as total_qty,
                     sum(stock.distributed_qty)                  as total_dist_qty,
                     sum(stock.qty) - sum(stock.distributed_qty) as no_need_qty

              from ab_stock_recycling_line stock
                       left join ab_product product on product.id = stock.item_id
              where stock.header_id = %s
              group by product.code, product.name, product.default_price
              having sum(stock.qty) - sum(stock.distributed_qty) > 0.1 \
              """
        self.env['ab_stock_recycling_line'].flush_model(['item_id', 'qty', 'distributed_qty', 'header_id'])
        self.env.cr.execute(sql, (self.id,))
        rows = self.env.cr.fetchall()
        return {
            'headers': ['Code', 'Name', 'Price', 'Target Qty', 'Distributed Qty', 'No Need Qty'],
            'rows': rows
        }

    def btn_download_need_files(self):
        # Convert the list of ids to a string
        request.session['stock_recycling_header_id'] = self.id
        # Return an action of type 'ir.actions.act_url'
        return {
            'type': 'ir.actions.act_url',
            'url': '/stock_need_download',
            'target': 'self',
        }

    def _get_item_type(self):
        # if item_type=all then remove item_type condition from sql
        and_item_type_str = ""
        item_type_tuple = tuple()
        if self.item_type != 'all':
            and_item_type_str = f" and item_type = {PLACEHOLDER} "
            item_type_tuple = (self.item_type,)

        return and_item_type_str, item_type_tuple
