from odoo import api, models, _


class AbPurchaseDashboard(models.Model):
    _inherit = 'ab_purchase_header'

    @api.model
    def get_purchase_dashboard_payload(self):
        """Read-only, store-scoped overview; pending invoice stock is observed only."""
        user = self.env.user
        can_view_all = (user.has_group('base.group_system')
                        or user.has_group('ab_purchase.group_ab_purchase_manager'))
        store_domain = [] if can_view_all else [('store_id', 'in', user.inventory_store_ids.ids)]
        pending_domain = store_domain + [('status', '=', 'pending')]
        saved_domain = store_domain + [('status', '=', 'saved')]

        pending = self.search(pending_domain, order='create_date desc, id desc', limit=8)
        recent = self.search(store_domain, order='create_date desc, id desc', limit=8)
        observed = self.env['ab_purchase_line'].search(
            [('header_id', 'in', pending.ids)], order='id desc', limit=12,
        )

        inventory_domain = [
            ('model_ref', '=', 'ab_purchase_line'),
            ('status', '=', 'saved'),
            ('qty', '>', 0),
        ] + store_domain
        # The purchase manager may not have inventory read ACLs. The explicit
        # store domain is applied before elevated reading; branch users cannot
        # obtain other stores' inventory data through this endpoint.
        posted_receipts = self.env['ab_inventory'].sudo().search_count(inventory_domain)

        return {
            'store_ids': None if can_view_all else user.inventory_store_ids.ids,
            'pending_count': self.search_count(pending_domain),
            'saved_count': self.search_count(saved_domain),
            'posted_receipts': posted_receipts,
            'observed': [{
                'id': line.id,
                'invoice_id': line.header_id.id,
                'invoice': line.header_id.doc_code,
                'store': line.header_id.store_id.display_name,
                'product': line.product_id.display_name,
                'qty': line.qty,
                'bonus': line.bonus,
                'unit': line.uom_id.display_name,
            } for line in observed],
            'recent': [{
                'id': invoice.id,
                'code': invoice.doc_code,
                'store': invoice.store_id.display_name,
                'supplier': invoice.supplier_id.display_name,
                'status': invoice.status,
            } for invoice in recent],
            'notice': _("Pending purchase quantities are observed inbound only. Stock becomes on-hand after an inventory movement is saved."),
        }
