from odoo import fields, models


class AbTestCustomerReferenceSync(models.Model):
    _name = "ab_test_customer_reference__sync"
    _inherit = "ab_test_sync_mixin"
    _description = "AB Sync Test Customer Reference Mirror"
    _order = "db_serial, reference, rec_id"

    name = fields.Char()
    reference = fields.Char(index=True)
    customer_id = fields.Many2one(
        "ab_customer",
        string="Customer",
        ondelete="restrict",
        index=True,
    )
    note = fields.Text()

    _uniq_branch_source = models.Constraint(
        "UNIQUE(db_serial, rec_id)",
        "Customer reference mirror must be unique per branch and source record.",
    )
