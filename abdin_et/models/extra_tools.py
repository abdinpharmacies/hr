from odoo import models, api
import unicodedata
import re
import datetime
from .tafqit import convert_number


class ExtraTools(models.AbstractModel):
    _name = 'abdin_et.extra_tools'
    _description = 'Extra Tools'

    # الدالة الرئيسية للتقفيط
    @api.model
    def tafqit(self, amount):
        """
        تحويل مبلغ رقمي إلى صيغة التقفيط باللغة العربية.
        مثال:
            tafqit(485.55)
        يُرجع:
            "فقط أربعمائة وخمسة وثمانون جنيها وخمسة وخمسون قرشا لا غير"
        """
        # فصل الجزء الصحيح عن الجزء العشري (القرش)
        int_part = int(amount)
        frac_part = round((amount - int_part) * 100)

        result = "فقط "

        if int_part > 0:
            result += convert_number(int_part) + " جنيها مصريا"

        if frac_part > 0:
            if int_part > 0:
                result += " و"
            result += convert_number(frac_part) + " قرشا"

        result += " لا غير"
        return result

    ##############################################################################################################
    def ab_msg(self, title='Done', message='Done', message_type='html', mode='ok',
               model_name=None, fn_method=None, *args, **kwargs
               ):
        context = dict(self._context or {})
        context[message_type] = message
        context['model_name'] = model_name
        context['mode'] = mode
        context['fn_method'] = fn_method
        context.update(kwargs)

        try:
            view_id = self.env.ref('abdin_et.ab_message_wiz').id
        except ValueError:
            view_id = False

        return {
            'name': title,
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'ab_message_wiz',
            "views": [(view_id, "form")],
            "view_id": view_id,
            'target': 'new',
            "context": context,
        }

    def sh_msg(self, *args, **kw):
        return self.ab_msg(*args, **kw)

    ##############################################################################################################
    @staticmethod
    def notify_user(msg, title="Error", msg_type="danger"):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': title,
                'message': msg,
                'type': msg_type,  # types: success,warning,danger,info
                'sticky': True,  # True/False will display for few seconds if false
            },
        }

    ##############################################################################################################
    @staticmethod
    def slugify(value):
        value = str(value)
        value = unicodedata.normalize('NFKC', value)
        value = re.sub(r'[^\w\s-]', ' ', value.lower())
        return value

    ##############################################################################################################
    @staticmethod
    def get_modified_name(name):
        replacement = 'أإآ'
        for s in replacement:
            name = name.replace(s, 'ا')

        name = name.replace('ؤ', 'و')
        name = name.replace('ى', 'ي')
        name = name.replace('  ', '%')
        return name

    ##############################################################################################################
    @staticmethod
    def last_day_of_month(any_date):
        # this will never fail
        # get close to the end of the month for any day, and add 4 days 'over'
        next_month = any_date.replace(day=28) + datetime.timedelta(days=4)
        # subtract the number of remaining 'overage' days to get last day of current month
        # , or said programmaticaly said, the previous day of the first of next month
        return next_month - datetime.timedelta(days=next_month.day)
