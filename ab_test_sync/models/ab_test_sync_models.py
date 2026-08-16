from odoo import fields, models


class AbTestSyncMixin(models.AbstractModel):
    _name = "ab_test_sync_mixin"
    _description = "AB Sync Test Mirror Mixin"

    db_serial = fields.Integer(string="DB Serial", required=True, readonly=True, index=True)
    rec_id = fields.Integer(string="Source Record ID", required=True, readonly=True, index=True)
    source_revision = fields.Integer(string="Source Revision", readonly=True, index=True)
    event_uuid = fields.Char(string="Event UUID", readonly=True, index=True)
    source_operation = fields.Selection(
        selection=[("upsert", "Upsert"), ("archive", "Archive")],
        string="Source Operation",
        readonly=True,
    )
    source_write_date = fields.Datetime(string="Source Write Date", readonly=True, index=True)
    synced_at = fields.Datetime(string="Synchronized At", readonly=True, index=True)
    payload_json = fields.Json(string="Full Source Payload", default=dict, readonly=True)
    active = fields.Boolean(default=True, index=True)


class AbTestCategorySync(models.Model):
    _name = "ab_test_category__sync"
    _inherit = "ab_test_sync_mixin"
    _description = "AB Sync Test Category Mirror"
    _order = "db_serial, code, rec_id"

    name = fields.Char()
    code = fields.Char(index=True)
    description = fields.Text()
    color = fields.Integer()
    parent_id = fields.Many2one(
        "ab_test_category__sync",
        string="Parent Category",
        ondelete="restrict",
        index=True,
    )
    child_ids = fields.One2many(
        "ab_test_category__sync",
        "parent_id",
        string="Child Categories",
    )

    _uniq_branch_source = models.Constraint(
        "UNIQUE(db_serial, rec_id)",
        "Category mirror must be unique per branch and source record.",
    )


class AbTestTagSync(models.Model):
    _name = "ab_test_tag__sync"
    _inherit = "ab_test_sync_mixin"
    _description = "AB Sync Test Tag Mirror"
    _order = "db_serial, code, rec_id"

    name = fields.Char()
    code = fields.Char(index=True)
    color = fields.Integer()

    _uniq_branch_source = models.Constraint(
        "UNIQUE(db_serial, rec_id)",
        "Tag mirror must be unique per branch and source record.",
    )


class AbTestHeaderSync(models.Model):
    _name = "ab_test_header__sync"
    _inherit = "ab_test_sync_mixin"
    _description = "AB Sync Test Header Mirror"
    _order = "db_serial, rec_id desc"

    name = fields.Char()
    reference = fields.Char(index=True)
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("confirmed", "Confirmed"),
            ("cancelled", "Cancelled"),
        ],
    )
    priority = fields.Selection(
        selection=[
            ("normal", "Normal"),
            ("high", "High"),
            ("urgent", "Urgent"),
        ],
    )
    transaction_date = fields.Date()
    category_id = fields.Many2one(
        "ab_test_category__sync",
        ondelete="restrict",
        index=True,
    )
    tag_ids = fields.Many2many(
        "ab_test_tag__sync",
        "ab_test_sync_header_tag_rel",
        "header_id",
        "tag_id",
        string="Tags",
    )
    line_ids = fields.One2many(
        "ab_test_line__sync",
        "header_id",
        string="Lines",
    )
    notes = fields.Text()
    settings_json = fields.Json(string="Settings JSON", default=dict)
    line_count = fields.Integer()
    total_amount = fields.Float(digits=(16, 3))

    _uniq_branch_source = models.Constraint(
        "UNIQUE(db_serial, rec_id)",
        "Header mirror must be unique per branch and source record.",
    )


class AbTestLineSync(models.Model):
    _name = "ab_test_line__sync"
    _inherit = "ab_test_sync_mixin"
    _description = "AB Sync Test Line Mirror"
    _order = "db_serial, header_id, sequence, rec_id"

    header_id = fields.Many2one(
        "ab_test_header__sync",
        ondelete="restrict",
        index=True,
    )
    sequence = fields.Integer()
    name = fields.Char()
    category_id = fields.Many2one(
        "ab_test_category__sync",
        ondelete="restrict",
        index=True,
    )
    tag_ids = fields.Many2many(
        "ab_test_tag__sync",
        "ab_test_sync_line_tag_rel",
        "line_id",
        "tag_id",
        string="Tags",
    )
    quantity = fields.Float(digits=(16, 3))
    unit_price = fields.Float(digits=(16, 3))
    subtotal = fields.Float(digits=(16, 3))
    planned_date = fields.Date()
    attributes_json = fields.Json(string="Attributes JSON", default=dict)

    _uniq_branch_source = models.Constraint(
        "UNIQUE(db_serial, rec_id)",
        "Line mirror must be unique per branch and source record.",
    )
