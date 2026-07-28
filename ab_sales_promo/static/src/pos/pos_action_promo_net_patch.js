/** @odoo-module **/

import {registry} from "@web/core/registry";
import {patch} from "@web/core/utils/patch";

const PosAction = registry.category("actions").get("ab_sales.pos");

if (PosAction) {
    const originalDefaultPromo = PosAction.prototype._defaultPromo;
    const originalNormalizePromo = PosAction.prototype._normalizePromo;
    const originalRecomputeBill = PosAction.prototype._recomputeBill;
    const originalAvailablePriceSelect = PosAction.prototype.onAvailablePriceSelect;

    patch(PosAction.prototype, {
        _defaultPromo() {
            const promo = originalDefaultPromo ? originalDefaultPromo.call(this, ...arguments) : {};
            promo.total_net_amount = parseFloat(promo.total_net_amount || 0) || 0;
            return promo;
        },
        _normalizePromo(promo) {
            const normalized = originalNormalizePromo
                ? originalNormalizePromo.call(this, promo)
                : this._defaultPromo();
            const raw = promo || {};
            normalized.total_net_amount = parseFloat(raw.total_net_amount || normalized.total_net_amount || 0) || 0;
            return normalized;
        },
        _recomputeBill(bill, {persist = true} = {}) {
            if (originalRecomputeBill) {
                originalRecomputeBill.call(this, bill, {persist});
            }
            if (!bill || !bill.promo) {
                return;
            }
            const net = parseFloat(bill.promo.total_net_amount);
            const hasPromoContext = !!(
                bill.promo.applied_id
                || bill.promo.selected_id
                || (parseFloat(bill.promo.discount_amount || 0) || 0) > 0
            );
            if (hasPromoContext && Number.isFinite(net)) {
                bill.total_net_amount = net;
                if (persist) {
                    this.persistCache();
                }
            }
        },
        onAvailablePriceSelect(line, priceValue) {
            if (originalAvailablePriceSelect) {
                originalAvailablePriceSelect.call(this, line, priceValue);
            }
            this.schedulePromoRefresh(this.currentBill);
        },
        async refreshPromotions(bill) {
            if (this._promoDisabled) {
                return;
            }
            const target = bill || this.currentBill;
            if (!target) {
                return;
            }
            if (!target.promo) {
                target.promo = this._defaultPromo();
            }
            this._promoTimer = null;
            const storeId = target.header?.store_id;
            const payloadLines = this._promoPayloadLines(target);
            if (!storeId || !payloadLines.length) {
                this._resetPromotions(target);
                return;
            }
            const requestId = ++this._promoRequestId;
            target.promo.loading = true;
            this.persistCache();
            try {
                const result = await this.orm.call("ab_sales_pos_api", "pos_promotions", [], {
                    store_id: storeId,
                    lines: payloadLines,
                    applied_program_id: target.promo.selected_id || false,
                    manual_clear: !!target.promo.manual_clear,
                });
                if (requestId !== this._promoRequestId) {
                    return;
                }
                target.promo.available = Array.isArray(result?.available_programs) ? result.available_programs : [];
                const appliedId = parseInt(result?.applied_program_id, 10);
                const selectedId = parseInt(result?.selected_program_id, 10);
                target.promo.applied_id = Number.isFinite(appliedId) ? appliedId : null;
                target.promo.applied_name =
                    result?.applied_program_name || this._findPromoName(target.promo.available, target.promo.applied_id);
                target.promo.selected_id = Number.isFinite(selectedId) ? selectedId : null;
                target.promo.selected_name =
                    result?.selected_program_name || this._findPromoName(target.promo.available, target.promo.selected_id);
                target.promo.message = result?.promo_message || "";
                target.promo.discount_amount = parseFloat(result?.promo_discount_amount || 0) || 0;
                target.promo.total_after = parseFloat(result?.amount_total_after_promo || 0) || 0;
                const totalNetAmount = parseFloat(result?.total_net_amount);
                if (Number.isFinite(totalNetAmount)) {
                    target.promo.total_net_amount = totalNetAmount;
                    target.total_net_amount = totalNetAmount;
                } else {
                    target.promo.total_net_amount = target.total_price || 0;
                    target.total_net_amount = target.total_price || 0;
                }
            } catch (err) {
                const message = err?.message || "";
                if (message.includes("does not exist")) {
                    this._promoDisabled = true;
                    this._resetPromotions(target);
                } else {
                    this.notification.add(message || "Failed to load promotions.", {type: "warning"});
                }
            } finally {
                if (requestId === this._promoRequestId) {
                    target.promo.loading = false;
                    this.persistCache();
                }
            }
        },
    });
}
