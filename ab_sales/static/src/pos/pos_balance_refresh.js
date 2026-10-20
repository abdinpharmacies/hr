/** @odoo-module **/

import {_t} from "@web/core/l10n/translation";
import {deserializeDateTime} from "@web/core/l10n/dates";

// Tokens protect display updates; requests are not queued or automatically retried.
const latestRefresh = new WeakMap();
const refreshContext = new WeakMap();

export function balanceAgeLabel(timestamp, now = Date.now()) {
    if (!timestamp) return "";
    let synced;
    try { synced = deserializeDateTime(timestamp).toMillis(); } catch { return ""; }
    if (!Number.isFinite(synced)) return "";
    const seconds = Math.floor(Math.max(0, now - synced) / 1000);
    if (seconds < 60) return seconds === 1 ? _t("since 1 second") : _t("since %s seconds", seconds);
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return minutes === 1 ? _t("since 1 minute") : _t("since %s minutes", minutes);
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return hours === 1 ? _t("since 1 hour") : _t("since %s hours", hours);
    const days = Math.floor(hours / 24);
    return days === 1 ? _t("since 1 day") : _t("since %s days", days);
}

export async function refreshPosBalances(orm, rows, storeId, productKey, isCurrent, {showAge = false, manual = false} = {}) {
    const targets = rows.filter((row) => Number.isInteger(row[productKey]) && row[productKey] > 0);
    if (!storeId || !targets.length || !isCurrent()) {
        return;
    }
    const token = {};
    const productIds = new Map(targets.map((row) => [row, row[productKey]]));
    for (const row of targets) {
        const context = `${storeId}:${row[productKey]}`;
        const previous = refreshContext.get(row);
        if (previous !== context) {
            row.pos_balance_age_label = "";
            row.pos_balance_unavailable = false;
            if (previous !== undefined) {
                row.pos_balance_last_sync_at = false;
                row.pos_balance = undefined;
            }
            refreshContext.set(row, context);
        }
        latestRefresh.set(row, token);
        row.pos_balance_refreshing = true;
    }
    let balances;
    try {
        balances = await orm.call("ab_sales_pos_api", "pos_refresh_pos_balances", [], {
            store_id: storeId,
            product_ids: [...new Set(productIds.values())],
            include_sync_metadata: true,
        });
    } catch {
        // Network/RPC failures have the same display meaning as unavailable SQL.
        balances = null;
    }
    for (const row of targets) {
        if (latestRefresh.get(row) === token && row[productKey] === productIds.get(row)) {
            row.pos_balance_refreshing = false;
        }
    }
    if (!isCurrent()) {
        return;
    }
    for (const row of targets) {
        if (latestRefresh.get(row) !== token || row[productKey] !== productIds.get(row)) {
            continue;
        }
        const metadata = balances?.[row[productKey]];
        const wasUnavailable = row.pos_balance_unavailable;
        if (Number.isFinite(metadata?.balance)) {
            row.pos_balance = metadata.balance;
            row.pos_balance_last_sync_at = metadata.last_sync_at || false;
        }
        row.pos_balance_unavailable = !(metadata?.refresh_success === true && Number.isFinite(metadata.balance));
        if (!row.pos_balance_unavailable) {
            row.pos_balance_age_label = "";
        } else if (showAge && (!wasUnavailable || manual)) {
            row.pos_balance_age_label = balanceAgeLabel(row.pos_balance_last_sync_at);
        }
    }
}
