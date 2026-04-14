from odoo import api, fields, models
from odoo.tools.translate import _


class ProductInherit(models.Model):
    _name = 'ab_product'
    _inherit = 'ab_product'

    eplus_serial = fields.Integer(index=True)

    last_update_date = fields.Datetime(index=True)

    eplus_create_date = fields.Datetime(index=True)

    def qty_from_small(self, qty, unit_size):
        """
         :param unit_size: 'large', 'medium' or 'small'
         :param qty: absolute final inventory quantity
         :return: convert from small qty to other units.
         """
        if not (self and qty and unit_size):
            return 0

        self.ensure_one()
        unit_s_no = self.unit_s_id.unit_no
        unit_m_no = self.unit_m_id.unit_no
        # Cancel This Check
        # if not (qty / unit_m_no).is_integer():
        #     raise ValidationError(_("CONVERTING FROM SMALL ERROR: SMALL QTY INCONSISTENT WITH MEDIUM QTY, "
        #                             "Product ID: %s" % self.id))

        if unit_size == 'large':
            return qty / unit_s_no
        elif unit_size == 'medium':
            return qty * unit_m_no / unit_s_no
        else:  # 'small'
            return qty

    def qty_to_small(self, qty, unit_size):
        """
         :param unit_size: 'large', 'medium' or 'small'
         :param qty: absolute final inventory quantity
         :return: convert qty from other units to small.
         """
        if not (self and qty and unit_size):
            return 0

        self.ensure_one()
        unit_s_no = self.unit_s_id.unit_no
        unit_m_no = self.unit_m_id.unit_no
        # Cancel this check
        # if abs(int((qty * unit_m_no)) - qty * unit_m_no) > 0.1:
        #     raise ValidationError(_("CONVERTING TO SMALL ERROR: SMALL QTY INCONSISTENT WITH MEDIUM QTY, "
        #                             "Product ID: %s" % self.id))

        if unit_size == 'large':
            qty_in_small = qty * unit_s_no
        elif unit_size == 'medium':
            qty_in_small = (qty * unit_s_no) / unit_m_no
        else:
            qty_in_small = qty

        # @todo FIX this
        qty_in_small = round(qty_in_small)

        return qty_in_small


class ProductCardInherit(models.Model):
    _name = 'ab_product_card'
    _inherit = 'ab_product_card'

    eplus_serial = fields.Integer(index=True)
    last_update_date = fields.Datetime(index=True)
