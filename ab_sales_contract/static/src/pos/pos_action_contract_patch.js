/** @odoo-module **/

import { registry } from "@web/core/registry";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

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
            this._manualPromotionBillIds = new Set();
            originalSetup.call(this, ...arguments);
            const refreshPromotions = this.refreshPromotions;
            this.refreshPromotions = (bill) => {
                const target = bill || this.currentBill;
                if (this._contractManualPromotions(target)) {
                    return target.header.contract_id
                        ? this._refreshContractTotals(target)
                        : this._refreshManualPromotions(target);
                }
                return refreshPromotions.call(this, bill);
            };
            const buildPrintPayload = this._buildCurrentBillPrintPayload;
            if (buildPrintPayload) {
                this._buildCurrentBillPrintPayload = () => {
                    const bill = this.currentBill;
                    const payload = buildPrintPayload();
                    Object.assign(payload.header, {
                        server_header_id: !this.billEditable(bill) ? (bill.odoo_header_id || false) : false,
                        store_id: bill.header.store_id || false,
                        customer_id: bill.header.customer_mode === "new" ? false : bill.header.customer_id || false,
                        customer_mode: bill.header.customer_mode,
                        contract_id: bill.header.contract_id || false,
                        contract_name: bill.header.contract_name || "",
                        total_after_discount: this.totalAfterDiscount(bill),
                        total_invoice_discount: bill.header.total_invoice_discount || 0,
                        applied_program_id: bill.promo?.applied_id || false,
                        company_pay: bill.contract_totals?.company_pay ?? 0,
                        cust_pay: bill.contract_totals?.cust_pay ?? bill.total_net_amount,
                    });
                    const sourceLines = bill.lines.filter((line) => line.product_name || line.product_code
                        || Number(line.qty) || Number(line.sell_price) || Number(line.net_amount));
                    payload.lines.forEach((line, index) => {
                        line.product_id = sourceLines[index]?.product_id || false;
                        line.uom_id = sourceLines[index]?.uom_id || false;
                    });
                    return payload;
                };
            }
            this.contractValue = this.contractValue.bind(this);
            this.onContractM2OUpdate = this.onContractM2OUpdate.bind(this);
            this.onTotalInvoiceDiscountInput = this.onTotalInvoiceDiscountInput.bind(this);
            this._scheduleContractTotals = this._scheduleContractTotals.bind(this);
            this._refreshContractTotals = this._refreshContractTotals.bind(this);
            this._contractPayloadLines = this._contractPayloadLines.bind(this);
            this._contractTotalsTimer = null;
            this._contractTotalsRequestId = 0;
            this._contractSelectionRequestId = 0;
        },

        totalAfterDiscount(bill) {
            const amount = bill?.header?.contract_id
                ? bill.contract_totals?.total_after_discount
                : (bill?.promo?.applied_id ? bill.promo.total_after : bill?.total_price);
            if (amount !== null && amount !== undefined && amount !== "" && Number.isFinite(Number(amount))) {
                return Number(amount);
            }
            return Number(bill?.total_price || 0);
        },

        _normalizeBill(bill) {
            const normalized = originalNormalizeBill.call(this, bill);
            normalized.header.contract_id = normalized.header.contract_id || null;
            normalized.header.contract_allow_promotions = !!normalized.header.contract_allow_promotions;
            normalized.header.contract_name = normalized.header.contract_name || "";
            normalized.header.contract_allow_total_invoice_discount = !!normalized.header.contract_allow_total_invoice_discount;
            normalized.header.contract_total_invoice_discount_source =
                normalized.header.contract_total_invoice_discount_source || "our_company";
            normalized.header.total_invoice_discount = parseFloat(normalized.header.total_invoice_discount || 0) || 0;
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
                if (!("contract_allow_total_invoice_discount" in bill.header)) {
                    bill.header.contract_allow_total_invoice_discount = false;
                }
                if (!("contract_total_invoice_discount_source" in bill.header)) {
                    bill.header.contract_total_invoice_discount_source = "our_company";
                }
                if (!("total_invoice_discount" in bill.header)) {
                    bill.header.total_invoice_discount = 0;
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

        async onContractM2OUpdate(value) {
            const bill = this.currentBill;
            if (!bill || !this.billEditable(bill)) {
                return;
            }
            const selectionRequest = ++this._contractSelectionRequestId;
            this._invalidateContractPricing();
            if (bill.promo) {
                bill.promo.loading = false;
            }
            let contract;
            if (value?.id) {
                try {
                    [contract] = await this.orm.read("ab_contract", [value.id], ["name", "allow_promotions"]);
                    if (selectionRequest !== this._contractSelectionRequestId || !this.billEditable(bill)
                        || !this.state.bills.some((candidate) => candidate.id === bill.id)) {
                        return;
                    }
                    if (!contract) {
                        return;
                    }
                } catch (err) {
                    if (selectionRequest === this._contractSelectionRequestId) {
                        this.notification.add(err?.message || _t("Failed to load contract."), {type: "danger"});
                    }
                    return;
                }
            }
            this._invalidateContractPricing();
            if (contract || bill.header.contract_id) {
                this._manualPromotionBillIds.add(bill.id);
            }
            const selectedId = bill.promo?.selected_id;
            const selectedName = bill.promo?.selected_name;
            const manualClear = !!bill.promo?.manual_clear;
            bill.header.contract_id = contract ? value.id : null;
            bill.header.contract_allow_promotions = !!contract?.allow_promotions;
            bill.header.contract_name = contract ? contract.name || value.display_name || "" : "";
            bill.header.contract_allow_total_invoice_discount = false;
            bill.header.contract_total_invoice_discount_source = "our_company";
            bill.header.total_invoice_discount = 0;
            bill.contract_totals = null;
            this._resetPromotions(bill);
            if (!contract) {
                bill.promo.selected_id = selectedId || null;
                bill.promo.selected_name = selectedName || "";
                bill.promo.manual_clear = manualClear;
            }
            bill.updated_at = new Date().toISOString();
            this.persistCache();
            return this.refreshPromotions(bill);
        },

        _contractManualPromotions(bill) {
            if (bill?.header?.contract_id) {
                this._manualPromotionBillIds.add(bill.id);
            }
            return !!bill && this._manualPromotionBillIds.has(bill.id);
        },

        _invalidateContractPricing() {
            ++this._contractTotalsRequestId;
            ++this._promoRequestId;
            clearTimeout(this._contractTotalsTimer);
            clearTimeout(this._promoTimer);
            this._contractTotalsTimer = null;
            this._promoTimer = null;
        },

        _contractPromotionInput(bill) {
            return JSON.stringify([bill.header.contract_id || false, bill.header.store_id,
                bill.header.customer_mode === "new" ? false : bill.header.customer_id || false,
                this._contractPayloadLines(bill), bill.header.total_invoice_discount,
                bill.promo?.selected_id, bill.promo?.manual_clear]);
        },

        _contractPromotionCurrent(bill, input) {
            return this.billEditable(bill) && input === this._contractPromotionInput(bill)
                && this.state.bills.some((candidate) => candidate.id === bill.id);
        },

        _clearContractPromotionAmounts(bill) {
            bill.promo.discount_amount = 0;
            bill.promo.total_after = bill.total_price || 0;
            bill.promo.total_net_amount = bill.total_price || 0;
            bill.total_net_amount = bill.total_price || 0;
            bill.contract_totals = null;
        },

        _applyManualPromotionResult(bill, result) {
            const requestedId = bill.promo.selected_id;
            bill.promo.available = Array.isArray(result.available_programs) ? result.available_programs : [];
            bill.promo.applied_id = requestedId && result.applied_program_id === requestedId ? requestedId : null;
            bill.promo.applied_name = bill.promo.applied_id ? result.applied_program_name || "" : "";
            bill.promo.selected_id = requestedId && result.selected_program_id === requestedId ? requestedId : null;
            bill.promo.selected_name = bill.promo.selected_id ? result.selected_program_name || "" : "";
            bill.promo.message = bill.promo.selected_id ? result.promo_message || "" : "";
            bill.promo.discount_amount = Number(result.promo_discount_amount || 0);
            bill.promo.total_after = Number(result.amount_total_after_promo || 0);
            const net = Number(result.cust_pay ?? result.total_net_amount ?? bill.total_price ?? 0);
            bill.promo.total_net_amount = net;
            bill.total_net_amount = net;
        },

        async _refreshManualPromotions(bill) {
            if (!this.billEditable(bill) || this._promoDisabled) {
                return;
            }
            this._invalidateContractPricing();
            if (!bill.promo) {
                bill.promo = this._defaultPromo();
            }
            const lines = this._promoPayloadLines(bill);
            if (!bill.header.store_id || !lines.length) {
                this._resetPromotions(bill);
                return;
            }
            if (!bill.promo.applied_id) {
                this._clearContractPromotionAmounts(bill);
            }
            const input = this._contractPromotionInput(bill);
            const requestId = ++this._promoRequestId;
            const kwargs = {
                store_id: bill.header.store_id,
                lines,
                applied_program_id: bill.promo.selected_id || false,
                manual_clear: true,
            };
            if (PosAction.components?.AbSalesPosPromoPanel) {
                kwargs.customer_id = bill.header.customer_mode === "new" ? false : bill.header.customer_id || false;
            }
            bill.promo.loading = true;
            this.persistCache();
            try {
                const result = await this.orm.call("ab_sales_pos_api", "pos_promotions", [], kwargs);
                if (requestId !== this._promoRequestId || !this._contractPromotionCurrent(bill, input)) {
                    return;
                }
                this._applyManualPromotionResult(bill, result);
            } catch (err) {
                if (requestId === this._promoRequestId && this._contractPromotionCurrent(bill, input)) {
                    if (err?.message) {
                        this.notification.add(err.message, {type: "warning"});
                    }
                }
            } finally {
                if (requestId === this._promoRequestId) {
                    bill.promo.loading = false;
                    this.persistCache();
                }
            }
        },

        onTotalInvoiceDiscountInput(value) {
            const bill = this.currentBill;
            if (!bill?.header) {
                return;
            }
            const discount = Math.max(0, parseFloat(value || 0) || 0);
            bill.header.total_invoice_discount = discount;
            bill.updated_at = new Date().toISOString();
            this.persistCache();
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
                    uom_id: line.uom_id || false,
                }));
        },

        _scheduleContractTotals(bill, {immediate = false} = {}) {
            if (!bill || !this.billEditable(bill)) {
                return;
            }
            if (!bill.header?.contract_id) {
                if (!bill.promo?.applied_id) {
                    bill.total_net_amount = bill.total_price || 0;
                }
                bill.header.contract_allow_total_invoice_discount = false;
                bill.header.contract_allow_promotions = false;
                bill.header.contract_total_invoice_discount_source = "our_company";
                bill.header.total_invoice_discount = 0;
                bill.contract_totals = null;
                if (immediate) {
                    bill.updated_at = new Date().toISOString();
                    this.persistCache();
                }
                return;
            }
            this._contractManualPromotions(bill);
            this._invalidateContractPricing();
            if (immediate) {
                this._refreshContractTotals(bill);
                return;
            }
            this._contractTotalsTimer = setTimeout(() => {
                this._refreshContractTotals(bill);
            }, 300);
        },

        async _refreshContractTotals(bill) {
            if (!bill || !this.billEditable(bill)) {
                return;
            }
            const contractId = bill?.header?.contract_id;
            if (!contractId) {
                if (bill) {
                    bill.total_net_amount = bill.total_price || 0;
                    bill.updated_at = new Date().toISOString();
                    this.persistCache();
                }
                return;
            }
            this._contractManualPromotions(bill);
            this._invalidateContractPricing();
            if (!bill.promo) {
                bill.promo = this._defaultPromo();
            }
            if (!bill.promo.applied_id) {
                this._clearContractPromotionAmounts(bill);
            }
            const lines = this._contractPayloadLines(bill);
            const customerId = bill.header.customer_mode === "new" ? false : bill.header.customer_id || false;
            const input = this._contractPromotionInput(bill);
            const requestId = ++this._contractTotalsRequestId;
            if (bill.promo) {
                bill.promo.loading = true;
            }
            try {
                const result = await this.orm.call("ab_sales_pos_api", "pos_contract_totals", [], {
                    contract_id: contractId,
                    customer_id: customerId,
                    lines,
                    total_invoice_discount: bill.header.total_invoice_discount || 0,
                    store_id: bill.header.store_id || false,
                    applied_program_id: bill.promo?.selected_id || false,
                    manual_clear: true,
                });
                if (requestId !== this._contractTotalsRequestId || !this._contractPromotionCurrent(bill, input)) {
                    return;
                }
                bill.header.contract_allow_promotions = !!result?.allow_promotions;
                if (!result?.allow_promotions) {
                    this._resetPromotions(bill);
                } else if (bill.promo && result.available_programs) {
                    this._applyManualPromotionResult(bill, result);
                }
                bill.header.contract_allow_total_invoice_discount = !!result?.allow_total_invoice_discount;
                bill.header.contract_total_invoice_discount_source =
                    result?.total_invoice_discount_source || "our_company";
                if (!bill.header.contract_allow_total_invoice_discount) {
                    bill.header.total_invoice_discount = 0;
                }
                bill.total_net_amount = parseFloat(result?.cust_pay || 0) || 0;
                bill.contract_totals = {
                    allow_total_invoice_discount: !!result?.allow_total_invoice_discount,
                    total_invoice_discount_source: result?.total_invoice_discount_source || "our_company",
                    total_invoice_discount: parseFloat(bill.header.total_invoice_discount || 0) || 0,
                    discount: parseFloat(result?.discount || 0) || 0,
                    total_after_discount: parseFloat(result?.total_after_discount || 0) || 0,
                    cust_pay: parseFloat(result?.cust_pay || 0) || 0,
                    company_pay: parseFloat(result?.company_pay || 0) || 0,
                };
                bill.updated_at = new Date().toISOString();
                this.persistCache();
            } catch (err) {
                if (requestId !== this._contractTotalsRequestId || !this._contractPromotionCurrent(bill, input)) {
                    return;
                }
                bill.total_net_amount = bill.total_price || 0;
                bill.updated_at = new Date().toISOString();
                this.persistCache();
            } finally {
                if (requestId === this._contractTotalsRequestId && bill.promo) {
                    bill.promo.loading = false;
                    this.persistCache();
                }
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
                return this._scheduleContractTotals(target);
            }
            if (this._contractManualPromotions(target) && this.billEditable(target)) {
                this._invalidateContractPricing();
            }
            return originalSchedulePromoRefresh.call(this, bill);
        },

        async refreshPromotions(bill) {
            const target = bill || this.currentBill;
            if (target?.header?.contract_id) {
                return this._refreshContractTotals(target);
            }
            await originalRefreshPromotions.call(this, bill);
        },

        _buildSubmitHeader(bill) {
            const header = originalBuildSubmitHeader.call(this, bill);
            header.contract_id = bill.header.contract_id || false;
            header.contract_name = bill.header.contract_name || "";
            header.total_invoice_discount = parseFloat(bill.header.total_invoice_discount || 0) || 0;
            header.company_pay = parseFloat(bill.contract_totals?.company_pay || bill.header.company_pay || 0) || 0;
            header.cust_pay = parseFloat(bill.contract_totals?.cust_pay || bill.header.cust_pay || 0) || 0;
            return header;
        },
    });
}
