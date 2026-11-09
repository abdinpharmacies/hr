from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class AbAccountingJeLine(models.Model):
    _name = 'ab_accounting_je_line'
    _inherit = 'ab_accounting_je_line'

    # fixed_asset_ids = fields.One2many('ab_fixed_asset_assets_inventory', 'je_line_id')
    fixed_asset_id = fields.Many2one('ab_fixed_asset_assets_inventory', index=True)
    has_fixed_asset_je = fields.Boolean(compute='_compute_has_fixed_asset_je',
                                        search='_search_has_fixed_asset_je',
                                        compute_sudo=True)

    @api.depends('account_id')
    def _compute_has_fixed_asset_je(self):
        for rec in self:
            if rec.account_id.internal_type in ('fixed_asset_je', 'fixed_asset'):
                rec.has_fixed_asset_je = True
            else:
                rec.has_fixed_asset_je = False

    def _search_has_fixed_asset_je(self, operator, val):
        # Odoo 19 canonicalizes Boolean searches to membership domains.
        if operator in ('in', 'not in'):
            values = set(val)
            if not values or values == {False, True}:
                matches_all = bool(values) == (operator == 'in')
                return [(1, '=', 1)] if matches_all else [(0, '=', 1)]
            val = True in values
            operator = '=' if operator == 'in' else '!='
        if operator not in ['=', '!='] or not isinstance(val, bool):
            raise UserError(_('Operation not supported'))

        self.env.cr.execute("select je.id from ab_accounting_je_line je "
                            "join ab_accounting_account_guide gg on gg.id=je.account_id "
                            "where gg.internal_type in ('fixed_assets','fixed_asset_je')")
        ids = [row[0] for row in self.env.cr.fetchall()]

        if operator != '=':  # that means it is '!='
            val = not val
        return [('id', 'in' if val else 'not in', ids)]


class AbAccountingJeHeader(models.Model):
    _name = 'ab_accounting_je_header'
    _inherit = 'ab_accounting_je_header'

    has_fixed_asset_je = fields.Boolean(compute='_compute_has_fixed_asset_je',
                                        compute_sudo=True)

    @api.depends('line_ids', 'line_ids.account_id')
    def _compute_has_fixed_asset_je(self):
        for rec in self:
            if rec.line_ids.filtered('has_fixed_asset_je'):
                rec.has_fixed_asset_je = True
            else:
                rec.has_fixed_asset_je = False

    def _msg_is_lines_ok(self, lines):
        msg = super()._msg_is_lines_ok(lines)

        for line in lines:
            if line.has_fixed_asset_je:
                if not line.fixed_asset_id:
                    msg += _(f"\n- You must set target fixed asset for account: {line.account_id.name}.")
                if line.store_id != line.fixed_asset_id.current_store_id:
                    msg += _(f"\n- 'Asset Store' is not same as 'Line Store' for ID: %d" % line.id)
        return msg


class AbAccountingJeLineQry(models.Model):
    _name = 'ab_accounting_je_line_qry'
    _inherit = 'ab_accounting_je_line_qry'

    fixed_asset_id = fields.Many2one(related='je_line_id.fixed_asset_id')
