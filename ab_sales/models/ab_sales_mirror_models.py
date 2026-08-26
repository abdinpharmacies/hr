from odoo import api, fields, models


class AbSalesMirrorMixin(models.AbstractModel):
    _name = "ab_sales_mirror_mixin"
    _description = "AB Sales Reporting Mirror Mixin"

    db_serial = fields.Integer(string="DB Serial", required=False, readonly=True, index=True)
    rec_id = fields.Integer(string="Source Record ID", required=False, readonly=True, index=True)
    source_revision = fields.Integer(string="Source Revision", readonly=True, index=True)
    event_uuid = fields.Char(string="Event UUID", readonly=True, index=True)
    source_create_uid = fields.Many2one(
        "ab_users",
        string="Source Created By",
        readonly=True,
        ondelete="restrict",
        index=True,
    )
    source_write_uid = fields.Many2one(
        "ab_users",
        string="Source Last Updated By",
        readonly=True,
        ondelete="restrict",
        index=True,
    )
    source_operation = fields.Selection(
        selection=[("upsert", "Upsert"), ("archive", "Archive")],
        string="Source Operation",
        readonly=True,
    )
    source_write_date = fields.Datetime(string="Source Write Date", readonly=True, index=True)
    synced_at = fields.Datetime(string="Synchronized At", readonly=True, index=True)
    payload_json = fields.Json(string="Full Source Payload", default=dict, readonly=True)
    active = fields.Boolean(default=True, index=True)


class AbSalesHeaderMirror(models.Model):
    _name = "ab_sales_header"
    _inherit = "ab_sales_mirror_mixin"
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
        "ab_sales_line",
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


