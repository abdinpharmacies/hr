from odoo import api, fields, models


class AbSalesSyncMixin(models.AbstractModel):
    _name = "ab_sales_sync_mixin"
    _description = "AB Sales Sync Mirror Mixin"

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


class AbSalesHeaderSync(models.Model):
    _name = "ab_sales_header__sync"
    _inherit = "ab_sales_sync_mixin"
    _description = "Branch Sales Header Mirror"
    _order = "db_serial, eplus_serial desc, rec_id desc"

    store_id = fields.Many2one("ab_store", string="Store", ondelete="restrict", index=True)
    customer_id = fields.Many2one("ab_customer", string="Customer", ondelete="restrict", index=True)
    invoice_address = fields.Char(string="Invoice Address")
    is_delivery = fields.Boolean(string="Delivery")
    employee_delivery_id = fields.Many2one(
        "ab_hr_employee",
        string="Delivery Employee",
        ondelete="restrict",
        index=True,
    )
    description = fields.Text(string="Description")
    status = fields.Selection(
        selection=[
            ("prepending", "PrePending"),
            ("pending", "Pending"),
            ("saved", "Saved"),
        ],
        string="Status",
        index=True,
    )
    is_closed = fields.Boolean(string="Closed")
    line_ids = fields.One2many(
        "ab_sales_line__sync",
        "header_id",
        string="Lines",
    )
    eplus_serial = fields.Integer(string="ePlus Serial", index=True)
    push_state = fields.Selection(
        selection=[
            ("none", "None"),
            ("success", "Success"),
            ("error", "Error"),
        ],
        string="Push State",
        index=True,
    )
    push_message = fields.Text(string="Push Message")
    new_customer_name = fields.Char(string="New Customer Name")
    new_customer_phone = fields.Char(string="New Customer Phone")
    new_customer_address = fields.Char(string="New Customer Address")
    bill_customer_name = fields.Char(string="Bill Customer Name")
    bill_customer_phone = fields.Char(string="Bill Customer Phone", index=True)
    bill_customer_address = fields.Char(string="Bill Customer Address")
    customer_insurance_name = fields.Char(string="Customer Insurance Name")
    customer_insurance_number = fields.Char(string="Customer Insurance Number")
    pos_client_token = fields.Char(string="POS Client Token", index=True)
    employee_id = fields.Many2one(
        "ab_hr_employee",
        string="Actual Salesperson",
        ondelete="restrict",
        index=True,
    )
    line_count = fields.Integer(string="Line Count", compute="_compute_totals", store=True)
    total_qty = fields.Float(string="Total Quantity", compute="_compute_totals", store=True, digits=(18, 4))
    total_price = fields.Float(string="Total Price", compute="_compute_totals", store=True)
    total_net_amount = fields.Float(string="Total Net Amount", compute="_compute_totals", store=True)

    _uniq_branch_source = models.Constraint(
        "UNIQUE(db_serial, rec_id)",
        "Sales header mirror must be unique per branch and source record.",
    )

    @api.depends("line_ids", "line_ids.qty", "line_ids.price_subtotal", "line_ids.net_amount")
    def _compute_totals(self):
        for record in self:
            lines = record.line_ids.filtered("active")
            record.line_count = len(lines)
            record.total_qty = sum(lines.mapped("qty"))
            record.total_price = sum(lines.mapped("price_subtotal"))
            record.total_net_amount = sum(lines.mapped("net_amount"))


class AbSalesLineSync(models.Model):
    _name = "ab_sales_line__sync"
    _inherit = "ab_sales_sync_mixin"
    _description = "Branch Sales Line Mirror"
    _order = "db_serial, header_id, rec_id"
    _rec_name = "product_id"

    header_id = fields.Many2one(
        "ab_sales_header__sync",
        string="Header",
        ondelete="restrict",
        index=True,
    )
    product_id = fields.Many2one("ab_product", string="Product", ondelete="restrict", index=True)
    product_code = fields.Char(string="Product Code", index=True)
    inventory_json = fields.Json(string="Inventory JSON", default=dict)
    qty_str = fields.Char(string="Qty")
    qty = fields.Float(string="Quantity", digits=(18, 4))
    balance = fields.Float(string="Total Balance")
    price = fields.Float(string="Price")
    available_prices = fields.Char(string="Available Prices")
    sell_price = fields.Float(string="Sell Price")
    target_sell_price = fields.Float(string="Target Sell Price")
    cost = fields.Float(string="Cost")
    net_amount = fields.Float(string="Net Amount", compute="_compute_net_amount", store=True)
    products_not_exist = fields.Boolean(string="Products Not Exist")
    uom_id = fields.Many2one("ab_product_uom", string="UoM", ondelete="restrict", index=True)
    price_subtotal = fields.Float(string="Subtotal")
    price_tax = fields.Float(string="Tax")
    unavailable_reason = fields.Selection(
        selection=[
            ("not_transferred", "Not transferred yet from main store"),
            ("wrong_price", "Wrong price in system"),
            ("stocktaking_error", "Stocktaking error"),
            ("not_entered", "Not entered by data entry yet"),
            ("promised_customer", "Already told customer we will deliver product"),
            ("other", "Other"),
        ],
        string="Unavailable Reason",
    )
    unavailable_reason_other = fields.Char(string="Other Reason")

    _uniq_branch_source = models.Constraint(
        "UNIQUE(db_serial, rec_id)",
        "Sales line mirror must be unique per branch and source record.",
    )

    @api.depends("qty", "sell_price")
    def _compute_net_amount(self):
        for record in self:
            record.net_amount = (record.qty or 0.0) * (record.sell_price or 0.0)


