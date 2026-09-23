from odoo import api, fields, models


class JEQuery(models.Model):
    _name = 'ab_accounting_je_line_qry'
    _description = 'ab_accounting_je_line_qry'
    _inherit = ['ab_accounting_je_line_common']
    _auto = False

    je_line_id = fields.Many2one('ab_accounting_je_line')
    credit_val = fields.Float(store=True)
    debit_val = fields.Float(store=True)
    store_id = fields.Many2one('ab_store', store=True)
    store_code = fields.Char(related='store_id.code', string="Store Code")
    due_date = fields.Date(store=True)
    settlement_date = fields.Date(store=True)
    final_date = fields.Date(store=True)
    posted_date = fields.Date(store=True)
    costcenter_id = fields.Many2one('ab_costcenter', store=True)
    costcenter_code = fields.Char(store=True)
    doc_no = fields.Char(store=True)
    explain = fields.Text(store=True)
    account_id = fields.Many2one('ab_accounting_account_guide', store=True)
    children_ids = fields.Many2many(related='account_id.children_ids', string='Children of:')
    parent_account_id = fields.Many2one('ab_accounting_account_guide', store=True)
    with_account_id = fields.Many2one('ab_accounting_account_guide', store=True)
    internal_type = fields.Selection(selection=lambda self: self._get_internal_type_selection())

    parent_path = fields.Char(store=True)
    reconcile = fields.Boolean(store=True)
    has_due_date = fields.Boolean(store=True)
    has_costcenter = fields.Boolean(store=True)
    has_store = fields.Boolean(store=True)

    header_id = fields.Many2one('ab_accounting_je_header', store=True)
    is_frozen = fields.Boolean(store=True)
    is_posted = fields.Boolean(store=True)
    doctype_id = fields.Many2one('ab_accounting_doctype', store=True)
    linked_account_id = fields.Many2one('ab_accounting_account')

    is_confirmed = fields.Boolean(store=True)
    net_val = fields.Float(store=True)
    abs_val = fields.Float(string='Absolute Value', store=True)
    int_val = fields.Float(string='Integer Value', store=True)
    active = fields.Boolean(store=True)
    create_uid = fields.Many2one('res.users', store=True)
    create_date = fields.Date(store=True)
    write_uid = fields.Many2one('res.users', store=True)
    write_date = fields.Date(store=True)

    def name_get(self):
        res = []
        for rec in self:
            value = rec.net_val
            net_val = f"({abs(rec.net_val):,})" if value < 0 else f"{value:,}"
            res.append((rec.id, f"{rec.account_id.name} ({rec.costcenter_id.name}) {net_val}"))
        return res

    def _get_internal_type_selection(self):
        account_guide = self.env['ab_accounting_account_guide']
        account_guide_fields = account_guide.fields_get(allfields=['internal_type'])
        return account_guide_fields['internal_type']['selection']

    def init(self):
        self._cr.execute("""
        DROP VIEW IF EXISTS {table_name} CASCADE;
        ----------------------------------------------------
        CREATE OR REPLACE VIEW {table_name} AS
        SELECT
        je.id,
        je.id as je_line_id,
        je.credit_val,
        je.debit_val,
        je.store_id,
        je.due_date,
        je.settlement_date,
        case  
            when g.reconcile = true then
                case  
                    when je.settlement_date is null then
                        case 
                            when je.due_date<= current_date then current_date
                            else je.due_date
                        end
                    else je.settlement_date
                end
            else
                je.due_date                        
        end as final_date,
        COALESCE (h.posted_date, je.create_date) as posted_date,
        je.costcenter_id,
        cc.code as costcenter_code,
        je.doc_no,
        je.explain,
        je.account_id,
        g.linked_account_id,
        g.parent_id as parent_account_id,
        h.account_id as with_account_id,
        g.internal_type,
        g.parent_path,
        g.reconcile,
        g.has_due_date,
        g.has_costcenter,
        g.has_store,
        je.header_id,
        h.is_frozen,
        h.is_posted,
        h.doctype_id,
        je.is_confirmed,
        je.net_val,
        abs(je.net_val) as abs_val,
        floor(abs(je.net_val)) as int_val,
        je.active ,
        je.create_uid ,
        je.create_date ,
        je.write_uid ,
        je.write_date
        FROM  ab_accounting_je_line je
        left join ab_accounting_account_guide g on g.id = je.account_id
        left join ab_accounting_je_header h on h.id = je.header_id
        left join ab_costcenter cc on cc.id=je.costcenter_id
        """.format(table_name=self._table))
