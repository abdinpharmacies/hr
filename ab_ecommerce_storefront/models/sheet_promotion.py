from collections import defaultdict
from functools import lru_cache
from math import floor, isfinite
from uuid import uuid4

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError


def _best_offers(candidates):
    best_by_lines = {}
    for index, (lines, saving) in enumerate(candidates):
        key = frozenset(lines)
        previous = best_by_lines.get(key)
        if saving > 0 and (previous is None or saving > candidates[previous][1]):
            best_by_lines[key] = index
    singles = {next(iter(lines)): index for lines, index in best_by_lines.items() if len(lines) == 1}
    gains = {}
    by_line = defaultdict(set)
    for lines, index in best_by_lines.items():
        if len(lines) == 1:
            continue
        displaced = sum(candidates[singles[line]][1] for line in lines if line in singles)
        gain = candidates[index][1] - displaced
        if gain <= 0:
            continue
        gains[index] = gain
        for line in lines:
            by_line[line].add(index)
    conflicts = {
        index: frozenset().union(*(by_line[line] for line in candidates[index][0])) - {index}
        for index in gains
    }

    @lru_cache(None)
    def choose(remaining):
        if not remaining:
            return 0, ()
        pivot = max(remaining, key=lambda i: len(conflicts[i] & remaining))
        if not conflicts[pivot] & remaining:
            return sum(gains[i] for i in remaining), tuple(sorted(remaining))
        component = {pivot}
        frontier = {pivot}
        while frontier:
            frontier = set().union(*(conflicts[i] for i in frontier)) & remaining - component
            component.update(frontier)
        if component != remaining:
            first, left = choose(frozenset(component))
            second, right = choose(remaining - component)
            return first + second, left + right
        excluded = choose(remaining - {pivot})
        saved, others = choose(remaining - {pivot} - conflicts[pivot])
        included = saved + gains[pivot], (pivot,) + others
        return included if included[0] >= excluded[0] else excluded

    bundles = choose(frozenset(conflicts))[1]
    covered = set().union(*(candidates[index][0] for index in bundles))
    return bundles + tuple(index for line, index in singles.items() if line not in covered)


