from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError


class AbTransferSmartCacheState(models.Model):
    _name = "ab_transfer_smart_cache_state"
    _description = "Smart Transfer Snapshot State"
    _rec_name = "store_id"

    store_id = fields.Many2one("ab_store", required=True, index=True, ondelete="restrict")
    stock_revision = fields.Integer(readonly=True)
    stock_date = fields.Date(readonly=True)
    origin = fields.Selection([("live", "Live"), ("excel", "Excel")], readonly=True)
    imported_workflow = fields.Boolean(readonly=True)
    import_user_id = fields.Many2one("res.users", readonly=True)
    import_time = fields.Datetime(readonly=True)
    import_filename = fields.Char(readonly=True)
    sales_date = fields.Date(readonly=True)
    sales_refreshed_at = fields.Datetime(readonly=True)

    _unique_store = models.Constraint("UNIQUE(store_id)", "A branch has only one snapshot state.")

    @api.model
    def _business_date(self):
        return fields.Date.context_today(self.with_context(tz="Africa/Cairo"))

    @api.model
    def _check_branch_access(self, stores, importing=False):
        user = self.env.user
        if not self.env.su and not user.has_group("base.group_system"):
            groups = ["ab_transfer_smart.group_transfer_smart_purchase"]
            if not importing:
                groups += ["ab_transfer_smart.group_trnasfer_smart_store_preparation",
                           "ab_transfer_smart.group_trnasfer_smart_store_revision"]
            if not any(user.has_group(group) for group in groups):
                raise AccessError(_("You are not allowed to manage Smart Transfer snapshots."))
        stores.check_access("read")
        for store in stores:
            if "company_id" in store._fields and store.company_id and store.company_id not in self.env.companies:
                raise AccessError(_("The branch is outside your allowed companies."))

    @api.model
    def _lock_branches(self, stores, initialize=False):
        self._check_branch_access(stores)
        for store_id in sorted(set(stores.ids)):
            self.env.cr.execute("SELECT pg_advisory_xact_lock(%s, %s)", [1907351902, store_id])
            self.env.cr.execute(
                "SELECT id FROM ab_transfer_smart_cache_state WHERE store_id = %s FOR UPDATE", [store_id]
            )
            if not self.env.cr.fetchone() and initialize:
                self.sudo().create({"store_id": store_id})
        self.sudo().invalidate_model()
        self.env["ab_transfer_smart_stock_cache"].sudo().invalidate_model()
        self.env["ab_transfer_smart_sales_cache"].sudo().invalidate_model()

    @api.model
    def _state(self, store):
        return self.sudo().search([("store_id", "=", store.id)], limit=1)

    @api.model
    def _publish(self, store, values):
        state = self._state(store)
        if state:
            state.write(values)
        else:
            state = self.sudo().create(dict(values, store_id=store.id))
        return state

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            raise AccessError(_("Snapshot state can only be published by a successful refresh or import."))
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su:
            raise AccessError(_("Snapshot state can only be published by a successful refresh or import."))
        return super().write(vals)

    def unlink(self):
        raise UserError(_("Snapshot state cannot be deleted."))
