import itertools

import datetime

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

PAID_POINTS_VALUE = 5.0


class AbStore(models.Model):
    _name = 'ab_store'
    _inherit = 'ab_store'

    max_trans_value = fields.Float()


class DeliveryPointsWizard(models.Model):
    _name = 'ab_delivery_points_wizard'
    _description = 'ab_delivery_points_wizard'

    till_date = fields.Date(required=True)
    delivery_ids = fields.Many2many('ab_hr_employee', string='Delivery Employees')
    msg_html = fields.Html(readonly=True)

    @api.constrains('till_date')
    def _constraint_ab_delivery_points_wizard(self):
        for rec in self:
            if rec.till_date > datetime.date.today():
                raise ValidationError(_("End date must not be greater than today!"))

    def btn_get_delivery_points(self):
        till_date = self.till_date or datetime.date.today().replace(day=20)
        self._get_delivery_points(till_date)

    def _get_delivery_points(self, till_date):
        """
        1. Insert into sales (abdin_eplus_r_sales_trans_h) paid_points
        2. Get last_tup from sales
        3. Insert (total_paid_points, last_tup, employee_id, employee_code) in ab_delivery_points_payroll
        """
        cr = self.env.cr

        sales_ids = self._get_sales_ids(cr, till_date)
        if sales_ids:
            self._add_delivery_points_to_payroll(cr, till_date, sales_ids)
            self._add_as_paid(sales_ids)
            self.msg_html = "<span class='text-success h4'>Delivery Points Added Successfully.</span>"
        else:
            self.msg_html = "<span class='text-danger h4'>No Delivery Points To Add.</span>"

    def _get_sales_ids(self, cr, till_date):
        and_cc_code_in_delivery_codes = ""
        if self.delivery_ids:
            delivery_codes_list = [f"'{dlv.costcenter_id.code}'" for dlv in self.delivery_ids if dlv.costcenter_id]
            delivery_codes = ",".join(delivery_codes_list)
            and_cc_code_in_delivery_codes = f"and cc.code in ({delivery_codes})" if delivery_codes else ""

        cr.execute(f"""SELECT ss.id
            FROM abdin_eplus_r_sales_trans_h ss
            join abdin_eplus_employee ee on ss.deliv_emp_id = ee.e_id
            join ab_costcenter cc on cc.code = REPLACE(ee.e_code, '*', '')
            join ab_hr_employee hr on cc.id = hr.costcenter_id  
                where ss.is_delivery=True 
                and ss.bill_day<=%(till_date)s 
                and ss.bill_day>='2023-04-01'
                and abs(COALESCE( ss.deliv_points ,0)- COALESCE( ss.paid_points, 0)) > 0.01 
                {and_cc_code_in_delivery_codes}
        """, {'till_date': till_date, })
        sales_ids = [pt[0] for pt in cr.fetchall()]
        return sales_ids

    def _add_delivery_points_to_payroll(self, cr, till_date, sales_ids):
        paid_employees = set()
        delivery_payroll = self.env['ab_delivery_points_payroll'].sudo()
        self.flush_model()
        cr.execute(f"""
        SELECT 
            deliv_emp_id,
            sto_id,
            sum(COALESCE(deliv_points,0) - COALESCE(paid_points,0)),
            count(id),            
            max(tup)
        FROM abdin_eplus_r_sales_trans_h
        where id in ({','.join(['%s'] * len(sales_ids))})
        GROUP BY deliv_emp_id,sto_id
        """, tuple(sales_ids))
        data = cr.fetchall()

        for row in data:
            e_code = self.env['abdin_eplus.employee'].sudo().browse(row[0]).e_code

            employee = self.env['ab_hr_employee'].search([('costcenter_id.code', '=', str(e_code).replace('*', ''))],
                                                         limit=1)

            store_code = self.env['abdin_eplus.store'].sudo().browse(row[1]).sto_code
            store = self.env['ab_store'].search([('code', '=', store_code)])

            total_points = row[2]
            orders_count = row[3]
            max_tup = row[4]
            if employee:
                paid_employees.add(employee.costcenter_id.code)

                delivery_payroll.create({
                    'employee_id': employee.id,
                    'store_id': store.id,
                    'due_date': till_date.replace(day=1),
                    'section': 154,  # حوافز نقاط الدليفلرية
                    'section_value': total_points,
                    'status': 'for_manager',
                    'payment_type_id': 1,  # salary
                    'orders_count': orders_count,
                    'last_tup': max_tup,
                })
        return paid_employees

    def _add_as_paid(self, sales_ids):
        sales = self.env['abdin_eplus.r_sales_trans_h'].sudo()
        sales_rs = sales.browse(sales_ids)
        # set paid_points after fetching data
        for pt in sales_rs:
            pt.paid_points = pt.deliv_points

    #########################################
    #########################################
    def btn_get_delivery_trans_points(self):
        till_date = self.till_date or datetime.date.today().replace(day=20)
        self._get_delivery_trans_points(till_date)

    def _get_delivery_trans_points(self, till_date):
        """
        1. Insert into trans (abdin_eplus.store_trans_h) paid_points
        3. Insert (total_paid_points, last_tup, employee_id, employee_code) in ab_delivery_points_payroll
        """
        cr = self.env.cr

        trans_ids = self._get_trans_ids(cr, till_date)
        if trans_ids:
            self._add_delivery_trans_points(cr, till_date, trans_ids)
            self._add_trans_as_paid(trans_ids)
            self.msg_html = "<span class='text-success h4'>Delivery Transfer Points Added Successfully.</span>"
        else:
            self.msg_html = "<span class='text-danger h4'>No Delivery Transfer Points To Add.</span>"

    def _get_trans_ids(self, cr, till_date):
        and_cc_code_in_delivery_codes = ""
        if self.delivery_ids:
            delivery_codes_list = [f"'{dlv.costcenter_id.code}'" for dlv in self.delivery_ids if dlv.costcenter_id]
            delivery_codes = ",".join(delivery_codes_list)
            and_cc_code_in_delivery_codes = f" and cc.code in ({delivery_codes})" if delivery_codes else ""

        cr.execute(f"""SELECT ss.id
            FROM abdin_eplus_store_trans_h ss
            join abdin_eplus_employee ee on ss.delivery_emp = ee.e_id
            join ab_costcenter cc on cc.code = REPLACE(ee.e_code, '*', '')
            join ab_hr_employee hr on cc.id = hr.costcenter_id  
            join abdin_eplus_store e_store on e_store.id = ss.stnh_t_sto_id  
            join ab_store store on store.code = e_store.sto_code  
                where ss.delivery_emp is not Null 
                and store.max_trans_value != 0
                and ss.sec_insert_date<(%(till_date)s + INTERVAL '1 day') 
                and ss.sec_insert_date>='2023-10-21'
                and abs(COALESCE( ss.paid_points ,0)) < 0.01 
                {and_cc_code_in_delivery_codes}
        """, {'till_date': till_date, })
        trans_ids = [pt[0] for pt in cr.fetchall()]
        return trans_ids

    def _add_delivery_trans_points(self, cr, till_date, trans_ids):
        paid_employees = set()
        delivery_payroll = self.env['ab_delivery_points_payroll'].sudo()
        self.flush_model()
        paid_points_value = PAID_POINTS_VALUE
        cr.execute(f"""
            SELECT 
                delivery_emp,
                stnh_t_sto_id,
                count(id),
                sum(%s) as due_paid_points
            FROM abdin_eplus_store_trans_h
                    WHERE id IN ({','.join(['%s'] * len(trans_ids))}) 
                    AND delivery_emp IS NOT NULL
                    AND COALESCE(paid_points,0)=0
                    GROUP BY delivery_emp,stnh_t_sto_id
                    ORDER BY stnh_t_sto_id
        """, (paid_points_value,) + tuple(trans_ids))
        data = cr.fetchall()

        cr.execute(f"""
            SELECT 
                stnh_t_sto_id,
                sum({PAID_POINTS_VALUE})
            FROM abdin_eplus_store_trans_h
                    WHERE 
                    sec_insert_date >= %(till_date)s   -  INTERVAL '30 day'
                    AND sec_insert_date<(%(till_date)s + INTERVAL '1 day')
                    
                    AND delivery_emp IS NOT NULL
                    and delivery_emp != 1
                    GROUP BY stnh_t_sto_id
                    ORDER BY stnh_t_sto_id
        
        """, {'till_date': till_date})
        store_act_total_points_dict = dict(cr.fetchall())

        for row in data:

            e_code = self.env['abdin_eplus.employee'].sudo().browse(row[0]).e_code

            employee = self.env['ab_hr_employee'].search(
                [('costcenter_id.code', '=', str(e_code).replace('*', ''))],
                limit=1)

            eplus_store_id = row[1]
            store_code = self.env['abdin_eplus.store'].sudo().browse(eplus_store_id).sto_code
            store = self.env['ab_store'].search([('code', '=', store_code)])
            orders_count = row[2]

            employee_act_total_points = row[3]
            store_act_total_points = store_act_total_points_dict.get(eplus_store_id)
            if not store_act_total_points:
                continue

            if not store.max_trans_value:
                raise ValidationError(_("Store must have max transfer value, please set it from accounting stores."))
            ratio = min(1, store.max_trans_value / store_act_total_points)

            employee_final_total_points = (employee_act_total_points * ratio)
            if employee:
                paid_employees.add(employee.costcenter_id.code)

                delivery_payroll.create({
                    'employee_id': employee.id,
                    'store_id': store.id,
                    'due_date': till_date.replace(day=1),
                    'section': 160,  # حوافز تحويلات الدليفلرية
                    'section_value': employee_final_total_points,
                    'status': 'for_manager',
                    'payment_type_id': 1,  # salary
                    'orders_count': orders_count,
                })
        return paid_employees

    def _add_trans_as_paid(self, trans_ids):
        trans = self.env['abdin_eplus.store_trans_h'].sudo()
        trans_rs = trans.browse(trans_ids)
        # set paid_points after fetching data
        for pt in trans_rs:
            pt.paid_points = PAID_POINTS_VALUE


class DeliveryPointsPayroll(models.Model):
    _inherits = {'ab_hr_payroll': 'payroll_id'}
    _name = 'ab_delivery_points_payroll'
    _description = 'ab_delivery_points_payroll'

    payroll_id = fields.Many2one('ab_hr_payroll', delegate=True, required=True, ondelete='restrict')
    orders_count = fields.Integer(required=True)
    order_returned = fields.Boolean(default=False)
    last_tup = fields.Integer(index=True, default=0)
