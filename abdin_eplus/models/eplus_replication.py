import logging

from odoo import fields, models, api
import datetime
import time
from odoo.exceptions import UserError

PARAM_STR = '?'
TABLES = [
    {'t_name': 'store',
     'o_fields': ['id', 'sto_id', 'sto_code', 'sto_name_ar', 'sto_ip1', 'activated', 'tup']},
    {'t_name': 'customer_contracts',
     'o_fields': ['id', 'cc_id', 'cc_cust_id', 'cc_name', 'cc_pay_perc', 'cc_dis_per_for_cust', 'tup']},
    {'t_name': 'employee', 'o_fields': ['id', 'e_id', 'e_code', 'e_name', 'e_active', 'e_delivery', 'tup']},
    {'t_name': 'vendor', 'o_fields': ['id', 'ven_id', 'ven_code', 'ven_name_ar', 'ven_tel', 'tup']},
    {'t_name': 'item_catalog',
     'o_fields': ['id', 'itm_id', 'itm_code', 'itm_def_sell_price', 'itm_def_pharm_price', 'itm_ismedicine', 'tup']},
    {'t_name': 'customer',
     'o_fields': ['id', 'cust_id', 'cust_code', 'cust_name_ar', 'cust_parent', 'cust_type', 'tup']},
]

PURCHASE_TABLES = [
    {'t_name': 'pur_trans_h',
     'o_fields': ['id', 'pth_id', 'sto_id', 'ven_id', 'total_bill', 'total_after_back',
                  'ven_bill_no', 'pth_notice', 'sec_insert_date', 'tup']},
    {'t_name': 'pur_trans_d',
     'o_fields': ['id', 'serial', 'pth_id', 'itm_id', 'qnty', 'bonus', 'itm_back_qty', 'itm_back_bonus',
                  'itm_cost',
                  'sec_insert_date', 'sec_update_date', 'tup']},
]

TRANSFER_TABLE_FIELDS = ['stnh_id', 'stnh_f_sto_id', 'stnh_t_sto_id', 'stnh_tot_sell_value',
                         'stnh_tot_cost_value',
                         'stnh_no_items', 'stnh_notes', 'stnh_flag', 'sec_insert_uid', 'sec_insert_date',
                         'sec_update_uid', 'sec_update_date', 'delivery_emp']
TRANS_DAYS_LATER = 15

STEP = 365  # step days running replication
TUP = "iif(sec_update_date is null,sec_insert_date,sec_update_date)"
XROWS = 10000

AVAILABLE_FIELDS = ['bill_type', 'cust_id', 'cust_parent', 'items_count', 'total_sales_d',
                    'total_sales_h', 'total_exchange_h', 'total_bill_after_disc_h', 'total_disc_percent_h',
                    'total_disc_money_h', 'extra_expenses_h', 'total_bill_after_disc_d', 'cash_h',
                    'loaded_value_contract', 'credit_value_contract', 'cost_d', 'total_local_d',
                    'total_imported_d', 'sec_insert_date_h', 'bill_day', 'employee', 'is_delivery', 'deliv_emp_id',
                    'is_visa', 'deliv_points', 'tup'
                    ]

_logger = logging.getLogger(__name__)


class ExtraVars:
    o_table = None
    sales_fields = None


