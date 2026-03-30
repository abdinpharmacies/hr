/** @odoo-module **/

import {registry} from "@web/core/registry";
import {patch} from "@web/core/utils/patch";

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

        isUnavailableLine(line) {
            const posBalance = Number.isFinite(line?.pos_balance) ? line.pos_balance : parseFloat(line?.pos_balance || NaN);
            const sourceBalance = Number.isFinite(posBalance)
                ? posBalance
                : (Number.isFinite(line?.balance) ? line.balance : parseFloat(line?.balance || 0) || 0);
            const qty = Number.isFinite(line?.qty) ? line.qty : (parseFloat(line?.qty || 0) || 0);
            return qty > 0 && (qty - sourceBalance) > UNAVAILABLE_REASON_DIFF;
        },

        updateLineUnavailableReason(line, value) {
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
                const source = sourceLines[idx] || line || {};
                const requireReason = this.isUnavailableLine(source);
                return {
                    ...line,
                    unavailable_reason: requireReason ? (source.unavailable_reason || false) : false,
                    unavailable_reason_other: requireReason ? (source.unavailable_reason_other || "").trim() : "",
                };
            });
            return payload;
        },
    });
}
