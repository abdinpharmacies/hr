from odoo import api, fields, models


class AbSalesUiApiContract(models.TransientModel):
    _inherit = 'ab_sales_ui_api'

    @api.model
    def _bill_wizard_payload_header_proxy(self, header_payload):
        header = super()._bill_wizard_payload_header_proxy(header_payload)
        value = (header_payload or {}).get('total_after_discount')
        header.total_after_discount = float(value) if value is not None and value != '' else None
        return header

    @api.model
    def _bill_wizard_prepare_payload_print_content(self, payload=None, print_format='a4'):
        payload = dict(payload or {})
        header = dict(payload.get('header') or {})
        lines = payload.get('lines') or []
        if payload.get('document_type', 'sale') == 'sale' and header.get('server_header_id'):
            record_type, record, saved_lines, fmt, settings, content = self._bill_wizard_prepare_print_content(
                header_id=int(header['server_header_id']), print_format=print_format,
            )
            return record_type, record, saved_lines, fmt, settings, content, settings.get('receipt_header') or 'Sales Receipt'
        if payload.get('document_type', 'sale') == 'sale' and lines and all(line.get('product_id') for line in lines):
            pricing = self.env['ab_sales_pos_api']
            program_id = header.get('applied_program_id')
            customer_id = False if header.get('customer_mode') == 'new' else header.get('customer_id')
            if header.get('contract_id'):
                totals = pricing.pos_contract_totals(
                    contract_id=header['contract_id'], store_id=header.get('store_id'), lines=lines,
                    total_invoice_discount=header.get('total_invoice_discount', 0.0),
                    applied_program_id=program_id, manual_clear=not bool(program_id),
                    customer_id=customer_id,
                )
                header.update(total_after_discount=totals['total_after_discount'],
                              total_net_amount=totals['cust_pay'], cust_pay=totals['cust_pay'],
                              company_pay=totals['company_pay'],
                              promo_discount_amount=totals.get('promo_discount_amount', 0.0))
            elif 'applied_program_ids' in self.env['ab_sales_header']._fields:
                totals = pricing.pos_promotions(
                    store_id=header.get('store_id'), lines=lines,
                    applied_program_id=program_id, manual_clear=not bool(program_id),
                    customer_id=customer_id,
                )
                header.update(total_after_discount=totals['amount_total_after_promo'],
                              total_net_amount=totals['total_net_amount'],
                              promo_discount_amount=totals['promo_discount_amount'])
            payload['header'] = header
        return super()._bill_wizard_prepare_payload_print_content(payload=payload, print_format=print_format)

    @api.model
    def _bill_wizard_contract_values_from_lines(self, header, lines, fallback_required):
        contract = getattr(header, 'contract_id', False)
        frozen = getattr(header, 'status', '') in ('pending', 'saved', 'unknown')
        enabled = (getattr(header, 'contract_promotion_pricing', False) if frozen
                   else bool(contract and contract.allow_promotions))
        if not contract or not enabled:
            return super()._bill_wizard_contract_values_from_lines(header, lines, fallback_required)

        original = {line.id: line.qty for line in header.line_ids}
        if frozen and len(lines) == len(original) and all(original.get(line.id) == line.qty for line in lines):
            return {'total_after_discount': header.total_after_discount,
                    'cust_pay': header.cust_pay, 'company_pay': header.company_pay}, header.cust_pay

        values = {
            'store_id': header.store_id.id,
            'customer_id': header.customer_id.id if header.customer_id else False,
            'line_ids': [fields.Command.create({
                'product_id': line.product_id.id, 'uom_id': line.uom_id.id,
                'qty_str': str(line.qty), 'sell_price': line.sell_price,
            }) for line in lines],
        }
        if not frozen:
            values.update(contract_id=contract.id, total_invoice_discount=header.total_invoice_discount)
        if 'applied_program_ids' in self.env['ab_sales_header']._fields:
            values['applied_program_ids'] = [fields.Command.set(header.with_context(active_test=False).applied_program_ids.ids)]
        virtual = self.env['ab_sales_header'].new(values)
        virtual.line_ids._compute_qty()
        virtual.line_ids._compute_amount()
        if frozen:
            total = sum(line.qty * line.sell_price for line in virtual.line_ids)
            if hasattr(virtual, '_compute_promo_totals'):
                virtual._compute_amounts()
                virtual.with_context(force_program_effective=True)._compute_promo_totals()
                total = virtual.amount_total_after_promo
            return {'total_after_discount': total, 'cust_pay': fallback_required,
                    'company_pay': max(0.0, total - fallback_required)}, fallback_required
        virtual._ab_contract_recompute_lines()
        virtual._compute_contract_totals()
        return {'total_after_discount': virtual.total_after_discount, 'cust_pay': virtual.cust_pay,
                'company_pay': virtual.company_pay}, virtual.cust_pay
