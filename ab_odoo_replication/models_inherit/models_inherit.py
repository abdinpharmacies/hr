from odoo import api, models
from odoo.exceptions import ValidationError
from odoo.tools import config

IS_CONTROL_SERVER = config.get('is_control_server')


class IgnoreWriteDateUpdate(models.AbstractModel):
    _name = 'ignore_write_date_update'
    _description = 'ignore_write_date_update'

    def _ignore_write_date_update(self, values):
        curr_write_date = self.read(['write_date'])
        res = super().write(values)
        if curr_write_date:
            curr_write_date = self.read(['write_date'])[0]['write_date']
            self.env.cr.execute(f"UPDATE {self._table} SET write_date = %s WHERE id = %s", (curr_write_date, self.id))
        return res


class AbOdooReplicationOnlyAllowed(models.AbstractModel):
    _name = 'ab_odoo_replication_only_allowed'
    _description = 'ab_odoo_replication_only_allowed'
    _inherit = 'ignore_write_date_update'

    @api.model
    def create(self, values):
        raise ValidationError("This is Replication Database.\nThis Operation is 'Not Valid'.")

    def unlink(self):
        raise ValidationError("This is Replication Database.\nThis Operation is 'Not Valid'.")

    def write(self, values):
        if self.env.context.get('replication'):
            return self._ignore_write_date_update(values)
        raise ValidationError("This is Replication Database.\nThis Operation is 'Not Valid'.")


class Costcenter(models.Model):
    _name = 'ab_costcenter'
    _inherit = ['ab_costcenter', 'ab_odoo_replication_only_allowed']


class Store(models.Model):
    _name = 'ab_store'
    _inherit = ['ab_store', 'ab_odoo_replication_only_allowed']


class HrRegion(models.Model):
    _name = 'ab_hr_region'
    _inherit = ['ab_hr_region', 'ab_odoo_replication_only_allowed']


class HrJob(models.Model):
    _name = 'ab_hr_job'
    _inherit = ['ab_hr_job', 'ab_odoo_replication_only_allowed']


class HrDepartment(models.Model):
    _name = 'ab_hr_department'
    _inherit = ['ab_hr_department', 'ab_odoo_replication_only_allowed']


class HrEmployee(models.Model):
    _name = 'ab_hr_employee'
    _inherit = ['ab_hr_employee', 'ab_odoo_replication_only_allowed']


class ProductCompany(models.Model):
    _name = 'ab_product_company'
    _inherit = ['ab_product_company', 'ab_odoo_replication_only_allowed']


class ProductOrigin(models.Model):
    _name = 'ab_product_origin'
    _inherit = ['ab_product_origin', 'ab_odoo_replication_only_allowed']


class ProductGroup(models.Model):
    _name = 'ab_product_group'
    _inherit = ['ab_product_group', 'ab_odoo_replication_only_allowed']


class UsageCauses(models.Model):
    _name = 'ab_usage_causes'
    _inherit = ['ab_usage_causes', 'ab_odoo_replication_only_allowed']


class UsageManner(models.Model):
    _name = 'ab_usage_manner'
    _inherit = ['ab_usage_manner', 'ab_odoo_replication_only_allowed']


class ProductCard(models.Model):
    _name = 'ab_product_card'
    _inherit = ['ab_product_card', 'ab_odoo_replication_only_allowed']


class UomType(models.Model):
    _name = 'ab_uom_type'
    _inherit = ['ab_uom_type', 'ab_odoo_replication_only_allowed']


class Uom(models.Model):
    _name = 'ab_uom'
    _inherit = ['ab_uom', 'ab_odoo_replication_only_allowed']


# class ProductBarcode(models.Model):
#     _name = 'ab_product_barcode'
#     _inherit = ['ab_product_barcode', 'ab_odoo_replication_only_allowed']


class Product(models.Model):
    _name = 'ab_product'
    _inherit = ['ab_product', 'ab_odoo_replication_only_allowed']

    #
    # @api.model
    # def create(self, values):
    #     raise ValidationError("This is Replication Database.\nThis Operation is 'Not Valid'.")
    #
    # def unlink(self):
    #     raise ValidationError("This is Replication Database.\nThis Operation is 'Not Valid'.")
    #
    # def write(self, values):
    #     if self.env.context.get('replication') or 'barcode_ids' in values or self.env.user.id == 1:
    #         return self._ignore_write_date_update(values)
    #
    #     raise ValidationError("This is Replication Database.\nThis Operation is 'Not Valid'.")


# class ResUsers(models.Model):
#     _name = 'res.users'
#     _inherit = ['res.users', 'ignore_write_date_update']
#
#     def unlink(self):
#         raise ValidationError("Not Valid")
#
#     def write(self, values):
#         return self._ignore_write_date_update(values)


# class ResPartner(models.Model):
#     _name = 'res.partner'
#     _inherit = ['res.partner', 'ignore_write_date_update']
#
#     def unlink(self):
#         raise ValidationError("Not Valid")
#
#     def write(self, values):
#         return self._ignore_write_date_update(values)

class AbPromoProgram(models.Model):
    _name = 'ab_promo_program'
    _inherit = ['ab_promo_program']

    @api.model
    def create(self, values):
        if self.env.context.get('replication') or IS_CONTROL_SERVER:
            return super().create(values)

        raise ValidationError("This is Replication Database.\nThis Operation is 'Not Valid'.")

    def unlink(self):
        if self.env.context.get('replication') or IS_CONTROL_SERVER:
            return super().unlink()
        raise ValidationError("This is Replication Database.\nThis Operation is 'Not Valid'.")

    def write(self, values):
        if self.env.context.get('replication') or IS_CONTROL_SERVER:
            return super().write(values)

        raise ValidationError("This is Replication Database.\nThis Operation is 'Not Valid'.")
