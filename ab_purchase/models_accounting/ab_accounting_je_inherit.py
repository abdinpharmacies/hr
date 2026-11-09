from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class AbAccountingJeHeader(models.Model):
    _name = 'ab_accounting_je_header'
    _inherit = ['ab_accounting_je_header']

    je_eplus_serial = fields.Integer(compute='_compute_pur_eplus_serial',
                                     search='_search_pur_eplus_serial',
                                     compute_sudo=True)

    def _search_pur_eplus_serial(self, operator, val):
        # if operator not in ['=', '!='] or not isinstance(val, bool):
        #     raise UserError(_('Operation not supported'))

        pur_mo = self.env['ab_purchase_header'].sudo()
        pur_notice_mo = self.env['ab_purchase_notice_header'].sudo()
        je_pur_headers = pur_mo.search([('eplus_serial', operator, val)])
        je_notice_pur_headers = pur_notice_mo.search([('eplus_serial_calc', operator, val)])
        je_headers = je_pur_headers.mapped('je_header_id') | je_notice_pur_headers.mapped('je_header_id')
        return [('id', 'in', je_headers.ids)]

    @api.depends('res_header_ref', 'res_header_id')
    def _compute_pur_eplus_serial(self):
        for rec in self:
            eplus_serial = 0
            if rec.res_header_ref:
                res = self.env[rec.res_header_ref].browse(rec.res_header_id)
                if rec.res_header_ref == 'ab_purchase_header':
                    eplus_serial = res.eplus_serial
                elif rec.res_header_ref == 'ab_purchase_notice_header':
                    eplus_serial = res.eplus_serial_calc
                # else:
                #     eplus_serial =

            rec.je_eplus_serial = eplus_serial


class AbAccountingJeLine(models.Model):
    _name = 'ab_accounting_je_line'
    _inherit = ['ab_accounting_je_line', 'abdin_et.extra_tools']

    je_eplus_serial = fields.Integer(related='header_id.je_eplus_serial')
    auto_link_claim = fields.Boolean(default=True)
    claim_id = fields.Many2one('ab_purchase_claim', index=True, readonly=True)

    def btn_check_valid_invoice(self):
        msg = self._check_invoice_valid()
        if msg:
            return self.ab_msg(title=_("Not Valid ❌"), message=msg)
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Valid ✔"),
                    'message': _("Valid ✔✔✔"),
                    'type': 'success',  # types: success,warning,danger,info
                    'sticky': True,  # True/False will display for few seconds if false
                },
            }

    def _check_invoice_valid(self, ):
        try:
            msg = ''
            # Get bill details from BeConnect
            supplier_account = self.env.ref('ab_accounting.ab_accounting_account_guide_suppliers')

            je_line_mo = self.env['ab_accounting_je_line'].sudo()
            je_lines = je_line_mo.search([
                ('account_id', '=', supplier_account.id),
                ('id', '!=', self.id),
                '|',
                ('je_eplus_serial', '=', self.doc_no),
                '&',
                ('doc_no', '=', self.doc_no),
                ('je_eplus_serial', '=', 0),
            ])

            supplier_lines = je_lines.filtered(lambda line: line.costcenter_id == self.costcenter_id)
            total_prev_balance = sum(line.net_val * -1 for line in supplier_lines)
            if not supplier_lines and je_lines:
                actual_suppliers = je_lines.mapped('costcenter_id')
                msg += _(f"<br/>Invoice for another supplier {[(sup.code, sup.name) for sup in actual_suppliers]}")
            else:
                current_balance = total_prev_balance - self.debit_val + self.credit_val
                if current_balance >= 0.1:
                    msg += _(
                        f"<br/>This is a partial payment. "
                        f"<br/>Available payment is {total_prev_balance}")
                    # if not (self.explain and self.explain.find(self.costcenter_id.code) != -1):
                    # msg += _(
                    #     f"<br/>This is a partial payment, write vendor code "
                    #     f"{self.costcenter_id.code} "
                    #     f"in Explain to confirm!"
                    #     f"<br/>Available payment is {(total_jes - self.net_val) * -1}")
                elif current_balance <= -0.1:
                    msg += _(f"<br/>Entered value more than available payment, available payment ={total_prev_balance}")
                if any(line.claim_id for line in supplier_lines):
                    claims = [claim.id for claim in supplier_lines.mapped('claim_id') if claim]
                    msg += _(f"<br/>Invoice already closed in claim(s): {claims}")
                if total_prev_balance < 0.1:
                    msg += _('<br/>Previous Balance is less than 0.1 LE, may be this bill is fully returned!')
                all_supplier_lines = je_line_mo.search([
                    ('account_id', '=', supplier_account.id),
                    ('costcenter_id', '=', self.costcenter_id.id),
                ])

                total_supplier_balance = round(sum(line.net_val * -1 for line in all_supplier_lines), 2)
                if total_supplier_balance < 0.1:
                    msg += _("<br/>Supplier Balance is not enough. <br/>"
                             f"... Previous Balance is: {total_supplier_balance + self.net_val}")
        except Exception as ex:
            raise UserError(_(f"Unknown Error ({repr(ex)}"))

        return msg

    def btn_unlink_claim_id(self):
        if self.claim_id:
            self.claim_id = False

    def unlink(self):
        # if rec.claim_id:
        #     raise ValidationError(_("JE is linked with Claim id %s" % rec.claim_id.id))
        # if rec.res_header_ref:
        #     raise ValidationError(_("JE is linked with id %s" % rec.claim_id.id))
        res = super().unlink()
        return res

    @api.constrains('claim_id', 'costcenter_id', 'account_id')
    def _constrains_je_line_claim(self):
        for rec in self:
            if rec.claim_id:
                # account must be 'supplier_account', and costcenter must be 'claim_costcenter'
                if rec.costcenter_id != rec.claim_id.costcenter_id and rec.account_id != rec.claim_id.account_id.id:
                    raise ValidationError(
                        _(f"Error in Claim-{rec.claim_id.id}:"
                          f"\nAccount Must Be Supplier Account {rec.account_id.name}, "
                          f"\nand costcenter must be 'Claim Costcenter' {rec.costcenter_id.name}"))


class AbAccountingJeLineQry(models.Model):
    _name = 'ab_accounting_je_line_qry'
    _inherit = 'ab_accounting_je_line_qry'

    eplus_serial = fields.Integer(related='header_id.je_eplus_serial')
    claim_id = fields.Many2one(related='je_line_id.claim_id')