class AbSalesLineMirror(models.Model):
    _name = "ab_sales_line"
    _inherit = "ab_sales_mirror_mixin"
    _description = "Branch Sales Line Mirror"
    _order = "db_serial, header_id, rec_id"
    _rec_name = "product_id"

    header_id = fields.Many2one(
        "ab_sales_header",
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


class AbSalesReturnHeaderMirror(models.Model):
    _name = "ab_sales_return_header"
    _inherit = "ab_sales_mirror_mixin"
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
        "ab_sales_return_line",
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


class AbSalesReturnLineMirror(models.Model):
    _name = "ab_sales_return_line"
    _inherit = "ab_sales_mirror_mixin"
    _description = "Branch Sales Return Line Mirror"
    _order = "db_serial, header_id, rec_id"
    _rec_name = "product_id"

    header_id = fields.Many2one(
        "ab_sales_return_header",
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


class AbProductPricedMirror(models.Model):
    _name = "ab_product_priced"
    _inherit = "ab_sales_mirror_mixin"
    _description = "Branch Product Priced Mirror"
    _order = "db_serial, product_code, rec_id"
    _rec_name = "product_code"

    product_id = fields.Many2one("ab_product", string="Product", ondelete="restrict", index=True)
    product_code = fields.Char(string="Product Code", index=True)
    is_priced = fields.Boolean(string="Priced")
    notes = fields.Char(string="Notes")

    _uniq_branch_source = models.Constraint(
        "UNIQUE(db_serial, rec_id)",
        "Product priced mirror must be unique per branch and source record.",
    )


class AbProductMetadataMirror(models.Model):
    _name = "ab_product_metadata"
    _inherit = "ab_sales_mirror_mixin"
    _description = "Branch Product Metadata Mirror"
    _order = "db_serial, product_code, rec_id"
    _rec_name = "product_code"

    product_id = fields.Many2one("ab_product", string="Product", ondelete="restrict", index=True)
    product_code = fields.Char(string="Product Code", index=True)
    is_priced = fields.Boolean(string="Priced")
    notes = fields.Char(string="Notes")

    _uniq_branch_source = models.Constraint(
        "UNIQUE(db_serial, rec_id)",
        "Product metadata mirror must be unique per branch and source record.",
    )


class AbSalesInventoryMirror(models.Model):
    _name = "ab_sales_inventory"
    _inherit = "ab_sales_mirror_mixin"
    _description = "Branch Sales Inventory Mirror"
    _order = "db_serial, store_id, product_eplus_serial, rec_id"
    _rec_name = "product_code"

    product_eplus_serial = fields.Integer(string="Product ePlus Serial", index=True)
    product_id = fields.Many2one("ab_product", string="Product", ondelete="restrict", index=True)
    product_code = fields.Char(string="Product Code", index=True)
    store_id = fields.Many2one("ab_store", string="Store", ondelete="restrict", index=True)
    balance = fields.Float(string="Balance")
    default_price = fields.Float(string="Default Price")

    _uniq_branch_source = models.Constraint(
        "UNIQUE(db_serial, rec_id)",
        "Sales inventory mirror must be unique per branch and source record.",
    )


class AbSalesPerDayMirror(models.Model):
    _name = "ab_sales_per_day"
    _inherit = "ab_sales_mirror_mixin"
    _description = "Branch Sales Per Day Mirror"
    _order = "db_serial, sale_date desc, store_id, product_eplus_serial"

    store_id = fields.Many2one("ab_store", string="Store", ondelete="restrict", index=True)
    product_eplus_serial = fields.Integer(string="Product ePlus Serial", index=True)
    product_id = fields.Many2one("ab_product", string="Product", ondelete="restrict", index=True)
    sale_date = fields.Date(string="Sale Date", index=True)
    sales_qty = fields.Float(string="Sales Quantity", digits=(16, 4))
    sync_at = fields.Datetime(string="Source Synced At")

    _uniq_branch_source = models.Constraint(
        "UNIQUE(db_serial, rec_id)",
        "Sales per day mirror must be unique per branch and source record.",
    )


class AbSalesPerDaySyncStateMirror(models.Model):
    _name = "ab_sales_per_day_sync_state"
    _inherit = "ab_sales_mirror_mixin"
    _description = "Branch Sales Per Day Sync State Mirror"
    _order = "db_serial, sale_date desc, rec_id"

    sale_date = fields.Date(string="Sale Date", index=True)
    state = fields.Selection(
        selection=[
            ("pending", "Pending"),
            ("running", "Running"),
            ("done", "Done"),
            ("failed", "Failed"),
        ],
        string="Status",
        index=True,
    )
    rows_synced = fields.Integer(string="Rows Synced")
    started_at = fields.Datetime(string="Started At")
    finished_at = fields.Datetime(string="Finished At")
    error_message = fields.Text(string="Error")

    _uniq_branch_source = models.Constraint(
        "UNIQUE(db_serial, rec_id)",
        "Sales per day sync state mirror must be unique per branch and source record.",
    )


class AbProductRankMirror(models.Model):
    _name = "ab_product_rank"
    _inherit = "ab_sales_mirror_mixin"
    _description = "Branch Product Ranking Mirror"
    _order = "db_serial, score desc, order_count desc, qty_total desc, rec_id desc"
    _rec_name = "product_id"

    product_id = fields.Many2one("ab_product", string="Product", ondelete="restrict", index=True)
    store_id = fields.Many2one("ab_store", string="Store", ondelete="restrict", index=True)
    customer_phone = fields.Char(string="Customer Phone", index=True)
    rank_scope = fields.Selection(
        selection=[("branch", "Branch"), ("customer", "Customer")],
        string="Rank Scope",
        index=True,
    )
    period_days = fields.Integer(string="Period Days", index=True)
    order_count = fields.Integer(string="Order Count")
    qty_total = fields.Float(string="Total Quantity")
    score = fields.Float(string="Score", index=True)
    last_order_date = fields.Datetime(string="Last Order Date")

    _uniq_branch_source = models.Constraint(
        "UNIQUE(db_serial, rec_id)",
        "Product ranking mirror must be unique per branch and source record.",
    )


class AbSalesPosSettingsMirror(models.Model):
    _name = "ab_sales_pos_settings"
    _inherit = "ab_sales_mirror_mixin"
    _description = "Branch Sales POS Settings Mirror"
    _order = "db_serial, rec_id desc"

    user_id = fields.Many2one("ab_users", string="User", ondelete="restrict", index=True)
    settings_version = fields.Integer(string="Settings Version")
    last_synced_at = fields.Datetime(string="Last Synced At")
    settings_json = fields.Json(string="Settings JSON", default=dict)

    _uniq_branch_source = models.Constraint(
        "UNIQUE(db_serial, rec_id)",
        "Sales POS settings mirror must be unique per branch and source record.",
    )


class AbSalesPosDraftCacheMirror(models.Model):
    _name = "ab_sales_pos_draft_cache"
    _inherit = "ab_sales_mirror_mixin"
    _description = "Branch Sales POS Draft Cache Mirror"
    _order = "db_serial, source_write_date desc, rec_id desc"

    user_id = fields.Many2one("ab_users", string="User", ondelete="restrict", index=True)
    employee_id = fields.Many2one("ab_hr_employee", string="Employee", ondelete="restrict", index=True)
    employee_scope_key = fields.Integer(string="Employee Scope Key", index=True)
    cache_key = fields.Char(string="Cache Key", index=True)
    selected_id = fields.Char(string="Selected ID")
    last_synced_at = fields.Datetime(string="Last Synced At")
    bills_json = fields.Json(string="Bills JSON", default=list)

    _uniq_branch_source = models.Constraint(
        "UNIQUE(db_serial, rec_id)",
        "Sales POS draft cache mirror must be unique per branch and source record.",
    )


class AbSalesPosReplicationTurnMirror(models.Model):
    _name = "ab_sales_pos_replication_turn"
    _inherit = "ab_sales_mirror_mixin"
    _description = "Branch Sales POS Replication Turn Mirror"
    _order = "db_serial, last_manual_run_at desc, rec_id desc"

    user_id = fields.Many2one("ab_users", string="User", ondelete="restrict", index=True)
    cron_id = fields.Many2one("ir.cron", string="Cron", ondelete="restrict", index=True)
    last_manual_run_at = fields.Datetime(string="Last Manual Run At")

    _uniq_branch_source = models.Constraint(
        "UNIQUE(db_serial, rec_id)",
        "Sales POS replication turn mirror must be unique per branch and source record.",
    )


class AbPrinterMirror(models.Model):
    _name = "ab_printer"
    _inherit = "ab_sales_mirror_mixin"
    _description = "Branch Printer Configuration Mirror"
    _order = "db_serial, is_default desc, name asc, rec_id"

    name = fields.Char(string="Name", index=True)
    is_default = fields.Boolean(string="Default")
    ip = fields.Char(string="IP / Host")
    port = fields.Integer(string="Port")
    username = fields.Char(string="Username")
    printer_name = fields.Char(string="Printer / Share Name")
    protocol = fields.Selection(
        selection=[
            ("shared", "Shared"),
            ("connected", "Connected"),
            ("network", "Network"),
        ],
        string="Protocol",
    )
    paper_size = fields.Selection(
        selection=[
            ("pos_80mm", "POS 80mm"),
            ("a4", "A4"),
        ],
        string="Paper Size",
    )
    notes = fields.Text(string="Notes")
    extra_feed_lines = fields.Integer(string="Extra Feed Lines")

    _uniq_branch_source = models.Constraint(
        "UNIQUE(db_serial, rec_id)",
        "Printer configuration mirror must be unique per branch and source record.",
    )
