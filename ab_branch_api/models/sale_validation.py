import math
from collections import defaultdict

from odoo import models, _
from odoo.exceptions import AccessError, UserError

from .routing import current_request, request_store


class ApiSaleValidation(models.Model):
    _inherit = 'ab_sales_header'

    def _unavailable_lines_missing_reason(self):
        if not current_request(self):
            return super()._unavailable_lines_missing_reason()
        self.ensure_one()
        self.check_access('read')
        self.line_ids.check_access('read')
        if self.store_id != request_store(self):
            raise AccessError(_('The SQL store does not match the authorized API store.'))
        products = self.line_ids.product_id
        products.check_access('read')
        serials = sorted(set(products.mapped('eplus_serial')))
        if any(not serial for serial in serials):
            raise UserError(_('Line with missing product E-Plus serial.'))
        balances = {}
        self.env['ab_branch_api']._business_permissions('sale')
        inventory = self.env['ab_sales_inventory']
        try:
            for offset in range(0, len(serials), 200):
                rows = inventory._backend_inventory_snapshot(self.store_id, serials[offset:offset + 200])
                for row in rows:
                    serial = row['product_eplus_serial']
                    balance = float(row['balance'])
                    if (serial in balances or serial not in serials
                            or row['store_eplus_serial'] != self.store_id.eplus_serial
                            or not math.isfinite(balance) or balance < 0):
                        raise UserError(_('The branch returned invalid stock data.'))
                    balances[serial] = balance
        except AccessError:
            raise
        except Exception as error:
            raise UserError(_('Unable to verify current branch stock. Retry before submitting this invoice.')) from error
        if set(balances) != set(serials):
            raise UserError(_('Some invoice products are inactive or missing from branch stock data. Review the products before submitting.'))
        requested = defaultdict(float)
        for line in self.line_ids:
            if (not line.uom_id or line.uom_id.category_id != line.product_id.uom_category_id
                    or not math.isfinite(line.uom_id.factor) or line.uom_id.factor <= 0
                    or not math.isfinite(line.product_id.uom_id.factor) or line.product_id.uom_id.factor <= 0):
                raise UserError(_('Branch product unit is missing or ambiguous.'))
            quantity = self._line_qty_in_balance_uom(line)
            if not math.isfinite(quantity) or quantity <= 0:
                raise UserError(_('Invalid quantity in a line (<= 0).'))
            requested[line.product_id.eplus_serial] += quantity
        missing = self.line_ids.filtered(lambda line:
            requested[line.product_id.eplus_serial] - balances[line.product_id.eplus_serial] > self._UNAVAILABLE_REASON_DIFF
            and (not line.unavailable_reason or (line.unavailable_reason == 'other'
                and not (line.unavailable_reason_other or '').strip())))
        if missing:
            details = []
            for product in missing.product_id:
                serial = product.eplus_serial
                details.append(_('%(product)s: requested %(requested).3f, available %(available).3f %(unit)s') % {
                    'product': product.display_name, 'requested': requested[serial],
                    'available': balances[serial], 'unit': product.uom_id.display_name})
            raise UserError(_('Current branch stock is insufficient. Select a reason for every affected line; Other requires details.\n%s') % '\n'.join(details))
        return missing
