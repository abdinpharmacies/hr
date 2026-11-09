import pandas as pd
from odoo import api, fields, models, _

PARAM_STR = '%s'


class EplusReplicationCheck(models.AbstractModel):
    _name = 'ab_eplus_replication'
    _inherit = 'ab_eplus_replication'

    def get_df(self, sql, params=None):
        with self.connect_eplus(param_str=PARAM_STR) as conn:
            df = pd.read_sql_query(sql, conn, params=params)
        return df

    @staticmethod
    def convert_to_df(data, columns=None):
        columns = columns or ['col']
        df = pd.DataFrame(data, columns=columns)
        return df

    @staticmethod
    def oprint(data):
        print(data)

    def get_not_replicated(self, eplus_df, model_name):
        method_name = self.METHODS_MAP.get(model_name)
        odoo_ids = self.env[model_name].search([]).mapped('eplus_serial')

        odoo_df = self.convert_to_df(odoo_ids, )

        field_name = eplus_df.columns[0]

        # Merge with an outer join and identify rows where df2['Column2'] is NaN
        merged_df = eplus_df.merge(odoo_df, left_on=field_name, right_on='col', how='left', indicator=True)

        # Filter the rows where the merge indicator shows 'left_only'
        not_replicated_df = merged_df[merged_df['_merge'] == 'left_only']

        if not_replicated_df.empty:
            return

        # Extract the relevant column
        not_replicated_df = not_replicated_df[[field_name]]
        serials = ','.join(not_replicated_df[field_name].astype(int).astype(str).tolist())

        getattr(self, method_name)(where_extra_and=f" and main.{field_name} in ({serials})",
                                   replicate_all=True)

        # not_replicated_df['pth_id'].apply(lambda x: self.get_purchase_header(int(x)))
        return not_replicated_df

    def action_eplus_replicate(self):
        self = self.with_user(2)
        self.replicate_ab_product()
        self.replicate_ab_supplier()

        # self.replicate_ab_store()

        self.replicate_ab_purchase_header(where_extra_and=" and main.sec_insert_date>'2024-01-01' and pth_paid=0 ")
        self.replicate_ab_purchase_line(where_extra_and=" and h.sec_insert_date>'2024-01-01' and pth_paid=0 ")

        self.submit_purchases_in_inventory()

        self.replicate_purchase_returns(where_extra_and=" and h.sec_insert_date>'2024-01-01' and pth_paid=0 ")

        self.replicate_purchase_g_returns(where_extra_and=" and h.sec_insert_date>'2024-05-30' ", replicate_all=True)

        self.submit_purchase_returns_in_inventory()
