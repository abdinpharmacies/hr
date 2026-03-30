from odoo import api, fields, models
from odoo.tools.translate import _
from odoo.exceptions import ValidationError

PARAM_STR = '%s'


class InventoryAdjustHeaderPush(models.Model):
    _name = 'ab_inventory_adjust_header'
    _inherit = 'ab_inventory_adjust_header'

    def _get_emp_code(self):
        linked_employees = self.env.user.ab_employee_ids
        employee_code = linked_employees[0].costcenter_id.code if linked_employees else '1'
        return employee_code

    def btn_push_eplus_inventory(self):
        old_qty_dicts = []
        new_qty_dicts = []
        for line in self.line_ids:
            old_qty_dicts.append({'product_id': line.product_id.id, 'qty': line.qty})
        self.btn_get_eplus_inventory()
        for line in self.line_ids:
            new_qty_dicts.append({'product_id': line.product_id.id, 'qty': line.qty})
            if line.new_qty < 0:
                raise ValidationError(_("Qty is negative Error, Product: %s - Name: %s"
                                        % (line.product_id.code, line.product_id.name)))
        if old_qty_dicts != new_qty_dicts:
            raise ValidationError(_("Qty Changes , Please check again"))

        # self.btn_get_products_details()
        new = False
        if self.eplus_inv_id:
            self._update_adjust_lines()
        else:
            new = True
            self.eplus_inv_id = self._insert_adjust_lines()

        msg = f"""
        <div>Stock Adjustment Document {'Created' if new else 'Updated'}: <span class="text-success">{self.eplus_inv_id}</span></div> 
        """
        return self.ab_msg(title="Done", message=msg)

    def _update_adjust_lines(self):
        store_ip = self.store_id.ip2 if self.adjust_type == 'main_adjust' else self.store_id.ip1
        with self.connect_eplus(server=store_ip, param_str=PARAM_STR) as conn:
            with conn.cursor() as cr:
                sql_inv_h = f"SELECT inv_flag FROM inventory_h WHERE inv_id={PARAM_STR}"
                cr.execute(sql_inv_h, (self.eplus_inv_id,))
                inv_h_status = cr.fetchone()
                if inv_h_status:
                    if inv_h_status[0] != 'P':
                        raise ValidationError(_("Document is not pending anymore!"))
                else:
                    raise ValidationError(_("Document does not exist!"))

                self._delete_all_adjust_lines(cr)
                for line in self.line_ids:
                    self._insert_adjust_line(cr, self.eplus_inv_id, line)
                    self._update_inventory_price(cr, line)

    def _delete_all_adjust_lines(self, cr):
        sql = f"""
        DELETE FROM inventory_d  
        WHERE invd_inv_id = {int(self.eplus_inv_id)}
        """
        cr.execute(sql)

    def _update_adjust_line(self, cr, line):
        sql_invd = f"""
        UPDATE Inventory_d set 
                        invd_old_qty={PARAM_STR}, 
                        invd_new_qty={PARAM_STR},
                        invd_sell_price={PARAM_STR}
                        where invd_inv_id={PARAM_STR} and invd_itm_id={PARAM_STR} and invd_c_id={PARAM_STR}
                        ;
        """

        cr.execute(sql_invd, (line.qty,
                              line.new_qty,
                              line.new_sell_price,
                              self.eplus_inv_id,
                              line.product_id.eplus_serial,
                              line.c_id,
                              ))

    def _check_adjust_line_exists(self, cr, line):
        sql_invd = f"""
        SELECT 1 FROM  Inventory_d 
        WHERE invd_inv_id={PARAM_STR} and invd_itm_id={PARAM_STR} and invd_c_id={PARAM_STR}                ;
        """

        cr.execute(sql_invd,
                   (self.eplus_inv_id,
                    line.product_id.eplus_serial,
                    line.c_id,)
                   )
        if cr.fetchone():
            return True
        else:
            return False

    def _get_employee_id(self, cr):
        employee_code = self._get_emp_code()
        sql_emp = f"SELECT ISNULL((SELECT e_id FROM employee WHERE e_code={PARAM_STR}),1)"
        cr.execute(sql_emp, (employee_code,))
        employee_id = cr.fetchone()
        return employee_id

    def _create_and_get_invd_inv_id(self, cr):
        employee_id = self._get_employee_id(cr)
        formatted_date = self.create_date.strftime('%Y-%m-%d %H:%M:%S')
        sql_header = f"""INSERT INTO Inventory_h (inv_sto_id, inv_begin_time, inv_no_items, inv_flag, inv_notes, sec_insert_uid) OUTPUT Inserted.[inv_id]
                        VALUES ({PARAM_STR}, {PARAM_STR}, {PARAM_STR}, 'P', {PARAM_STR}, {PARAM_STR})"""

        cr.execute(sql_header,
                   (self.store_id.eplus_serial, formatted_date, len(self.line_ids), self.description,
                    employee_id))
        invd_inv_id = cr.fetchone()[0]
        return invd_inv_id

    @staticmethod
    def _get_invd_id(cr, invd_inv_id):
        sql = f"select isnull((select max(invd_id) + 1  from inventory_d where invd_inv_id={PARAM_STR}),1)"
        cr.execute(sql, (invd_inv_id,))
        return cr.fetchone()[0]

    def _insert_adjust_lines(self):
        store_ip = self.store_id.ip2 if self.adjust_type == 'main_adjust' else self.store_id.ip1
        with self.connect_eplus(store_ip, param_str=PARAM_STR) as conn:
            with conn.cursor() as cr:
                invd_inv_id = self._create_and_get_invd_inv_id(cr)

                for line in self.line_ids:
                    self._insert_adjust_line(cr, invd_inv_id, line)
                    self._update_inventory_price(cr, line)

                return invd_inv_id

    def _insert_adjust_line(self, cr, invd_inv_id, line):
        employee_id = self._get_employee_id(cr)
        formatted_date = self.create_date.strftime('%Y-%m-%d %H:%M:%S')

        adjust_sql = f"""
        INSERT INTO Inventory_d (invd_id, invd_inv_id, invd_itm_id, invd_c_id, invd_itm_unit, 
                        invd_old_qty, invd_new_qty,invd_old_exp_date, invd_new_exp_date, 
                        invd_sell_price, invd_pharm_price, invd_tax, 
                        sec_insert_uid,sec_insert_date)
                        VALUES ({','.join(['%s'] * 14)});
        """

        invd_id = self._get_invd_id(cr, invd_inv_id)

        cr.execute(adjust_sql,
                   (invd_id, invd_inv_id, line.product_id.eplus_serial, line.c_id, '1', line.qty,
                    line.new_qty, line.itm_expiry_date, line.itm_expiry_date, line.sell_price,
                    line.pharm_price, line.sell_tax, employee_id, formatted_date))

    @staticmethod
    def _update_inventory_price(cr, line):
        inventory_sql = f"""update Item_Class_Store set
                                    sell_price={PARAM_STR},
                                    sec_update_date=getdate()
                                FROM Item_Class_Store ics
                                where ics.c_id={PARAM_STR} and ics.sto_id={PARAM_STR} and ics.itm_id={PARAM_STR}"""

        cr.execute(inventory_sql,
                   (line.new_sell_price, line.c_id,
                    line.header_id.store_id.eplus_serial,
                    line.product_id.eplus_serial))
