from odoo import api, fields, models, _

MODEL_MAP = {
    'ab_purchase_header': _('PURCHASE'),
    'ab_purchase_notice_header': _('NOTICE'),
    'ab_purchase_ob_header': _('OPENING BALANCE'),
    'ab_purchase_claim': _('CLAIM'),
}


class AbPurchaseAccountingCommon(models.AbstractModel):
    _name = 'ab_purchase_je_header_delegate_common'
    _inherit = ['ab_accounting_je_header_delegate_common']
    _description = 'ab_purchase_je_header_delegate_common'

    je_header_id = fields.Many2one('ab_accounting_je_header',
                                   delegate=True,
                                   ondelete='cascade', required=True, index=True)

    @api.model
    def default_get(self, default_fields):
        rec = super().default_get(default_fields)
        ref = self.env.ref
        if self._name == 'ab_purchase_ob_header':
            account_id = ref('ab_accounting.ab_accounting_account_guide_inventory').id
        else:
            account_id = ref('ab_accounting.ab_accounting_account_guide_suppliers').id
        rec.update(
            account_id=account_id,
            doctype_id=ref('ab_accounting.ab_accounting_doctype_auto_je').id,
            res_header_id=self.id,
            res_header_ref=self._name,
        )

        return rec

    def name_get(self):
        res = []
        for rec in self:
            model = MODEL_MAP.get(rec._name, 'UNKNOWN')

            res.append((rec.id, f"{model} - {rec.id}"))
        return res

    def write(self, vals):
        self = self.with_context(from_header=True)
        res = super().write(vals)
        if self._name == 'ab_purchase_header':
            self = self.with_context(sudo_confirm=True)
            pur_notice_mo = self.env['ab_purchase_notice_header'].sudo()
            self._override_pur_write(pur_notice_mo, vals)
        elif self._name == 'ab_purchase_notice_header':
            self = self.with_context(sudo_confirm=True)
            self._override_pur_notice_write(vals)
        elif self._name == 'ab_purchase_claim':
            self._override_claim_write()

        return res

    def _override_pur_notice_write(self, vals):
        self = self.sudo()
        for rec in self:
            if rec.je_header_id.mapped('line_ids'):
                je_vals = {}
                if "supplier_id" in vals:
                    je_vals.update({'costcenter_id': rec.supplier_id.costcenter_id.id})
                if "doc_code" in vals:
                    je_vals.update({'doc_no': rec.doc_code})
                if "doc_date" in vals:
                    je_vals.update({'due_date': rec.doc_date})
                if "store_id" in vals:
                    je_vals.update({'store_id': rec.store_id.id})

                if je_vals:
                    rec.je_header_id.sudo().line_ids.write(je_vals)

    def _override_pur_write(self, pur_notice_mo, vals):
        self = self.sudo()
        for rec in self:
            pur_notices = pur_notice_mo.search([('purchase_header_id', '=', rec.id)])
            je_headers_notice = pur_notices.mapped('je_header_id')
            # je_headers_pur = pur_mo.browse(rec.id).je_header_id
            je_headers = rec.je_header_id | je_headers_notice

            # if "store_id" in vals:
            #     inventory_lines = inventory.search(
            #         [("source_id", "=", rec.line_ids.mapped("source_id.id"))]
            #     )
            #     inventory_lines.store_id = rec.store_id.id
            if je_headers.mapped('line_ids'):
                je_vals = {}
                if "supplier_id" in vals:
                    pur_notices.update({'supplier_id': rec.supplier_id.id})
                    je_vals.update({'costcenter_id': rec.supplier_id.costcenter_id.id})
                if "doc_code" in vals:
                    je_vals.update({'doc_no': rec.doc_code})
                if "store_id" in vals:
                    je_vals.update({'store_id': rec.store_id.id})

                if je_vals:
                    je_headers.sudo().line_ids.write(je_vals)

                # Only change due_date of je_header_id of ab_purchase_header (exclude notices)
                if "doc_date" in vals:
                    rec.je_header_id.line_ids.sudo().write({'due_date': rec.doc_date})

    def _override_claim_write(self):
        self = self.sudo()
        for rec in self:
            supplier_account = rec.account_id

            lines_updates = []
            for line in rec.je_header_id.line_ids:
                if line.is_confirmed:
                    continue

                line_vals = {}
                if line.costcenter_id != rec.costcenter_id:
                    line_vals.update({'costcenter_id': rec.costcenter_id})

                if ((not line.claim_id)
                        and (line.account_id == supplier_account)
                        and line.auto_link_claim
                ):
                    line_vals.update({'claim_id': rec.id})
                if line.account_id != supplier_account:
                    if line.claim_id:
                        line_vals.update({'claim_id': False})
                # @todo remove hard coded stor_id
                if line.doc_no != f'CLAIM-{rec.id}':
                    line_vals.update({'doc_no': f'CLAIM-{rec.id}'})
                if not line.store_id:
                    line_vals.update({'store_id': 78})
                if not line.explain:
                    line_vals.update({'explain': rec.description})
                lines_updates.append((1, line.id, line_vals))

            rec.je_header_id.sudo().write({'line_ids': [upd for upd in lines_updates]})