class AbSalesReturnHeaderSync(models.Model):
    _name = "ab_sales_return_header__sync"
    _inherit = "ab_sales_sync_mixin"
    _description = "Branch Sales Return Header Mirror"
    _order = "db_serial, sales_return_id desc, rec_id desc"

    origin_header_id = fields.Integer(string="Invoice Number", index=True)
    store_id = fields.Many2one("ab_store", string="Store", ondelete="restrict", index=True)
    sto_eplus_serial = fields.Integer(string="Store ePlus Serial", index=True)
    status = fields.Selection(
        selection=[
            ("prepending", "PrePending"),
            ("pending", "Pending"),
            ("saved", "Saved"),
        ],
        string="Status",
        index=True,
    )
    line_ids = fields.One2many(
        "ab_sales_return_line__sync",
        "header_id",
        string="Return Lines",
    )
    total_return_qty = fields.Float(string="Total Qty")
    total_return_value = fields.Float(string="Total Value")
    sales_return_id = fields.Integer(string="Sales Return ID", index=True)
    f_transaction_id = fields.Integer(string="F-Transaction ID", index=True)
    total_sales_net = fields.Float(string="Total Sales Net")
    notes = fields.Text(string="Notes")
    line_count = fields.Integer(string="Line Count", compute="_compute_line_count", store=True)

    _uniq_branch_source = models.Constraint(
        "UNIQUE(db_serial, rec_id)",
        "Sales return header mirror must be unique per branch and source record.",
    )

    @api.depends("line_ids")
    def _compute_line_count(self):
        for record in self:
            record.line_count = len(record.line_ids)


class AbSalesReturnLineSync(models.Model):
    _name = "ab_sales_return_line__sync"
    _inherit = "ab_sales_sync_mixin"
    _description = "Branch Sales Return Line Mirror"
    _order = "db_serial, header_id, rec_id"
    _rec_name = "product_id"

    header_id = fields.Many2one(
        "ab_sales_return_header__sync",
        string="Return Header",
        ondelete="restrict",
        index=True,
    )
    sale_line_id = fields.Integer(string="Original Line")
    qty_str = fields.Char(string="Qty")
    qty = fields.Float(string="Quantity", digits=(18, 4))
    product_id = fields.Many2one("ab_product", string="Product", ondelete="restrict", index=True)
    uom_id = fields.Many2one("ab_product_uom", string="UoM", ondelete="restrict", index=True)
    source_itm_unit = fields.Integer(string="Source Unit")
    source_uom_factor = fields.Float(string="Source UoM Factor", digits=(16, 6))
    item_unit1_unit2 = fields.Float(string="itm_unit1_unit2", digits=(16, 6))
    item_unit1_unit3 = fields.Float(string="itm_unit1_unit3", digits=(16, 6))
    qty_sold = fields.Float(string="Sold Qty")
    qty_sold_source = fields.Float(string="Sold Qty (Source)")
    max_returnable_qty = fields.Float(string="Max Returnable", digits=(10, 4))
    max_returnable_source = fields.Float(string="Max Returnable (Source)", digits=(10, 4))
    qty_to_return = fields.Float(string="Qty to Return")
    sell_price = fields.Float(string="Sell Price")
    cost = fields.Float(string="Cost")
    line_value = fields.Float(string="Line Value")
    itm_eplus_id = fields.Integer(string="E-Plus Item ID", index=True)
    sth_id = fields.Integer(string="sth_id", index=True)
    sto_id = fields.Integer(string="sto_id", index=True)
    c_id = fields.Integer(string="c_id", index=True)
    std_id = fields.Integer(string="std_id", index=True)
    itm_nexist = fields.Boolean(string="Item Does Not Exist")

    _uniq_branch_source = models.Constraint(
        "UNIQUE(db_serial, rec_id)",
        "Sales return line mirror must be unique per branch and source record.",
    )
