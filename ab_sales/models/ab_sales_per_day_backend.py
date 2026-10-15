"""Backend boundary: live committed reads and native sales workflows."""
import math
from odoo import models, _
from odoo.exceptions import UserError
from .ab_sales_pos_backend import selected_server

from datetime import datetime, time, timedelta
from .ab_sales_per_day import SALES_PER_DAY_SQL

class SalesPerDayBackend(models.Model):
    _inherit = 'ab_sales_per_day'

    def _backend_sales_day(self, store, day):
        """Explicit branch daily totals; committed read, no cache writes or commits."""
        start = datetime.combine(day, time.min)
        with self.connect_eplus(server=selected_server(self, store), param_str='?', autocommit=False, propagate_error=True) as conn:
            with conn.cursor() as cur:
                rows = self._backend_daily_rows(
                    cur, start, start + timedelta(days=1), [int(store.eplus_serial)], committed=True)
        result = []
        for branch, product, qty in rows:
            if int(branch) != store.eplus_serial or qty is None or not math.isfinite(float(qty)):
                raise UserError(_('The branch returned invalid sales data.'))
            result.append({'store_eplus_serial': int(branch), 'product_eplus_serial': int(product),
                           'sales_qty': float(qty), 'sale_date': str(day)})
        return result

    def _backend_daily_rows(self, cursor, start, end, branches, committed=False):
        """Query only requested branches; cursor owner determines transaction lifetime."""
        if not branches:
            return []
        sql = SALES_PER_DAY_SQL.format(store_placeholders=','.join('?' for branch in branches))
        if committed:
            sql = sql.replace(' WITH (NOLOCK)', '')
        cursor.execute(sql, (start, end, *branches))
        rows = cursor.fetchall()
        if any(int(row[0]) not in branches for row in rows):
            raise UserError(_('The branch returned invalid sales data.'))
        return rows
