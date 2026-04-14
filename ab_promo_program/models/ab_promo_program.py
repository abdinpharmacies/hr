from math import floor

from odoo import api, fields, models
from odoo.tools.translate import _
from odoo.exceptions import ValidationError


class AbPromoProgram(models.Model):
    _name = 'ab_promo_program'
    _description = 'ab_promo_program'

    _order = 'sequence, id'

    name = fields.Char(required=True, index=True)
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)

    supplier_id = fields.Many2one('ab_costcenter')
    budget = fields.Float()

    max_repetition_per_invoice = fields.Integer(
        default=3,
        string="Max Repetition per Invoice",
        help="Maximum number of times this promotion can be applied within a single invoice. "
    )

    # Scope / Applicability
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, index=True)
    store_ids = fields.Many2many(
        comodel_name='ab_store',
        relation='ab_promo_program_store_rel',
        column1='promo_id',
        column2='store_id',
        string="Stores",
        help="Leave empty to apply to all stores."
    )
    replica_db_ids = fields.Many2many(
        comodel_name='ab_replica_db',
        relation='ab_promo_program_replica_db_rel',
        column1='promo_id',
        column2='replica_db_id',
        string="Replica Databases",
        help="Leave empty to apply to all replica databases.",
    )
    partner_ids = fields.Many2many('ab_customer', string="Allowed Customers")
    partner_domain = fields.Char(
        string="Partner Domain (safe_eval)",
        help="Optional dynamic domain on ab_customer, e.g. "
             "[('category_id.name', 'in', ['VIP','Gold'])]"
    )

    # Time window
    rule_date_from = fields.Datetime()
    rule_date_to = fields.Datetime()

    # Amount gates (optional – off by default)
    rule_min_amount = fields.Monetary(
        string="Rule Min Amount (Money)",
        help="Minimum header untaxed amount to be eligible (optional)."
    )
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id.id)

    # Product rules
    rule_products_domain = fields.Char(
        string="Products Domain (safe_eval)",
        help="Domain on ab_product, e.g. [('sale_ok','=',True),('categ_id.name','ilike','Skin')] "
             "Leave empty to accept any product."
    )
    rule_min_qty = fields.Integer(
        string="Rule Min Qty",
        default=1, help="Total qty (over matching products) required.")
    promo_uom_basis = fields.Selection([
        ('largest_uom', 'Largest Unit'),
        ('smallest_uom', 'Smallest Unit'),
    ], string="Promo UoM Basis", default='largest_uom',
        help="Controls which unit basis is used when evaluating minimum promo quantity.")
    rule_same_reward_qty = fields.Boolean(
        default=False,
        help="If true, require exactly rule_min_qty + reward_quantity in cart "
             "(mimics 'Buy X Get Y same product' eligibility checks)."
    )
    # Optional: set of explicit products (faster than evaluating domain every time)

    disc_percent = fields.Float(
        string="Discount (%)",
        default=0.0,
        help="The discount in percentage (could be more than 100 e.g. 200 300 400)"
    )

    apply_disc_on = fields.Selection([
        ('on_order', 'On Ordered Quantity'),
        ('cheapest_product', 'On Cheapest Product'),
        ('fixed_price', 'Fixed Price'),
        ('specific_products', 'On Specific Products'),
    ], default='on_order', required=True)

    fixed_price = fields.Float(default=0)

    product_ids = fields.Many2many(
        comodel_name='ab_product',
        relation='ab_promo_program_explicit_product_rel',
        column1='promo_id',
        column2='product_id',
        string="Explicit Products (optional)")

    # Used when apply_disc_on == 'specific_products'
    disc_specific_product_ids = fields.Many2many(
        comodel_name='ab_product',
        relation='ab_promo_program_discount_products_rel',
        column1='promo_id',
        column2='product_id',
        string="Discount On Specific Products"
    )
    rule_text = fields.Char(
        string="Offer Description",
        compute="_compute_rule_text",
        store=False
    )

    status = fields.Selection(
        selection=[
            ("pending", "Pending"),
            ("running", "Running"),
            ("finished", "Finished"),
        ],
        compute="_compute_status",
        search="_search_status",
    )

    def _search_status(self, operator, value):
        now = fields.Datetime.now()
        domains = []
        status_domains = {
            "running": [
                ("rule_date_from", "!=", False),
                ("rule_date_to", "!=", False),
                ("rule_date_from", "<=", now),
                ("rule_date_to", ">", now),
            ],
            "finished": [
                ("rule_date_to", "!=", False),
                ("rule_date_to", "<=", now),
            ],
            "pending": ['|', '|',
                        ("rule_date_from", "=", False),
                        ("rule_date_to", "=", False),
                        ("rule_date_from", ">", now), ]
            ,
        }
        if "running" in value:
            domains.append(status_domains['running'])
        if "pending" in value:
            domains.append(status_domains['pending'])
        if "finished" in value:
            domains.append(status_domains['finished'])

        domains_or = fields.Domain.OR(domains)
        if operator in fields.Domain.NEGATIVE_OPERATORS:
            domains_or = ["!"] + domains_or
        return domains_or

    @api.depends("rule_date_from", "rule_date_to")
    def _compute_status(self):
        now = fields.Datetime.now()
        for rec in self:
            if rec.rule_date_from and rec.rule_date_to:
                if rec.rule_date_from <= now < rec.rule_date_to:
                    rec.status = "running"
                elif now >= rec.rule_date_to:
                    rec.status = "finished"
                else:
                    rec.status = "pending"
            else:
                rec.status = "pending"

    @api.depends('rule_min_qty', 'rule_min_amount', 'disc_percent', 'apply_disc_on')
    def _compute_rule_text(self):
        for rec in self:
            rule_min_qty = rec.rule_min_qty
            rule_min_amount = rec.rule_min_amount
            disc_perc = rec.disc_percent
            fixed_price = rec.fixed_price

            rule_min_amount_msg = (_("- with min amount %s %s -") % (rule_min_amount, rec.currency_id.symbol)
                                   if rule_min_amount else "")
            if rec.apply_disc_on == 'cheapest_product':
                rec.rule_text = rec._get_promotion_cheapest_text(rule_min_qty, disc_perc)
            elif rec.apply_disc_on == 'on_order':
                rec.rule_text = _(
                    f"Buy {rec.rule_min_qty} {rule_min_amount_msg} get {int(disc_perc)}% on ordered quantity")
            elif rec.apply_disc_on == 'fixed_price':
                rec.rule_text = _(
                    f"Buy {rec.rule_min_qty} with price upto {fixed_price} LE per item.")
            else:
                rec.rule_text = _(f"Buy {rule_min_amount_msg} get {int(disc_perc)}% on order")

    @api.model
    def _get_promotion_cheapest_text(self, rule_min_qty, disc_percent):
        """
        Translate rule_min_qty + disc_percent into
        a readable formula like 'Buy 2 get 1 free and 50% off 4th'.
        """
        if rule_min_qty <= 1 or disc_percent <= 0:
            return ""

        factor = disc_percent / 100.0
        full = int(floor(factor))
        rem = factor - full

        # Example: rule_min_qty=3, disc_percent=200%
        #   → factor=2.0 → full=2 → rem=0 → Buy 1 get 2 free
        # Example: rule_min_qty=3, disc_percent=100%
        #   → factor=1.0 → full=1 → rem=0 → Buy 2 get 1 free
        # Example: rule_min_qty=4, disc_percent=150%
        #   → factor=1.5 → full=1 → rem=0.5 → Buy 2 get 1 free and 50% on 4th
        if rule_min_qty == 2:
            suffix = 'nd'
        elif rule_min_qty == 3:
            suffix = 'rd'
        else:
            suffix = 'th'

        if full == 0:
            # e.g., 50% → just describe as “Buy rule_min_qty-1 get last at X%”
            return f"Buy {rule_min_qty - 1} get {int(disc_percent)}% off {rule_min_qty}{suffix}"

        if rem == 0:
            buy = rule_min_qty - full
            get = full
            return f"Buy {buy} get {get} free"

        # If there’s a remainder (fractional part)
        buy = rule_min_qty - full
        get = full
        rem_pct = int(rem * 100)
        return f"Buy {buy} get {get} free and {rem_pct}% on {rule_min_qty}{suffix}"

    @api.depends('name', 'rule_text')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"{rec.name} - {rec.rule_text}"

    @api.constrains('rule_min_qty', 'apply_disc_on')
    def _constraint_ab_promo_program(self):
        for rec in self:
            if (rec.apply_disc_on == 'cheapest_product'
                    and rec.rule_min_qty < 2):
                raise ValidationError(_("Minimum qty for rule 'Cheapest Product' Must be at least 2"))
            if rec.rule_min_qty < 1:
                raise ValidationError(_("Minimum qty is 1"))