class LoyaltyProgram(models.Model):
    _inherit = 'loyalty.program'

    ab_sheet_key = fields.Char(string='Offer Sheet Reference', copy=False, index=True)
    ab_sheet_imported_product_ids = fields.Many2many(
        "product.product", "ab_sheet_imported_product_rel", "program_id", "product_id",
        string="Previously Imported Products", copy=False, groups="sales_team.group_sale_manager",
    )
    ab_sheet_group_qty = fields.Integer(string='Qualifying Group Size', default=1)
    ab_sheet_discount_qty = fields.Integer(string='Discounted Units per Group', default=1)
    ab_sheet_priority = fields.Integer(string='Offer Priority')
    ab_sheet_fixed_price = fields.Float(string='Final Unit Price in EGP', digits='Product Price')

    _sheet_key_unique = models.Constraint(
        'UNIQUE(website_id, company_id, ab_sheet_key)',
        'This offer has already been imported for this website.',
    )

    @api.model
    def _ab_sheet_values(self, name, website, product_ids, key, group_qty, discount_qty,
                         rate, fixed_price, priority, date_from, date_to):
        rule = {
            "mode": "auto", "minimum_qty": group_qty, "minimum_amount": 0,
            "reward_point_mode": "order", "reward_point_amount": 1,
            "product_ids": [fields.Command.set(product_ids)],
        }
        reward = {
            "reward_type": "discount", "discount_mode": "percent", "description": name,
            "discount_applicability": "cheapest", "discount": rate, "required_points": 1,
            "discount_product_ids": [fields.Command.set(product_ids)],
        }
        values = {
            "name": name, "program_type": "promotion", "company_id": website.company_id.id,
            "website_id": website.id, "sale_ok": False, "ecommerce_ok": True,
            "portal_visible": False, "trigger": "auto", "applies_on": "current",
            "date_from": date_from, "date_to": date_to, "ab_sheet_key": key,
            "ab_sheet_group_qty": group_qty, "ab_sheet_discount_qty": discount_qty,
            "ab_sheet_priority": priority, "ab_sheet_fixed_price": fixed_price,
            "ab_sheet_imported_product_ids": [fields.Command.set(product_ids)],
            "rule_ids": [fields.Command.create(rule)], "reward_ids": [fields.Command.create(reward)],
            "communication_plan_ids": [],
        }
        if "pos_ok" in self._fields:
            values["pos_ok"] = False
        return values

    @api.model
    def _search(self, domain, *args, **kwargs):
        if 'pos_ok' in self._fields:
            domain = fields.Domain(domain).map_conditions(
                lambda term: term & fields.Domain('ab_sheet_key', '=', False)
                if term.field_expr == 'pos_ok' and term.operator == '=' and term.value is True else term
            )
        return super()._search(domain, *args, **kwargs)

    @api.model_create_multi
    def create(self, values_list):
        if 'pos_ok' in self._fields:
            for values in values_list:
                if values.get('ab_sheet_key', self.env.context.get('default_ab_sheet_key')):
                    values['pos_ok'] = False
        return super().create(values_list)

    def copy_data(self, default=None):
        values_list = super().copy_data(default)
        for program, values in zip(self, values_list):
            if values is not None and program.ab_sheet_key:
                values['ab_sheet_key'] = str(uuid4())
        return values_list

    def write(self, values):
        if values.get('pos_ok') and (values.get('ab_sheet_key') or self.filtered('ab_sheet_key')):
            raise ValidationError(_('Imported offers apply only to their website.'))
        if values.get('ab_sheet_key') and 'pos_ok' in self._fields:
            values = dict(values, pos_ok=False)
        if {'ab_sheet_key', 'company_id', 'website_id'}.intersection(values):
            for program in self.filtered('ab_sheet_key'):
                if (values.get('ab_sheet_key', program.ab_sheet_key) != program.ab_sheet_key
                        or values.get('company_id', program.company_id.id) != program.company_id.id
                        or values.get('website_id', program.website_id.id) != program.website_id.id):
                    raise ValidationError(_('The website, company and reference of an imported offer are fixed.'))
        return super().write(values)

    @api.constrains('ab_sheet_key', 'ab_sheet_group_qty', 'ab_sheet_discount_qty',
                    'ab_sheet_fixed_price', 'ab_sheet_priority', 'website_id', 'company_id',
                    'program_type', 'sale_ok', 'ecommerce_ok', 'trigger', 'applies_on')
    def _check_sheet_promotion(self):
        for program in self.filtered('ab_sheet_key'):
            if not self.env.su and (
                not (self.env.user.has_group('base.group_system')
                     or self.env.user.has_group('sales_team.group_sale_manager'))
                or program.company_id not in self.env.companies
            ):
                raise AccessError(_('You cannot manage this imported offer.'))
            if (not program.website_id or program.website_id.company_id != program.company_id
                    or program.program_type != 'promotion' or program.trigger != 'auto'
                    or program.applies_on != 'current' or program.sale_ok or not program.ecommerce_ok
                    or program.ab_sheet_priority < 0
                    or not 1 <= program.ab_sheet_discount_qty <= program.ab_sheet_group_qty
                    or not isfinite(program.ab_sheet_fixed_price) or program.ab_sheet_fixed_price < 0):
                raise ValidationError(_('Check the website, promotion settings, quantities and price of the imported offer.'))


class LoyaltyRule(models.Model):
    _inherit = 'loyalty.rule'

    @api.constrains('program_id', 'mode', 'product_ids', 'reward_point_mode', 'reward_point_amount')
    def _check_sheet_rule(self):
        imported = self.filtered('program_id.ab_sheet_key')
        if imported:
            imported.program_id.check_access('write')
        for rule in imported:
            if (rule.mode != 'auto' or not rule.product_ids or rule.reward_point_mode != 'order'
                    or rule.reward_point_amount != 1 or len(rule.program_id.rule_ids) != 1):
                raise ValidationError(_('An imported offer requires one automatic rule with eligible products and one grant per order.'))


