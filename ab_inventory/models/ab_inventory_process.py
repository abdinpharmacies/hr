from odoo import api, fields, models
from odoo.tools.translate import _
from odoo.exceptions import ValidationError


class InventoryProcess(models.AbstractModel):
    _name = 'ab_inventory_process'
    _description = 'ab_inventory_process'

    def inventory_write(self, rec, qty, store_id, inventory_line=None,
                        status='pending_main',
                        sign=1):
        """
        :param rec: must have attributes
            1. source_id
            1. source_id.product_id related field
        :param qty: absolute final inventory quantity
        :param sign: 1 for inventory increase, -1 for decrease
        :param store_id: store_id of header except for transfer (from_store_id , to_store_id)
        :param inventory_line: if None -> create, else -> write
        :param status: not pending if write (not create) inventory or opening balance
        :return: on creation returns new record id, on write returns None
        """

        if rec._name == 'ab_purchase_line':
            header_ref = f"P{rec.header_id.id}"
        elif rec._name == 'ab_purchase_notice_line':
            header_ref = f"PN{rec.header_id.id}"
        elif rec._name == 'ab_purchase_ob_line':
            header_ref = f"OB{rec.header_id.id}"
        elif rec._name == 'ab_sales_line':
            header_ref = f"S{rec.header_id.id}"
        elif rec._name == 'ab_sales_return_line':
            header_ref = f"SN{rec.header_id.id}"
        elif rec._name == 'ab_transfer_line':
            header_ref = f"T{rec.header_id.id}"
        else:
            header_ref = f"OTHER{rec.id}"
        inventory_header_mo = self.env['ab_inventory_header'].sudo()
        header_id = inventory_header_mo.search([('header_ref', '=', header_ref)]).id
        if not header_id:
            header_id = inventory_header_mo.create({
                'header_ref': header_ref,
                'store_id': store_id,
                'model_ref': getattr(rec.header_id, '_name', None),
                'res_id': rec.header_id.id,
            }).id

        qty_s_unit = rec.product_id.qty_to_small(qty, rec.uom_id.unit_size)

        inventory_dict = {
            'source_id': rec.source_id.id,
            'qty': qty_s_unit * sign,
            'store_id': store_id or 78,
            'model_ref': rec._name,
            'res_id': rec.id,
            'status': status,
            'header_ref': header_ref,
            'header_id': header_id,
        }
        if inventory_line:
            inventory_line.write(inventory_dict)
        else:
            inventory = self.env['ab_inventory'].sudo()
            return inventory.create(inventory_dict)

    def change_inventory_status(self, status):
        self.status = status
