/** @odoo-module **/

import { registry } from "@web/core/registry";
import { patch } from "@web/core/utils/patch";

const PosAction = registry.category("actions").get("ab_sales.pos");

if (PosAction) {
    const originalSetup = PosAction.prototype.setup;
    const originalNormalizeBill = PosAction.prototype._normalizeBill;
    const originalCreateNewBill = PosAction.prototype.createNewBill;
    const originalRecomputeBill = PosAction.prototype._recomputeBill;
    const originalUpdateLineQty = PosAction.prototype.updateLineQty;
    const originalUpdateLineSellPrice = PosAction.prototype.updateLineSellPrice;
    const originalOnAvailablePriceSelect = PosAction.prototype.onAvailablePriceSelect;
    const originalRemoveLine = PosAction.prototype.removeLine;
    const originalSchedulePromoRefresh = PosAction.prototype.schedulePromoRefresh;
    const originalRefreshPromotions = PosAction.prototype.refreshPromotions;
    const originalBuildSubmitHeader = PosAction.prototype._buildSubmitHeader;

    patch(PosAction.prototype, {
        setup() {
            originalSetup.call(this, ...arguments);
            this.contractValue = this.contractValue.bind(this);
            this.onContractM2OUpdate = this.onContractM2OUpdate.bind(this);
            this._scheduleContractTotals = this._scheduleContractTotals.bind(this);
            this._refreshContractTotals = this._refreshContractTotals.bind(this);
            this._contractPayloadLines = this._contractPayloadLines.bind(this);
            this._contractTotalsTimer = null;
            this._contractTotalsRequestId = 0;
        },

        _normalizeBill(bill) {
            const normalized = originalNormalizeBill.call(this, bill);
            normalized.header.contract_id = normalized.header.contract_id || null;
            normalized.header.contract_name = normalized.header.contract_name || "";
            return normalized;
        },

        createNewBill(storeId) {
            const result = originalCreateNewBill.call(this, storeId);
            const bill = this.currentBill;
            if (bill?.header) {
                if (!("contract_id" in bill.header)) {
                    bill.header.contract_id = null;
                }
                if (!("contract_name" in bill.header)) {
                    bill.header.contract_name = "";
                }
                bill.updated_at = new Date().toISOString();
                this.persistCache();
            }
            return result;
        },

        contractValue() {
            const bill = this.currentBill;
            if (!bill?.header?.contract_id) {
                return false;
            }
            return {
                id: bill.header.contract_id,
                display_name: bill.header.contract_name || "",
            };
        },

        onContractM2OUpdate(value) {
            const bill = this.currentBill;
            if (!bill) {
                return;
            }
            if (!value || !value.id) {
                bill.header.contract_id = null;
                bill.header.contract_name = "";
            } else {
                bill.header.contract_id = value.id;
                bill.header.contract_name = value.display_name || "";
            }
            bill.updated_at = new Date().toISOString();
            this.persistCache();
            if (bill.header.contract_id) {
                this._resetPromotions(bill);
            } else {
                this.schedulePromoRefresh(bill);
            }
            this._scheduleContractTotals(bill, {immediate: true});
        },

        _contractPayloadLines(bill) {
            const lines = bill?.lines || [];
            return lines
                .filter((line) => line.product_id)
                .map((line) => ({
                    product_id: line.product_id,
                    qty_str: line.qty_str || "1",
                    sell_price: line.sell_price,
                }));
        },

        _scheduleContractTotals(bill, {immediate = false} = {}) {
            if (!bill) {
                return;
            }
            if (!bill.header?.contract_id) {
                bill.total_net_amount = bill.total_price || 0;
                if (immediate) {
                    bill.updated_at = new Date().toISOString();
                    this.persistCache();
                }
                return;
            }
            if (this._contractTotalsTimer) {
                clearTimeout(this._contractTotalsTimer);
                this._contractTotalsTimer = null;
            }
            if (immediate) {
                this._refreshContractTotals(bill);
                return;
            }
            this._contractTotalsTimer = setTimeout(() => {
                this._refreshContractTotals(bill);
            }, 300);
        },

        async _refreshContractTotals(bill) {
            const contractId = bill?.header?.contract_id;
            if (!contractId) {
                if (bill) {
                    bill.total_net_amount = bill.total_price || 0;
                    bill.updated_at = new Date().toISOString();
                    this.persistCache();
                }
                return;
            }
            const lines = this._contractPayloadLines(bill);
            if (!lines.length) {
                bill.total_net_amount = 0;
                bill.updated_at = new Date().toISOString();
                this.persistCache();
                return;
            }
            const requestId = ++this._contractTotalsRequestId;
            try {
                const result = await this.orm.call("ab_sales_pos_api", "pos_contract_totals", [], {
                    contract_id: contractId,
                    lines,
                });
                if (requestId !== this._contractTotalsRequestId) {
                    return;
                }
                const stillExists = this.state?.bills?.some((b) => b.id === bill.id);
                if (!stillExists) {
                    return;
                }
                bill.total_net_amount = parseFloat(result?.cust_pay || 0) || 0;
                bill.contract_totals = {
                    discount: parseFloat(result?.discount || 0) || 0,
                    total_after_discount: parseFloat(result?.total_after_discount || 0) || 0,
                    cust_pay: parseFloat(result?.cust_pay || 0) || 0,
                    company_pay: parseFloat(result?.company_pay || 0) || 0,
                };
                bill.updated_at = new Date().toISOString();
                this.persistCache();
            } catch (err) {
                bill.total_net_amount = bill.total_price || 0;
                bill.updated_at = new Date().toISOString();
                this.persistCache();
            }
        },

        _recomputeBill(bill, options = {}) {
            const prevNet = bill ? bill.total_net_amount : null;
            originalRecomputeBill.call(this, bill, options);
            if (bill?.header?.contract_id) {
                if (bill.contract_totals) {
                    const custPay = parseFloat(bill.contract_totals.cust_pay || 0) || 0;
                    bill.total_net_amount = custPay;
                } else if (prevNet !== null && prevNet !== undefined) {
                    bill.total_net_amount = prevNet;
                }
            }
            this._scheduleContractTotals(bill);
        },

        updateLineQty(line, value) {
            originalUpdateLineQty.call(this, line, value);
            this._scheduleContractTotals(this.currentBill);
        },

        updateLineSellPrice(line, value) {
            originalUpdateLineSellPrice.call(this, line, value);
            this._scheduleContractTotals(this.currentBill);
        },

        onAvailablePriceSelect(line, priceValue) {
            originalOnAvailablePriceSelect.call(this, line, priceValue);
            this._scheduleContractTotals(this.currentBill);
        },

        removeLine(line) {
            originalRemoveLine.call(this, line);
            this._scheduleContractTotals(this.currentBill);
        },

        schedulePromoRefresh(bill) {
            const target = bill || this.currentBill;
            if (target?.header?.contract_id) {
                this._resetPromotions(target);
                return;
            }
            return originalSchedulePromoRefresh.call(this, bill);
        },

        async refreshPromotions(bill) {
            const target = bill || this.currentBill;
            if (target?.header?.contract_id) {
                this._resetPromotions(target);
                return;
            }
            await originalRefreshPromotions.call(this, bill);
        },

        _buildSubmitHeader(bill) {
            const header = originalBuildSubmitHeader.call(this, bill);
            header.contract_id = bill.header.contract_id || false;
            return header;
        },
    });
}