class ClsReplicatAll(models.TransientModel, ExtraVars):
    _description = 'ClsReplicatAll'
    _name = 'abdin_eplus.replication'
    _inherit = 'ab_eplus_connect'

    date_begin = fields.Date(required=True, default=lambda self: self.get_default_date_range())
    date_end = fields.Date(required=True, default=lambda self: self.get_default_date_range())
    fields_comma_seperated = fields.Char()
    available_fields_html = fields.Html(default=lambda self: self.get_default_available_fields(), readonly=True)
    pull_all_data = fields.Boolean(default=False)
    pull_all_sales_data = fields.Boolean(default=False)
    trans_days_later = fields.Integer()

    def replicate_trans(self):
        with self.connect_eplus(param_str=PARAM_STR) as conn:
            with conn.cursor() as cr:
                for chunk in self.pull_trans(crx=cr):
                    if chunk[0]:
                        self.push_trans(chunk)

                    self.env.cr.commit()

    def get_default_date_range(self):
        row = self.env['abdin_eplus.r_sales_trans_h'].sudo().search([], limit=1, order='sec_insert_date_h desc')
        sec_insert_date_h = row.sec_insert_date_h
        if sec_insert_date_h:
            sec_insert_date_h += datetime.timedelta(days=1)
            return sec_insert_date_h.date()
        return datetime.date.today()

    def get_default_available_fields(self):
        html = "<div class='row'>"
        for fld in AVAILABLE_FIELDS:
            html += """<h1 class='col-md-4 h4'>%s</h1>
            """ % fld
        html += "</div>"
        return html

    ###################################################################################
    def get_sales_fields(self):
        # Get string seperated by comma from user then split()
        if self.fields_comma_seperated:
            fields_for_update = self.fields_comma_seperated.split(',')
            # Check if field is available
            for fld in fields_for_update:
                if fld not in AVAILABLE_FIELDS:
                    raise UserError('Not Available Field')
        else:
            fields_for_update = AVAILABLE_FIELDS

        # DO NOT UPDATE OR INSERT 'tup' IF REPLICATION IS MANUALLY
        if 'tup' in fields_for_update and self.date_begin:
            fields_for_update.remove('tup')

        self.sales_fields = ['sto_id', 'sth_id'] + fields_for_update

    ###################################################################################
    def replicate_abdin_eplus(self, x_days_later=None):
        start = time.perf_counter()
        try:
            today = datetime.date.today()
            self.get_sales_fields()
            # This if condition when we do replicate from interface
            if self.date_begin:
                date_begin = self.date_begin
                date_end = self.date_end + datetime.timedelta(days=1) - datetime.timedelta(seconds=0.01)
                for chunk in self.pull_sales((date_begin.isoformat(), date_end.isoformat())):
                    self.push_sales(chunk)
                    self.invalidate_model()
                    self.env.cr.commit()
            elif x_days_later:
                date_begin = today - datetime.timedelta(days=x_days_later)
                date_end = today + datetime.timedelta(days=1)
                for chunk in self.pull_sales((date_begin.isoformat(), date_end.isoformat()), x_days_later):
                    self.push_sales(chunk)
                    self.invalidate_model()
                    self.env.cr.commit()


            else:
                date_begin = today - datetime.timedelta(days=3605)
                date_end = today + datetime.timedelta(days=1)
                for chunk in self.pull_sales((date_begin, date_end)):
                    self.push_sales(chunk)
                    self.env.cr.commit()
                    self.invalidate_model()
                    self.env.cr.commit()
            # self.replicate_delivery_points_data()

        except Exception as e:
            raise UserError(f"Replicate ePlus Error:\n {repr(e)}")
        finally:
            end = time.perf_counter()
            pass

    ###################################################################################
    def replicate_tables(self):
        try:
            with self.connect_eplus(param_str=PARAM_STR) as conn_main:
                with conn_main.cursor() as cr_main:
                    cr_main.execute("""
                            SET TRANSACTION ISOLATION LEVEL SNAPSHOT;
                    """)

                    for table in TABLES:
                        _logger.info(f"###### replicating table: {table} ##########")
                        o_fields = table.get('o_fields')
                        table_name = table.get('t_name')
                        bconn_fields = self.get_bconn_fields(o_fields)
                        sql = self.get_sql(table_name, bconn_fields)
                        self.o_table = self.env['abdin_eplus.%s' % table_name].sudo()

                        # msg = 'Push (%s) Into Online Server %s records...' % (table_name, no_of_rows)
                        empty_table = self.o_table.search_count([]) == 0
                        for chunk in self.pull_data(sql, table_name, crx=cr_main):
                            if chunk[0]:
                                self.push_data(table_name, o_fields, chunk, empty_table)
                            self.env.cr.commit()

        except Exception as e:
            raise UserError(repr(e))

    ###################################################################################

    def replicate_purchase(self):
        try:
            with self.connect_eplus(param_str=PARAM_STR) as conn_main:
                with conn_main.cursor() as crx:
                    crx.execute("""
                            SET TRANSACTION ISOLATION LEVEL SNAPSHOT;
                    """)
                    for table in PURCHASE_TABLES:
                        o_fields = table.get('o_fields')
                        table_name = table.get('t_name')
                        bconn_fields = self.get_bconn_fields(o_fields)
                        sql = self.get_sql(table_name, bconn_fields)
                        self.o_table = self.env['abdin_eplus.%s' % table_name].sudo()

                        # msg = 'Push (%s) Into Online Server %s records...' % (table_name, no_of_rows)
                        empty_table = self.o_table.search_count([]) == 0
                        for chunk in self.pull_data(sql, table_name, crx=crx):
                            if chunk[0]:
                                self.push_data(table_name, o_fields, chunk, empty_table)

                            self.env.cr.commit()

        except Exception as e:
            raise UserError(repr(e))

    ###################################################################################
    def get_where_condition(self, table_name, count_only=False):
        if table_name == 'pur_trans_d':

            where_condition = f"WHERE {TUP} > {PARAM_STR} and sec_insert_date>='2023-01-01'"
        else:
            where_condition = f"WHERE {TUP} > {PARAM_STR}"
        if not count_only:
            where_condition += f" ORDER BY {TUP}"

        return where_condition

    ###################################################################################
    def get_bconn_fields(self, o_fields=None):
        bconn_fields = o_fields.copy()
        # change last field(tup) to (sql iif statement)
        bconn_fields[-1] = TUP
        # change first field(id) to (b-connect-id)
        bconn_fields[0] = o_fields[1]
        return bconn_fields

    ###################################################################################
    def get_sql(self, table_name, fields):
        where_condition = self.get_where_condition(table_name)
        sql = """SELECT {fields}
            from {table_name}
            {where_condition}
             """.format(fields=','.join(fields), table_name=table_name,
                        where_condition=where_condition)
        return sql

    ###################################################################################
    def get_rows_count(self, table_name, crx):
        where_condition = self.get_where_condition(table_name, True)
        # sql string
        sql = """
            select count(*)
            from {table_name}
            {where_condition}
            """.format(table_name=table_name, where_condition=where_condition)
        crx.execute(sql, self.get_last_tup_tuple())
        return crx.fetchone()[0]

    ###################################################################################
    def get_last_tup_tuple(self):
        last_tup = datetime.datetime(1970, 1, 1)
        if not self.pull_all_data:
            last_rec = self.o_table.search([('tup', '!=', False)], order='tup desc', limit=1)
            last_tup = last_rec.tup or datetime.datetime(1970, 1, 1)

        return (last_tup,)

    ###################################################################################
    def pull_data(self, sql, table_name, crx):
        try:
            crx.execute(sql, self.get_last_tup_tuple())  # make like qd.Execute

            rows_count = self.get_rows_count(table_name, crx)
            crx.execute(sql, self.get_last_tup_tuple())  # make like qd.Execute
            msg = "Pull (%s) From Local Server" % table_name
            for __ in self.web_progress_iter(range(0, rows_count, XROWS), msg=msg):
                yield crx.fetchmany(XROWS)

        except Exception as e:
            raise UserError(repr(e))
        # return my_data  # Put the query in my_data list also like rs.OpenRecordset

    ###################################################################################
    def push_data(self, table_name, o_fields, my_data, empty_table=False):
        i = 0
        o_fields_updated = o_fields.copy()
        o_fields_updated.pop(0)
        try:
            for acc in my_data:
                try:
                    if not empty_table and self.o_table.search_count([('id', '=', acc[0])]) > 0:

                        updated_field = ",".join([f"{fld}=%s" for fld in o_fields_updated])

                        sql = """
                            UPDATE abdin_eplus_{table_name} SET {updated_field}
                             WHERE id=%s
                            """.format(table_name=table_name, updated_field=updated_field, )
                        acc = acc[1:]
                        acc += (acc[0],)

                        self.env.cr.execute(sql, acc)
                    else:
                        sql = """
                            insert into abdin_eplus_{table_name}({fields})
                            VALUES({values})
                            """.format(table_name=table_name, fields=','.join(o_fields),
                                       values=','.join(["%s"] * len(acc)))
                        self.env.cr.execute(sql, tuple(acc))

                except  Exception as e:
                    raise UserError(repr(e))

                i = i + 1
        except Exception as e:
            raise Exception(e)

    ###################################################################################
    def pull_sales(self, between_dates, x_days_later=None):
        # get sales_fields if no comma seperated then will be global variable ['sto_id', 'sth_id'] + AVAILABLE_FIELDS
        if 'tup' in self.sales_fields and x_days_later:
            self.sales_fields.remove('tup')

        sales_fields = self.sales_fields

        # اضافة ساعتين فروق توقيت قاهرة عن جرينيتش واستبدال حقل تاريخ الادخال
        sales_fields = ['dateadd(hour,-2,sec_insert_date_h)'
                        if fld == 'sec_insert_date_h' else fld
                        for fld in sales_fields]

        # turn tup to integer before insert or update from odoo import api, fields, models
        sales_fields = ['tup * 1'
                        if fld == 'tup' else fld
                        for fld in sales_fields]

        sql_for_select = ','.join(sales_fields)

        last_tup = 0
        if not self.date_begin and not x_days_later:
            last_tup = self.env['abdin_eplus.r_sales_trans_h'].sudo().search(
                [('tup', '!=', False)], order='tup desc', limit=1).tup

        where_condition = f" WHERE tup> convert(binary(8),{PARAM_STR})"
        sql = f"SELECT {sql_for_select} FROM fn_sales_odoo({PARAM_STR},{PARAM_STR})  {where_condition} order by tup"

        sql_rows_count = f"SELECT COUNT(*) FROM fn_sales_odoo({PARAM_STR},{PARAM_STR}) {where_condition}"

        try:
            with self.connect_eplus(param_str=PARAM_STR) as cnx:
                with cnx.cursor() as crx:
                    crx.execute("""
                            SET TRANSACTION ISOLATION LEVEL SNAPSHOT;
                    """)

                    # may resolve deadlock
                    crx.execute("select top 1 * from r_sales_trans_h")
                    crx.execute("select top 1 * from r_sales_trans_d")

                    # get rows count where
                    crx.execute(sql_rows_count, between_dates + (last_tup,))
                    rows_count = crx.fetchone()[0]
                    crx.execute(sql, between_dates + (last_tup,))
                    msg = "Pull Sales From Local Server"
                    # rows_count + XROWS -> so that if count was old, fetchmany will fetch all new records
                    for i in self.web_progress_iter(range(0, rows_count, XROWS), msg=msg):
                        yield crx.fetchmany(XROWS)

        except Exception as e:
            cnx.rollback()
            raise UserError(e)
        # return my_data  # Put the query in my_data list also like rs.OpenRecordset

    ###################################################################################
    def push_sales(self, my_data):
        sales_fields = self.sales_fields
        # ربط حقول البيع بالكوما
        sql_for_insert = ','.join(sales_fields)

        # نسخ حقول البيع ثم ازالة المخزن ورقم الفاتورة ثم ربطها بالكوما
        updated_field = sales_fields.copy()
        updated_field = updated_field[2:]
        sql_for_update = ",".join([f"{fld}=%s" for fld in updated_field])

        i = 0
        try:
            for acc in self.web_progress_iter(my_data, msg='Push Sales Into Odoo Server'):
                acc = tuple(acc)

                # طريقة اودوو بطيئة
                # do_update = self.r_sales_trans_h.search_count(
                #     [('sto_id', '=', acc[0]), ('sth_id', '=', acc[1]), ]) > 0

                # CRITICAL --> DO NOT CHANGE THIS --> enforce update only if fields_comma_seperated is defined
                if self.fields_comma_seperated:
                    do_update = [1]
                else:
                    sql = "select 1 from abdin_eplus_r_sales_trans_h where sto_id=%s and sth_id=%s"
                    self.env.cr.execute(sql, (acc[0], acc[1]))
                    do_update = self.env.cr.fetchone()

                if do_update and do_update[0]:
                    sql = f"""UPDATE abdin_eplus_r_sales_trans_h
                    SET  {sql_for_update} WHERE sto_id=%s and sth_id=%s"""
                    acc += (acc[0], acc[1],)
                    acc = acc[2:]
                    self.env.cr.execute(sql, acc)

                # if not do_update then insert
                else:
                    values = ','.join(['%s'] * len(acc))
                    sql = f"""
                        INSERT INTO abdin_eplus_r_sales_trans_h ({sql_for_insert}) VALUES({values})"""
                    self.env.cr.execute(sql, acc)

                i = i + 1

        except Exception as e:
            self.env.cr.rollback()
            raise UserError(repr(e))

    ###################################################################################
    def pull_trans(self, crx):
        try:
            trans_days_later = self.trans_days_later or TRANS_DAYS_LATER
            trans_fields = ','.join(TRANSFER_TABLE_FIELDS)
            sql_for_count = f"""SELECT COUNT(*)
                from Store_Trans_h where sec_insert_date >= GETDATE() - {trans_days_later}
                """
            crx.execute(sql_for_count)
            rows_count = crx.fetchone()[0]

            sql = f"""SELECT {trans_fields}
                from Store_Trans_h where sec_insert_date >= GETDATE() - {trans_days_later}
                """
            crx.execute(sql)
            msg = "Pull Trans From Local Server"
            for __ in self.web_progress_iter(range(0, rows_count, XROWS), msg=msg):
                yield crx.fetchmany(XROWS)

        except Exception as e:
            raise UserError(e)

    ###################################################################################
    def push_trans(self, my_data):
        sql_for_update = ",".join([f"{fld}=%s" for fld in TRANSFER_TABLE_FIELDS])
        trans_fields = ','.join(TRANSFER_TABLE_FIELDS)
        try:
            for acc in my_data:
                try:
                    self._cr.execute(f"""select 1 
                    from abdin_eplus_store_trans_h WHERE stnh_id={acc[0]} and stnh_f_sto_id={acc[1]} """)
                    found = self._cr.fetchone()
                    if found and found[0]:
                        trans_id = acc[0]
                        from_store = acc[1]
                        sql = f"""
                            UPDATE abdin_eplus_store_trans_h SET {sql_for_update}
                             WHERE stnh_id=%s and stnh_f_sto_id=%s
                            """

                        self.env.cr.execute(sql, tuple(acc) + (trans_id, from_store))
                    else:
                        sql = f"""
                            insert into abdin_eplus_store_trans_h({trans_fields})
                            VALUES({','.join(["%s"] * len(acc))})
                            """
                        self.env.cr.execute(sql, tuple(acc))

                except  Exception as e:
                    raise UserError(e)

        except Exception as e:
            raise Exception(e)