class LoyaltyReward(models.Model):
    _inherit = 'loyalty.reward'

    @api.constrains('program_id', 'reward_type', 'discount_mode', 'discount_applicability',
                    'discount', 'discount_max_amount', 'discount_product_ids', 'required_points')
    def _check_sheet_reward(self):
        imported = self.filtered('program_id.ab_sheet_key')
        if imported:
            imported.program_id.check_access('write')
        for reward in imported:
            if (reward.reward_type != 'discount' or reward.discount_mode != 'percent'
                    or reward.discount_applicability != 'cheapest' or not reward.discount_product_ids
                    or reward.discount_max_amount or not 0 < reward.discount <= 100
                    or reward.required_points != 1 or len(reward.program_id.reward_ids) != 1
                    or reward.program_id.ab_sheet_fixed_price and reward.discount != 100):
                raise ValidationError(_('An imported offer requires one percentage reward on eligible products, without a discount cap.'))


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _ab_sheet_pricing_lines(self):
        self.ensure_one()
        rows = {}
        for line in self.order_line - self._get_no_effect_on_threshold_lines():
            if (line.display_type or line.reward_id or line.combo_item_id or line.is_delivery
                    or line.product_uom_qty <= 0 or line.price_total <= 0):
                continue
            units = line.product_uom_id._compute_quantity(line.product_uom_qty, line.product_id.uom_id, round=False)
            if units < 1:
                continue
            if not line.tax_ids:
                unit_price = line.price_total / units
                rows[line] = (floor(units), unit_price, unit_price, line.tax_ids, unit_price)
                continue
            base_line = line._prepare_base_line_for_taxes_computation()
            self.env['account.tax']._add_tax_details_in_base_line(base_line, self.company_id)
            details = base_line['tax_details']
            taxes = line.tax_ids.flatten_taxes_hierarchy().filtered(lambda t: t.amount_type != 'fixed')
            net = details['raw_total_excluded_currency'] / units
            gross = net
            reward_price = net
            for tax in details['taxes_data']:
                if tax['tax'] in taxes:
                    amount = tax['raw_tax_amount_currency'] / units
                    gross += amount
                    if tax['tax'].price_include:
                        reward_price += amount
            if gross > 0:
                rows[line] = (floor(units), line.price_total / units, gross, taxes, reward_price)
        return rows

    def _ab_sheet_cart_plan(self, statuses=None):
        if not self.website_id:
            return {}
        rows = self._ab_sheet_pricing_lines()
        if not rows:
            return {}
        domain = fields.Domain(self._get_program_domain()) & fields.Domain([
            ('ab_sheet_key', '!=', False), ('company_id', '=', self.company_id.id),
            ('website_id', '=', self.website_id.id),
            ('rule_ids.product_ids', 'in', [line.product_id.id for line in rows]),
        ])
        programs = self.env['loyalty.program'].search(domain, order='ab_sheet_priority DESC, id')
        statuses = dict(statuses or {})
        missing = programs.filtered(lambda program: program not in statuses)
        if missing:
            statuses.update(super()._program_check_compute_points(missing))
        cart_products = self.order_line.product_id
        proposals = []
        cutoffs = defaultdict(set)
        is_egp = self.currency_id == self.env.ref('base.EGP')
        for program in programs:
            rules = program.rule_ids.filtered('active')
            reward = program.reward_ids.filtered('active')
            if (len(rules) != 1 or len(reward) != 1 or reward in self.disabled_auto_rewards
                    or reward.reward_type != 'discount' or reward.discount_applicability != 'cheapest'
                    or reward.discount_mode != 'percent' or not 0 < reward.discount <= 100
                    or sum(statuses[program].get('points', [])) < reward.required_points
                    or rules.mode != 'auto' or reward.discount_max_amount
                    or program.limit_usage and program.total_order_count >= program.max_usage
                    or program.ab_sheet_fixed_price and (not is_egp or reward.discount != 100)):
                continue
            products = cart_products.filtered_domain(rules._get_valid_product_domain() & reward._get_discount_product_domain())
            products &= rules.product_ids & reward.discount_product_ids
            eligible = sorted((line for line in rows if line.product_id in products),
                              key=lambda line: (rows[line][1], line.id))
            total_qty = sum(rows[line][0] for line in eligible)
            if total_qty < rules.minimum_qty:
                continue
            discounted_qty = total_qty // program.ab_sheet_group_qty * program.ab_sheet_discount_qty
            amounts = {}
            for line in eligible:
                units, price, gross, taxes, reward_price = rows[line]
                take = min(discounted_qty, units)
                if not take:
                    break
                discounted_qty -= take
                fraction = 1.0
                if program.ab_sheet_fixed_price:
                    fraction = min(1, max(0, price - program.ab_sheet_fixed_price) / gross)
                if fraction:
                    amounts[line] = (gross * take * fraction, taxes, reward_price * take * fraction)
            if not amounts:
                continue
            if program.ab_sheet_group_qty == 1:
                for line, values in amounts.items():
                    units = rows[line][0]
                    cutoffs[line].add(units)
                    proposals.append((program, {line: units}, {line: values}, reward.discount))
            else:
                used = {}
                remaining = total_qty - total_qty % program.ab_sheet_group_qty
                for line in eligible:
                    quantity = min(rows[line][0], remaining)
                    if not quantity:
                        break
                    used[line] = quantity
                    cutoffs[line].add(quantity)
                    remaining -= quantity
                proposals.append((program, used, amounts, reward.discount))

        levels = defaultdict(list)
        for program, used, amounts, rate in proposals:
            level = levels[program.ab_sheet_priority]
            if program.ab_sheet_group_qty > 1:
                segments = {(line, end) for line, qty in used.items() for end in cutoffs[line] if end <= qty}
                level.append((program, segments, amounts, rate))
                continue
            line, quantity = next(iter(used.items()))
            gross, taxes, reward_price = amounts[line]
            start = 0
            for end in sorted(cutoffs[line]):
                fraction = (end - start) / quantity
                benefit = gross * fraction, taxes, reward_price * fraction
                level.append((program, {(line, end)}, {line: benefit}, rate))
                start = end

        reserved = set()
        plan = {}
        for priority in sorted(levels, reverse=True):
            options = [option for option in levels[priority] if not reserved.intersection(option[1])]
            candidates = [(lines, self.currency_id.round(sum(a[0] for a in amounts.values()) * rate / 100))
                          for program, lines, amounts, rate in options]
            for index in _best_offers(candidates):
                program, lines, amounts, rate = options[index]
                if candidates[index][1] <= 0:
                    continue
                reserved.update(lines)
                total, per_tax = plan.get(program, (0, defaultdict(float)))
                for gross, taxes, reward_price in amounts.values():
                    total += gross
                    per_tax[taxes] += reward_price
                plan[program] = total, per_tax
        return plan

    def _discountable_cheapest(self, reward):
        if reward.program_id.ab_sheet_key:
            return self._ab_sheet_cart_plan().get(reward.program_id, (0, {}))
        return super()._discountable_cheapest(reward)

    def _program_check_compute_points(self, programs):
        status = super()._program_check_compute_points(programs)
        sheet_programs = programs.filtered('ab_sheet_key')
        if sheet_programs:
            plan = self._ab_sheet_cart_plan(status)
            for program in sheet_programs:
                if program not in plan and 'error' not in status[program]:
                    status[program] = {'error': _('The cart does not qualify for this offer.')}
        return status
