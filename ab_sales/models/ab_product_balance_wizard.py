# models/ab_product_balance_wizard.py
from datetime import datetime

from odoo import models, fields, api, _
from odoo.exceptions import AccessError, UserError


class AbProductBalanceWizard(models.TransientModel):
    _name = 'ab_product_balance_wizard'
    _description = 'Product Balance Wizard'

    product_id = fields.Many2one('ab_product')
    balance_html = fields.Html(string="Store Balances", compute='_compute_balance_html')

    balance_data = fields.Json(string="Store Balances", compute='_compute_balance_data')

    @api.model
    def _branch_api_unavailable_reason(self, store, config):
        if not store.eplus_serial or store.eplus_serial <= 0:
            return _('This branch has no E-Plus ID.')
        if not config:
            return _('Branch API is not configured.')
        if (not store.active or not store.allow_sale or store.eplus_serial <= 0
                or config.db_serial <= 0 or config.enrollment_state != 'ready'
                or not config.api_key):
            return _('Branch API connection is not ready.')
        return False

    @api.depends('product_id')
    def _compute_balance_data(self):
        reader = self.env['ab_sales_all_store_balance']
        stores = reader._stores()
        configs = self.env['ab_sales_branch_rpc_config'].sudo().search(
            fields.Domain('active', '=', True) & fields.Domain('store_id', 'in', stores.ids))
        config_by_store = {config.store_id.id: config for config in configs}
        for wizard in self:
            rows = []
            product = wizard.product_id
            snapshot = reader._read_live(product) if product else {}
            if product:
                for store in stores:
                    reason = self._branch_api_unavailable_reason(store, config_by_store.get(store.id))
                    live_reason = snapshot['unavailable_reasons'].get(store.id)
                    pair = (store.id, product.eplus_serial)
                    rows.append({
                        'store_id': store.id,
                        'store_name': store.display_name,
                        'store_code': store.code or '',
                        'balance': snapshot['balances'].get(pair),
                        'cached_fallback': snapshot['cached_fallback'] and pair in snapshot['balances'],
                        'source': snapshot['metadata'].get((store.id, product.eplus_serial), {}).get('source', 'unavailable'),
                        'refreshed_at': snapshot['metadata'].get((store.id, product.eplus_serial), {}).get('refreshed_at', False),
                        'can_refresh': not reason and product.eplus_serial > 0,
                        'unavailable_reason': live_reason or reason or (False if product.eplus_serial > 0 else
                                                        _('Some products are unavailable at the branch.')),
                    })
            wizard.balance_data = {'product_id': product.id or False, 'rows': rows,
                                   'initial_error': snapshot.get('initial_error', False)}

    @api.model
    def refresh_branch_balance(self, product_id, store_id):
        """Read one transfer branch for this informational popup, without E-Plus access.

        Like the central breakdown, this read can cross the employee's sales scope.
        Only this fixed read operation is elevated; transaction permissions are unchanged.
        """
        self.check_access('read')
        if (type(product_id) is not int or product_id <= 0
                or type(store_id) is not int or store_id <= 0):
            raise UserError(_('A valid product and branch are required.'))
        product = self.env['ab_product'].browse(product_id).exists()
        product.check_access('read')
        if not product or product.eplus_serial <= 0:
            raise UserError(_('Some products are unavailable at the branch.'))
        # Validate transfer eligibility anew; never trust client-supplied row metadata.
        store = self.env['ab_sales_all_store_balance']._stores().filtered(lambda s: s.id == store_id)
        if not store:
            raise AccessError(_('This store is not allowed.'))
        config = self.env['ab_sales_branch_rpc_config'].sudo().search(
            fields.Domain('active', '=', True) & fields.Domain('store_id', '=', store.id), limit=1)
        reason = self._branch_api_unavailable_reason(store, config)
        if reason:
            raise UserError(reason)
        started = datetime.utcnow()
        response = config._execute_kw('ab_branch_api', 'get_product_balances',
                                      [config.db_serial, [product.eplus_serial]])
        config._validate_identity(response)
        rows = response.get('data')
        if (not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict)
                or type(rows[0].get('product_eplus_serial')) is not int
                or rows[0]['product_eplus_serial'] != product.eplus_serial
                or type(rows[0].get('store_eplus_serial')) is not int
                or isinstance(rows[0].get('balance'), bool)
                or isinstance(rows[0].get('default_price'), bool)):
            raise UserError(_('The branch returned invalid stock data.'))
        try:
            self.env['ab_sales_branch_client']._validate_balance_rows(store, rows)
            fetched = response.get('fetched_at')
            if not isinstance(fetched, str) or not fetched:
                raise ValueError('Missing branch timestamp')
            fetched = fields.Datetime.to_datetime(fetched)
        except (TypeError, ValueError, OverflowError):
            raise UserError(_('The branch returned invalid stock data.')) from None
        inventory = self.env['ab_sales_inventory']
        # The fixed informational operation above has already authorized this branch.
        # Do not weaken the general transaction client's employee scope checks.
        inventory._apply_balance_cache(store, rows, 'branch_api', started, fetched=fetched)
        snapshot = self.env['ab_sales_all_store_balance']._read([product.eplus_serial])
        pair = (store.id, product.eplus_serial)
        return {'product_id': product.id, 'store_id': store.id,
                'balance': snapshot['balances'].get(pair), **snapshot['metadata'].get(pair, {})}

    @api.depends('product_id')
    def _compute_balance_html(self):
        for wiz in self:
            if wiz.product_id:
                wiz.balance_html = wiz.product_id._get_all_stores_balance_html(
                    [wiz.product_id.eplus_serial]
                )
            else:
                wiz.balance_html = ""
