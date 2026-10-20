/** @odoo-module **/

import {registry} from "@web/core/registry";
import {patch} from "@web/core/utils/patch";
import {_t} from "@web/core/l10n/translation";

const PosAction = registry.category("actions").get("ab_sales.pos");
const UNAVAILABLE_REASON_DIFF = 0.025;

if (PosAction) {
    patch(PosAction.prototype, {
        setup() {
            super.setup(...arguments);
            this.isUnavailableLine = this.isUnavailableLine.bind(this);
            this.updateLineUnavailableReason = this.updateLineUnavailableReason.bind(this);
            this.updateLineUnavailableReasonOther = this.updateLineUnavailableReasonOther.bind(this);
            this._injectUnavailableReasonFieldsInSubmit = this._injectUnavailableReasonFieldsInSubmit.bind(this);

            if (!this._abUnavailableReasonOrmWrapped) {
                const rawCall = this.orm.call.bind(this.orm);
                this.orm.call = async (model, method, args = [], kwargs = {}) => {
                    if (model === "ab_sales_pos_api" && method === "pos_submit" && kwargs && typeof kwargs === "object") {
                        kwargs = this._injectUnavailableReasonFieldsInSubmit(kwargs);
                    }
                    return rawCall(model, method, args, kwargs);
                };
                this._abUnavailableReasonOrmWrapped = true;
            }
        },

        _normalizeBill(bill) {
            const normalized = super._normalizeBill(...arguments);
            const lines = normalized?.lines || [];
            for (const line of lines) {
                line.unavailable_reason = line.unavailable_reason || "";
                line.unavailable_reason_other = line.unavailable_reason_other || "";
            }
            return normalized;
        },

        addProduct(product, qty = 1) {
            const line = super.addProduct(...arguments);
            if (line) {
                if (typeof line.unavailable_reason !== "string") {
                    line.unavailable_reason = "";
                }
                if (typeof line.unavailable_reason_other !== "string") {
                    line.unavailable_reason_other = "";
                }
                this.persistCache();
            }
            return line;
        },

        _lineQtyInBalanceUom(line) {
            const qty = Number.isFinite(line?.qty) ? line.qty : parseFloat(line?.qty || 0) || 0;
            const selectedFactor = Number.isFinite(line?.uom_factor)
                ? line.uom_factor
                : parseFloat(line?.uom_factor || 0) || 0;
            const baseFactor = Number.isFinite(line?.default_uom_factor)
                ? line.default_uom_factor
                : parseFloat(line?.default_uom_factor || 0) || 0;
            const normalizedSelectedFactor = selectedFactor > 0 ? selectedFactor : (baseFactor > 0 ? baseFactor : 1);
            const normalizedBaseFactor = baseFactor > 0 ? baseFactor : normalizedSelectedFactor;
            return qty * normalizedSelectedFactor / normalizedBaseFactor;
        },

        branchShortageFeedback(bill) {
            if (bill?.submission?.status !== "rejected") return null;
            const normalize = (text) => String(text || "").replace(/\s+/g, " ").trim();
            const message = String(bill.submission.message || "").trim();
            const legacy = "Products where requested qty exceeds available balance require a reason before submit.\nIf reason is 'Other', details are required.\n\nMissing lines:\n%s";
            const current = "Current branch stock is insufficient. Select a reason for every affected line; Other requires details.\n%s";
            const formats = [legacy, current,
                _t("Products where requested qty exceeds available balance require a reason before submit.\nIf reason is 'Other', details are required.\n\nMissing lines:\n%s"),
                _t("Current branch stock is insufficient. Select a reason for every affected line; Other requires details.\n%s")];
            const prefix = formats.map((format) => format.split("%s")[0].trim()
                .replace(/[.*+?^${}()|[\]\\]/g, "\\$&").replace(/\s+/g, "\\s+"))
                .map((pattern) => message.match(new RegExp(`^${pattern}\\s*`)))
                .find(Boolean);
            if (!prefix) return null;
            const details = message.slice(prefix[0].length).trim();
            const productName = (text) => normalize(text).replace(/^-\s+/, "").replace(/^\[[^\]]+\]\s*/, "");
            const entries = details.split(/\n|(?:^|\s)-\s+/).filter(Boolean).map(productName);
            const lines = (bill.lines || []).filter((line) => {
                const name = productName(line.product_name);
                return name && entries.some((entry) => entry === name || entry.startsWith(`${name}: `));
            });
            const affected = lines.length ? lines : (bill.lines || []);
            const names = [...new Set(affected.map((line) => line.product_name).filter(Boolean))];
            return {
                lines: affected,
                message: _t("The branch requires a stock shortage reason. Select a reason below each affected product, then retry this invoice. If you select Other, enter details. The displayed balance may differ from the balance used by the branch.") +
                    (names.length ? `\n${names.join("\n")}` : ""),
            };
        },

        isUnavailableLine(line) {
            const bill = (this.state?.bills || []).find((bill) => (bill.lines || []).includes(line));
            if (this.branchShortageFeedback(bill)?.lines.includes(line)) return true;
            const posBalance = Number.isFinite(line?.pos_balance) ? line.pos_balance : parseFloat(line?.pos_balance || NaN);
            const sourceBalance = Number.isFinite(posBalance)
                ? posBalance
                : (Number.isFinite(line?.balance) ? line.balance : parseFloat(line?.balance || 0) || 0);
            const productLines = bill ? bill.lines.filter((item) => item.product_id === line.product_id) : [line];
            const qtyInBalanceUom = productLines.reduce((total, item) => total + this._lineQtyInBalanceUom(item), 0);
            return qtyInBalanceUom > 0 && (qtyInBalanceUom - sourceBalance) > UNAVAILABLE_REASON_DIFF;
        },

        updateLineUnavailableReason(line, value) {
            if (!this.branchBillEditable(this.currentBill)) return;
            if (!line) {
                return;
            }
            line.unavailable_reason = value || "";
            if (line.unavailable_reason !== "other") {
                line.unavailable_reason_other = "";
            }
            this.persistCache();
        },

        updateLineUnavailableReasonOther(line, value) {
            if (!this.branchBillEditable(this.currentBill)) return;
            if (!line) {
                return;
            }
            line.unavailable_reason_other = value || "";
            this.persistCache();
        },

        _injectUnavailableReasonFieldsInSubmit(kwargs) {
            const payload = {...kwargs};
            const token = (kwargs?.header?.pos_client_token || "").trim();
            const targetBill = token
                ? (this.state?.bills || []).find((bill) => (bill?.header?.pos_client_token || "").trim() === token)
                : this.currentBill;
            const sourceLines = targetBill?.lines || [];
            const baseLines = Array.isArray(kwargs?.lines) ? kwargs.lines : [];
            payload.lines = baseLines.map((line, idx) => {
                if (Object.hasOwn(line, "unavailable_reason")) return line;
                const source = sourceLines[idx] || line || {};
                return {
                    ...line,
                    unavailable_reason: source.unavailable_reason || false,
                    unavailable_reason_other: (source.unavailable_reason_other || "").trim(),
                };
            });
            return payload;
        },
    });
}
