from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.translate import _


class AbTestCategory(models.Model):
    _name = "ab_test_category"
    _description = "AB Sync Test Category"
    _order = "code, name"

    name = fields.Char(required=True)
    code = fields.Char(required=True, index=True)
    description = fields.Text()
    color = fields.Integer(default=0)
    active = fields.Boolean(default=True, index=True)
    parent_id = fields.Many2one(
        "ab_test_category",
        string="Parent Category",
        ondelete="restrict",
        index=True,
    )
    child_ids = fields.One2many(
        "ab_test_category",
        "parent_id",
        string="Child Categories",
    )

    _uniq_code = models.Constraint(
        "UNIQUE(code)",
        "Category code must be unique.",
    )

    @api.constrains("parent_id")
    def _check_parent_cycle(self):
        if not self._check_recursion():
            raise ValidationError(_("A category cannot be its own ancestor."))


class AbTestTag(models.Model):
    _name = "ab_test_tag"
    _description = "AB Sync Test Tag"
    _order = "code, name"

    name = fields.Char(required=True)
    code = fields.Char(required=True, index=True)
    color = fields.Integer(default=0)
    active = fields.Boolean(default=True, index=True)

    _uniq_code = models.Constraint(
        "UNIQUE(code)",
        "Tag code must be unique.",
    )


class AbTestHeader(models.Model):
    _name = "ab_test_header"
    _description = "AB Sync Test Header"
    _order = "id desc"

    name = fields.Char(required=True)
    reference = fields.Char(required=True, index=True)
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("confirmed", "Confirmed"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        required=True,
        index=True,
    )
    priority = fields.Selection(
        selection=[
            ("normal", "Normal"),
            ("high", "High"),
            ("urgent", "Urgent"),
        ],
        default="normal",
        required=True,
    )
    transaction_date = fields.Date(default=fields.Date.context_today, required=True)
    category_id = fields.Many2one(
        "ab_test_category",
        required=True,
        ondelete="restrict",
        index=True,
    )
    tag_ids = fields.Many2many(
        "ab_test_tag",
        "ab_test_header_tag_rel",
        "header_id",
        "tag_id",
        string="Tags",
    )
    line_ids = fields.One2many(
        "ab_test_line",
        "header_id",
        string="Lines",
    )
    notes = fields.Text()
    settings_json = fields.Json(string="Settings JSON", default=dict)
    line_count = fields.Integer(compute="_compute_totals", store=True)
    total_amount = fields.Float(compute="_compute_totals", store=True, digits=(16, 3))
    active = fields.Boolean(default=True, index=True)

    _uniq_reference = models.Constraint(
        "UNIQUE(reference)",
        "Header reference must be unique.",
    )

    @api.depends("line_ids", "line_ids.subtotal")
    def _compute_totals(self):
        for record in self:
            record.line_count = len(record.line_ids)
            record.total_amount = sum(record.line_ids.mapped("subtotal"))


class AbTestLine(models.Model):
    _name = "ab_test_line"
    _description = "AB Sync Test Line"
    _order = "header_id, sequence, id"

    header_id = fields.Many2one(
        "ab_test_header",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(default=10)
    name = fields.Char(required=True)
    category_id = fields.Many2one(
        "ab_test_category",
        ondelete="restrict",
        index=True,
    )
    tag_ids = fields.Many2many(
        "ab_test_tag",
        "ab_test_line_tag_rel",
        "line_id",
        "tag_id",
        string="Tags",
    )
    quantity = fields.Float(default=1.0, required=True, digits=(16, 3))
    unit_price = fields.Float(required=True, digits=(16, 3))
    subtotal = fields.Float(compute="_compute_subtotal", store=True, digits=(16, 3))
    planned_date = fields.Date()
    attributes_json = fields.Json(string="Attributes JSON", default=dict)
    active = fields.Boolean(default=True, index=True)

    @api.depends("quantity", "unit_price")
    def _compute_subtotal(self):
        for record in self:
            record.subtotal = record.quantity * record.unit_price

    @api.constrains("quantity")
    def _check_quantity(self):
        for record in self:
            if record.quantity < 0:
                raise ValidationError(_("Quantity cannot be negative."))


class AbTestDeleteCascadeParent(models.Model):
    _name = "ab_test_delete_cascade_parent"
    _description = "AB Sync Test Cascade Delete Parent"
    _order = "code, name"

    name = fields.Char(required=True)
    code = fields.Char(required=True, index=True)
    active = fields.Boolean(default=True, index=True)
    child_ids = fields.One2many(
        "ab_test_delete_cascade_child",
        "parent_id",
        string="Children",
    )

    _uniq_code = models.Constraint(
        "UNIQUE(code)",
        "Parent code must be unique.",
    )


class AbTestDeleteCascadeChild(models.Model):
    _name = "ab_test_delete_cascade_child"
    _description = "AB Sync Test Cascade Delete Child"
    _order = "parent_id, id"

    parent_id = fields.Many2one(
        "ab_test_delete_cascade_parent",
        string="Parent",
        required=True,
        ondelete="cascade",
        index=True,
    )
    name = fields.Char(required=True)
    note = fields.Text()
    active = fields.Boolean(default=True, index=True)


class AbTestDeleteSetNullParent(models.Model):
    _name = "ab_test_delete_set_null_parent"
    _description = "AB Sync Test Set Null Delete Parent"
    _order = "code, name"

    name = fields.Char(required=True)
    code = fields.Char(required=True, index=True)
    active = fields.Boolean(default=True, index=True)
    child_ids = fields.One2many(
        "ab_test_delete_set_null_child",
        "parent_id",
        string="Children",
    )

    _uniq_code = models.Constraint(
        "UNIQUE(code)",
        "Parent code must be unique.",
    )


class AbTestDeleteSetNullChild(models.Model):
    _name = "ab_test_delete_set_null_child"
    _description = "AB Sync Test Set Null Delete Child"
    _order = "parent_id, id"

    parent_id = fields.Many2one(
        "ab_test_delete_set_null_parent",
        string="Parent",
        ondelete="set null",
        index=True,
    )
    name = fields.Char(required=True)
    note = fields.Text()
    active = fields.Boolean(default=True, index=True)


class AbTestDeleteRestrictParent(models.Model):
    _name = "ab_test_delete_restrict_parent"
    _description = "AB Sync Test Restrict Delete Parent"
    _order = "code, name"

    name = fields.Char(required=True)
    code = fields.Char(required=True, index=True)
    active = fields.Boolean(default=True, index=True)
    child_ids = fields.One2many(
        "ab_test_delete_restrict_child",
        "parent_id",
        string="Children",
    )

    _uniq_code = models.Constraint(
        "UNIQUE(code)",
        "Parent code must be unique.",
    )


class AbTestDeleteRestrictChild(models.Model):
    _name = "ab_test_delete_restrict_child"
    _description = "AB Sync Test Restrict Delete Child"
    _order = "parent_id, id"

    parent_id = fields.Many2one(
        "ab_test_delete_restrict_parent",
        string="Parent",
        required=True,
        ondelete="restrict",
        index=True,
    )
    name = fields.Char(required=True)
    note = fields.Text()
    active = fields.Boolean(default=True, index=True)
