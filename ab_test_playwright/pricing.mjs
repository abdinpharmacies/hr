export function isBusinessRpc(url, method) {
    return new URL(url).pathname.startsWith('/web/dataset/call_kw/') && method !== 'pos_save_draft_cache';
}

export function assertBackendQuote(quote, expected, promotionId, tolerance) {
    const money = (actual, value, label) => {
        if (!Number.isFinite(Number(actual)) || !Number.isFinite(value) || Math.abs(Number(actual) - value) > tolerance) {
            throw new Error(`${label}: expected ${value}, received ${actual}`);
        }
    };
    const applied = expected.promotion ? promotionId : false;
    if ((quote.applied_program_id || false) !== applied) throw new Error('Backend quote applied another promotion');
    if (expected.contract) {
        for (const [field, name] of [['cust_pay', 'customer_pay'], ['company_pay', 'company_pay'],
            ['discount', 'contract_discount'], ['total_after_discount', 'contract_total_after_discount']]) {
            money(quote[field], expected[name], field);
        }
        if (quote.allow_promotions && (quote.selected_program_id || false) !== applied) {
            throw new Error('Backend quote selected another promotion');
        }
    } else {
        money(quote.total_net_amount ?? quote.amount_total_after_promo, expected.customer_pay, 'quote customer payment');
    }
    money(quote.promo_discount_amount || 0, expected.promotion_discount || 0, 'quote promotion discount');
}
