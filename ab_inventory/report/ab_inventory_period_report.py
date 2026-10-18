from datetime import datetime, time, timedelta

import pytz

from odoo import Command, fields, models, _
from odoo.exceptions import ValidationError


class AbInventoryPeriodReport(models.TransientModel):
    _name = 'ab_inventory_period_report'
    _description = 'Inventory Period Report'

    date_from = fields.Date(string='From Date', required=True, default=fields.Date.today)
    date_to = fields.Date(string='To Date', required=True, default=fields.Date.today)
    store_id = fields.Many2one(
        'ab_store', string='Store', required=True,
        default=lambda self: self.env.user.inventory_store_ids[:1].id,
    )
    product_id = fields.Many2one('ab_product', string='Item')
    line_ids = fields.One2many('ab_inventory_period_report_line', 'report_id', readonly=True)
    movement_line_ids = fields.One2many(
        'ab_inventory_period_movement_line', 'report_id', readonly=True,
    )

    def _utc_start(self, day):
        zone = pytz.timezone(self.env.user.tz or 'UTC')
        local = zone.localize(datetime.combine(day, time.min))
        return local.astimezone(pytz.UTC).replace(tzinfo=None)

    def action_generate(self):
        self.ensure_one()
        if self.date_from > self.date_to:
            raise ValidationError(_("From Date cannot be later than To Date."))
        process = self.env['ab_inventory_process']
        process._check_store(self.store_id.id)

        start = self._utc_start(self.date_from)
        end = self._utc_start(self.date_to + timedelta(days=1))
        movement = self.env['ab_inventory']
        base = [('store_id', '=', self.store_id.id), ('status', '=', 'saved')]
        if self.product_id:
            base.append(('product_id', '=', self.product_id.id))

        def quantities(extra_domain):
            rows = movement._read_group(
                base + extra_domain, ['product_id', 'source_id'], ['qty:sum'],
            )
            return {(product.id, source.id): quantity or 0 for product, source, quantity in rows}

        opening = quantities([('saved_at', '<', start)])
        period_domain = [('saved_at', '>=', start), ('saved_at', '<', end)]
        incoming = quantities(period_domain + [('qty', '>', 0)])
        outgoing = {source_id: -quantity for source_id, quantity in
                    quantities(period_domain + [('qty', '<', 0)]).items()}
        source_ids = sorted(set(opening) | set(incoming) | set(outgoing))
        movement_commands = [Command.clear()]
        if self.product_id:
            running = dict(opening)
            movements = movement.search(
                base + [('saved_at', '>=', start), ('saved_at', '<', end)],
                order='saved_at, id',
            )
            for entry in movements:
                key = (entry.product_id.id, entry.source_id.id)
                before = running.get(key, 0)
                after = before + entry.qty
                movement_commands.append(Command.create({
                    'movement_id': entry.id,
                    'source_id': entry.source_id.id,
                    'opening_qty': before,
                    'incoming_qty': entry.incoming_qty,
                    'outgoing_qty': entry.outgoing_qty,
                    'closing_qty': after,
                }))
                running[key] = after
        self.write({'line_ids': [Command.clear()] + [
            Command.create({
                'product_id': source_id[0],
                'source_id': source_id[1],
                'opening_qty': opening.get(source_id, 0),
                'incoming_qty': incoming.get(source_id, 0),
                'outgoing_qty': outgoing.get(source_id, 0),
                'closing_qty': opening.get(source_id, 0)
                               + incoming.get(source_id, 0)
                               - outgoing.get(source_id, 0),
            }) for source_id in source_ids
        ], 'movement_line_ids': movement_commands})
        return {
            'type': 'ir.actions.act_window',
            'name': _('Inventory Period Report'),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }


class AbInventoryPeriodReportLine(models.TransientModel):
    _name = 'ab_inventory_period_report_line'
    _description = 'Inventory Period Report Line'
    _order = 'source_id'

    report_id = fields.Many2one('ab_inventory_period_report', required=True, ondelete='cascade')
    source_id = fields.Many2one('ab_product_source', string='Batch / Source', readonly=True)
    product_id = fields.Many2one('ab_product', string='Item', readonly=True)
    opening_qty = fields.Float(digits=(20, 6), string='Opening', readonly=True)
    incoming_qty = fields.Float(digits=(20, 6), string='Incoming', readonly=True)
    outgoing_qty = fields.Float(digits=(20, 6), string='Outgoing', readonly=True)
    closing_qty = fields.Float(digits=(20, 6), string='Closing', readonly=True)


class AbInventoryPeriodMovementLine(models.TransientModel):
    _name = 'ab_inventory_period_movement_line'
    _description = 'Inventory Period Movement Line'
    _order = 'id'

    report_id = fields.Many2one('ab_inventory_period_report', required=True, ondelete='cascade')
    movement_id = fields.Many2one('ab_inventory', string='Movement', readonly=True)
    saved_at = fields.Datetime(related='movement_id.saved_at', string='Saved At')
    source_id = fields.Many2one('ab_product_source', string='Batch / Source', readonly=True)
    opening_qty = fields.Float(digits=(20, 6), string='Opening', readonly=True)
    incoming_qty = fields.Float(digits=(20, 6), string='Incoming', readonly=True)
    outgoing_qty = fields.Float(digits=(20, 6), string='Outgoing', readonly=True)
    closing_qty = fields.Float(digits=(20, 6), string='Closing', readonly=True)
