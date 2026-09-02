from odoo import api, models


class AbOdooSyncRules(models.AbstractModel):
    _name = "ab_odoo_sync_rules"
    _description = "AB Odoo Sync Rules"

    _never_mirror_models = frozenset(
        {
            "ab_costcenter",
            "ab_store",
            "ab_replica_db",
            "ab_hr_region",
            "ab_hr_job",
            "ab_hr_department",
            "ab_hr_employee",
            "ab_hr_job_occupied",
            "ab_customer",
            "ab_uom_type",
            "ab_uom",
            "ab_product_uom_category",
            "ab_product_uom",
            "ab_product_card",
            "ab_product",
            "ab_product_barcode",
            "ab_contract",
            "ab_promo_program",
            "ab_employee_access_sales_role",
            "ab_employee_access",
            "ab_doctor",
            "ab_product_metadata",
            "ab_product_company",
            "ab_product_origin",
            "ab_product_group",
            "ab_usage_causes",
            "ab_usage_manner",
            "ab_sales_channel",
        }
    )

    _user_source_model = "res.users"
    _user_mirror_model = "ab_users"

    @api.model
    def never_mirror_models(self):
        return self._never_mirror_models

    @api.model
    def user_source_model(self):
        return self._user_source_model

    @api.model
    def user_mirror_model(self):
        return self._user_mirror_model

    @api.model
    def is_never_mirror_model(self, model_name):
        return model_name in self._never_mirror_models

    @api.model
    def is_upload_source_forbidden(self, model_name):
        return model_name == self._user_source_model

    @api.model
    def is_id_only_relation_model(self, model_name):
        return model_name == self._user_source_model or self.is_never_mirror_model(model_name)
