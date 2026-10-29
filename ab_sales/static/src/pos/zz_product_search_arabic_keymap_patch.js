/** @odoo-module **/

import {registry} from "@web/core/registry";
import {patch} from "@web/core/utils/patch";

import {hasArabicChars, hasLatinKeyboardChars, mapArabicToUsQwerty, mapUsToArabicQwerty} from "./utils/keyboard_mapping";

const PRODUCT_LIMIT = 24;

function mergeUniqueProducts(baseRows, fallbackRows, limit = PRODUCT_LIMIT) {
    const merged = [];
    const seenIds = new Set();
    for (const row of [...(baseRows || []), ...(fallbackRows || [])]) {
        const id = parseInt(row?.id || 0, 10);
        if (!id || seenIds.has(id)) {
            continue;
        }
        seenIds.add(id);
        merged.push(row);
        if (merged.length >= limit) {
            break;
        }
    }
    return merged;
}

const PosAction = registry.category("actions").get("ab_sales.pos");

if (PosAction) {
    patch(PosAction.prototype, {
        async searchProducts(query) {
            const sourceQuery = String(query || "").trim();
            const pendingSearch = super.searchProducts(sourceQuery);
            const requestId = this._productSearchRequestId;
            await pendingSearch;
            if (requestId !== this._productSearchRequestId) {
                return;
            }

            if (!sourceQuery) {
                return;
            }
            if (!hasArabicChars(sourceQuery) && !hasLatinKeyboardChars(sourceQuery)) {
                return;
            }
            if (this.state.enableProductSearchKeyboardMapping === false) {
                return;
            }
            if (requestId !== this._productSearchRequestId || (this.state.productQuery || "").trim() !== sourceQuery) {
                return;
            }

            const currentRows = Array.isArray(this.state.productResults) ? this.state.productResults : [];
            if (currentRows.length) {
                return;
            }

            const fallbackQueries = [];
            if (hasArabicChars(sourceQuery)) {
                const mappedEnglish = mapArabicToUsQwerty(sourceQuery);
                if (mappedEnglish && mappedEnglish !== sourceQuery) {
                    fallbackQueries.push(mappedEnglish);
                }
            }
            if (hasLatinKeyboardChars(sourceQuery)) {
                const mappedArabic = mapUsToArabicQwerty(sourceQuery);
                if (mappedArabic && mappedArabic !== sourceQuery) {
                    fallbackQueries.push(mappedArabic);
                }
            }
            const uniqueFallbackQueries = [...new Set(fallbackQueries)];
            if (!uniqueFallbackQueries.length) {
                return;
            }

            const bill = this.currentBill;
            if (!bill) {
                return;
            }

            const storeId = bill?.header?.store_id || null;
            const customerPhone = this.activeCustomerPhone(bill);
            const ctx = storeId ? {pos_store_id: storeId} : {};
            let mergedRows = currentRows;

            for (const fallbackQuery of uniqueFallbackQueries) {
                try {
                    const mappedRows = await this.orm.call("ab_sales_ui_api", "search_products", [], {
                        query: fallbackQuery,
                        limit: PRODUCT_LIMIT,
                        has_balance: this.state.productHasBalanceOnly,
                        has_pos_balance: this.state.productHasPosBalanceOnly,
                        store_id: storeId,
                        customer_phone: customerPhone,
                        item_type: this.state.productItemType || "all",
                        min_price: this.state.productMinPrice,
                        max_price: this.state.productMaxPrice,
                        context: ctx,
                    });
                    if (requestId !== this._productSearchRequestId || (this.state.productQuery || "").trim() !== sourceQuery) {
                        return;
                    }
                    mergedRows = mergeUniqueProducts(mergedRows, mappedRows, PRODUCT_LIMIT);
                    if (mergedRows.length >= PRODUCT_LIMIT) {
                        break;
                    }
                } catch {
                    // Ignore fallback errors and keep searching with any remaining fallback query.
                }
            }

            if (mergedRows.length) {
                this.state.productResults = mergedRows;
                this.state.selectionIndex = -1;
                this.state.qtyBuffer = "";
                this.state.qtyBufferProductId = null;
                this.schedulePosBalanceRefresh(this.state.productResults, storeId);
            }
        },
    });
}
