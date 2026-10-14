/** @odoo-module **/

// Tokens protect display updates; requests are not queued or automatically retried.
const latestRefresh = new WeakMap();

export async function refreshPosBalances(orm, rows, storeId, productKey, isCurrent) {
    const targets = rows.filter((row) => Number.isInteger(row[productKey]) && row[productKey] > 0);
    if (!storeId || !targets.length || !isCurrent()) {
        return;
    }
    const token = {};
    for (const row of targets) {
        latestRefresh.set(row, token);
        row.pos_balance_refreshing = true;
    }
    let balances;
    try {
        balances = await orm.call("ab_sales_pos_api", "pos_refresh_pos_balances", [], {
            store_id: storeId,
            product_ids: [...new Set(targets.map((row) => row[productKey]))],
        });
    } catch {
        // Network/RPC failures have the same display meaning as unavailable SQL.
        balances = null;
    }
    for (const row of targets) {
        if (latestRefresh.get(row) === token) {
            row.pos_balance_refreshing = false;
        }
    }
    if (!isCurrent()) {
        return;
    }
    for (const row of targets) {
        if (latestRefresh.get(row) !== token) {
            continue;
        }
        const value = balances?.[row[productKey]];
        row.pos_balance_unavailable = !Number.isFinite(value);
        if (!row.pos_balance_unavailable) {
            row.pos_balance = value;
        }
    }
}
