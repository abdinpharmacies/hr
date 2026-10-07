# -*- coding: utf-8 -*-

from odoo import api, models, _
from odoo.exceptions import UserError, ValidationError




class AbSalesPosCustomerApi(models.TransientModel):
    _name = 'ab_sales_pos_api'
    _inherit = ["ab_sales_pos_api"]

    @staticmethod
    def _normalize_phone(phone):
        return (phone or "").strip()

    @staticmethod
    def _is_valid_phone(phone):
        phone = (phone or "").strip()
        if len(phone) != 11:
            return False
        if not phone.isdigit():
            return False
        return phone.startswith(("010", "011", "012", "015"))

    @staticmethod
    def _is_valid_name(name):
        name = (name or "").strip()
        if not name:
            return False
        if " " not in name:
            return False
        return len(name.replace(" ", "")) >= 4

    @staticmethod
    def _is_valid_address(address):
        return len((address or "").strip()) >= 3

    def _validate_new_customer_payload(self, phone=None, name=None, address=None):
        self._require_models("ab_sales_header")
        vals = {
            "new_customer_name": (name or "").strip(),
            "new_customer_phone": self._normalize_phone(phone),
            "new_customer_address": (address or "").strip(),
        }
        header = self.env["ab_sales_header"].new(vals)
        if not header._validate_new_customer():
            raise UserError(_("Customer name, phone and address are required."))
        return {
            "phone": vals["new_customer_phone"],
            "name": vals["new_customer_name"],
            "address": vals["new_customer_address"],
        }


    @staticmethod
    def _customer_payload(customer):
        return {
            "id": customer.id,
            "name": customer.name or "",
            "code": customer.code or "",
            "mobile_phone": customer.mobile_phone or "",
            "work_phone": customer.work_phone or "",
            "address": customer.address or "",
            "eplus_serial": customer.eplus_serial or 0,
        }


    @api.model
    def pos_validate_new_customer(self, phone=None, name=None, address=None):
        self._validate_new_customer_payload(phone=phone, name=name, address=address)
        return True
