/** @odoo-module **/

import {registry} from "@web/core/registry";
import {patch} from "@web/core/utils/patch";

const ARABIC_TO_US_QWERTY_MAP = Object.freeze({
    "\u0630": "`",
    "\u0636": "q",
    "\u0635": "w",
    "\u062B": "e",
    "\u0642": "r",
    "\u0641": "t",
    "\u063A": "y",
    "\u0639": "u",
    "\u0647": "i",
    "\u062E": "o",
    "\u062D": "p",
    "\u062C": "[",
    "\u062F": "]",
    "\u0634": "a",
    "\u0633": "s",
    "\u064A": "d",
    "\u06CC": "d",
    "\u0628": "f",
    "\u0644": "g",
    "\u0627": "h",
    "\u062A": "j",
    "\u0646": "k",
    "\u0645": "l",
    "\u0643": ";",
    "\u06A9": ";",
    "\u0637": "'",
    "\u0626": "z",
    "\u0621": "x",
    "\u0624": "c",
    "\u0631": "v",
    "\u0649": "n",
    "\u0629": "m",
    "\u0648": ",",
    "\u0632": ".",
    "\u0638": "/",
    "\u060C": ",",
    "\u061B": ";",
    "\u061F": "/",
});

const ARABIC_CHAR_RE = /[\u0600-\u06FF]/;
const LATIN_KEY_CHAR_RE = /[A-Za-z`\[\];',./]/;
const PRODUCT_LIMIT = 24;
const LAM_ALEF_REPLACEMENTS = Object.freeze({
    "\u0644\u0627": "b",
    "\uFEF5": "b",
    "\uFEF6": "b",
    "\uFEF7": "b",
    "\uFEF8": "b",
    "\uFEF9": "b",
    "\uFEFA": "b",
    "\uFEFB": "b",
    "\uFEFC": "b",
});
const US_TO_ARABIC_QWERTY_MAP = Object.freeze({
    "`": "\u0630",
    "q": "\u0636",
    "w": "\u0635",
    "e": "\u062B",
    "r": "\u0642",
    "t": "\u0641",
    "y": "\u063A",
    "u": "\u0639",
    "i": "\u0647",
    "o": "\u062E",
    "p": "\u062D",
    "[": "\u062C",
    "]": "\u062F",
    "a": "\u0634",
    "s": "\u0633",
    "d": "\u064A",
    "f": "\u0628",
    "g": "\u0644",
    "h": "\u0627",
    "j": "\u062A",
    "k": "\u0646",
    "l": "\u0645",
    ";": "\u0643",
    "'": "\u0637",
    "z": "\u0626",
    "x": "\u0621",
    "c": "\u0624",
    "v": "\u0631",
    "b": "\u0644\u0627",
    "n": "\u0649",
    "m": "\u0629",
    ",": "\u0648",
    ".": "\u0632",
    "/": "\u0638",
});

function hasArabicChars(text) {
    return ARABIC_CHAR_RE.test(String(text || ""));
}

function hasLatinKeyboardChars(text) {
    return LATIN_KEY_CHAR_RE.test(String(text || ""));
}

function mapArabicToUsQwerty(text) {
    let normalized = String(text || "");
    for (const [source, target] of Object.entries(LAM_ALEF_REPLACEMENTS)) {
        normalized = normalized.split(source).join(target);
    }
    return Array.from(normalized, (char) => ARABIC_TO_US_QWERTY_MAP[char] || char).join("").trim();
}

function mapUsToArabicQwerty(text) {
    return Array.from(String(text || ""), (char) => {
        const key = String(char || "").toLowerCase();
        return US_TO_ARABIC_QWERTY_MAP[key] || char;
    }).join("").trim();
}

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
            await super.searchProducts(sourceQuery);

            if (!sourceQuery) {
                return;
            }
            if (!hasArabicChars(sourceQuery) && !hasLatinKeyboardChars(sourceQuery)) {
                return;
            }
            if (this.state.enableProductSearchKeyboardMapping === false) {
                return;
            }
            if ((this.state.productQuery || "").trim() !== sourceQuery) {
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
                        context: ctx,
                    });
                    if ((this.state.productQuery || "").trim() !== sourceQuery) {
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
