import datetime

# -*- coding: utf-8 -*-
from odoo import fields
import datetime


class Many2oneUnconstraint(fields.Many2one):
    """
    This class for creating Many2one relation without creating a fkey constraint
    """

    def __int__(self, **kwargs):
        super(Many2oneUnconstraint, self).__int__(**kwargs)

    def update_db_foreign_key(self, model, column):
        """
        Delete fkey constraint if exists.
        """
        model_table = model._table
        connname = '%s_%s_fkey' % (model._table, self.name)
        model.env.cr.execute(f"""
            alter table {model_table} drop constraint IF EXISTS  {connname};
            """)
        model.env.cr.commit()


def daterange(start_date, end_date, step_days):
    for i in range(int((end_date - start_date).days),0, step_days*-1):
        yield start_date + datetime.timedelta(i)
