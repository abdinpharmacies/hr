/** @odoo-module **/

import {registry} from "@web/core/registry";
import {patch} from "@web/core/utils/patch";
import "@ab_sales/pos/pos_action";

const approved = (status) => ["pending", "saved"].includes(status);
const PosAction = registry.category("actions").get("ab_sales.pos");

patch(PosAction.prototype, {
    _applySubmissionState(bill, result) {
        const wasApproved = approved(bill.submission_status);
        super._applySubmissionState(...arguments);
        const stock = result.branch_stock;
        if (wasApproved || !approved(bill.submission_status) || !stock
                || stock.store_id !== bill.header?.store_id || this._balanceRefreshUnmounted) return;

        const update = (row, productId) => {
            const details = stock.balances?.[productId];
            if (!Number.isFinite(details?.balance)) return;
            // Replace absolute balances. Replaying an invoice must never subtract twice.
            row.balance = details.balance;
            row.balance_total = details.balance;
            row.pos_balance = details.balance;
            row.has_balance = details.balance > 0;
            row.has_pos_balance = details.balance > 0;
            row.pos_balance_last_sync_at = details.last_sync_at || false;
            row.pos_balance_unavailable = false;
            row.pos_balance_refreshing = false;
            row.pos_balance_age_label = "";
        };
        for (const draft of this.state.bills) {
            if (draft.header?.store_id === stock.store_id) {
                for (const line of draft.lines || []) update(line, line.product_id);
            }
        }
        if (this.currentBill?.header?.store_id !== stock.store_id) return;
        // In-flight reads from before approval cannot restore the old quantity.
        ++this._posBalanceRequestId;
        ++this._linePosBalanceRequestId;
        for (const name of ["_posBalanceTimer", "_linePosBalanceTimer"]) {
            clearTimeout(this[name]);
            this[name] = null;
        }
        for (const product of this.state.productResults || []) update(product, product.id);
        // Refresh search/filter results from the branch, including sold-out products.
        // searchProducts immediately invalidates older search responses.
        this.searchProducts((this.state.productQuery || "").trim());
        this._refreshPosBalancesForLines(this.currentBill, this._linePosBalanceRequestId);
    },
});
