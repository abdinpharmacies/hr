/** @odoo-module **/

import { registry } from "@web/core/registry";
import { patch } from "@web/core/utils/patch";

const PosAction = registry.category("actions").get("ab_sales.pos");

if (PosAction) {
    const baseSetup = PosAction.prototype.setup;
    const baseNormalizeBill = PosAction.prototype._normalizeBill;
    const baseCreateNewBill = PosAction.prototype.createNewBill;
    const baseOnContractM2OUpdate = PosAction.prototype.onContractM2OUpdate;
    const baseRefreshContractTotals = PosAction.prototype._refreshContractTotals;
    const baseRecomputeBill = PosAction.prototype._recomputeBill;
    const baseBuildSubmitHeader = PosAction.prototype._buildSubmitHeader;

    patch(PosAction.prototype, {
        setup() {
            baseSetup.call(this, ...arguments);
            this.onTotalInvoiceDiscountInput = this.onTotalInvoiceDiscountInput.bind(this);
        },

        _normalizeBill(bill) {
            const normalized = baseNormalizeBill.call(this, bill);
            normalized.header.total_invoice_discount = parseFloat(normalized.header.total_invoice_discount || 0) || 0;
            normalized.header.contract_allow_total_invoice_discount = !!normalized.header.contract_allow_total_invoice_discount;
            return normalized;
        },

        createNewBill(storeId) {
            const result = baseCreateNewBill.call(this, storeId);
            const bill = this.currentBill;
            if (bill?.header) {
                if (!("total_invoice_discount" in bill.header)) {
                    bill.header.total_invoice_discount = 0;
                }
                if (!("contract_allow_total_invoice_discount" in bill.header)) {
                    bill.header.contract_allow_total_invoice_discount = false;
                }
                bill.updated_at = new Date().toISOString();
                this.persistCache();
            }
            return result;
        },

        onContractM2OUpdate(value) {
            const bill = this.currentBill;
            if (bill && (!value || !value.id)) {
                bill.header.total_invoice_discount = 0;
                bill.header.contract_allow_total_invoice_discount = false;
            }
            return baseOnContractM2OUpdate.call(this, value);
        },

        onTotalInvoiceDiscountInput(ev) {
            const bill = this.currentBill;
            if (!bill) {
                return;
            }
            const parsed = parseFloat(ev?.target?.value || 0);
            bill.header.total_invoice_discount = Number.isFinite(parsed) && parsed > 0 ? parsed : 0;
            bill.updated_at = new Date().toISOString();
            this.persistCache();
            this._scheduleContractTotals(bill, { immediate: true });
        },

        async _refreshContractTotals(bill) {
            const contractId = bill?.header?.contract_id;
            if (!contractId) {
                return baseRefreshContractTotals.call(this, bill);
            }

            const lines = this._contractPayloadLines(bill);
            const requestId = ++this._contractTotalsRequestId;
            try {
                const result = await this.orm.call("ab_sales_pos_api", "pos_contract_totals", [], {
                    contract_id: contractId,
                    lines,
                    total_invoice_discount: bill.header?.contract_allow_total_invoice_discount
                        ? (parseFloat(bill.header?.total_invoice_discount || 0) || 0)
                        : 0,
                });
                if (requestId !== this._contractTotalsRequestId) {
                    return;
                }
                const stillExists = this.state?.bills?.some((currentBill) => currentBill.id === bill.id);
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
                bill.header.contract_allow_total_invoice_discount = !!result?.allow_total_invoice_discount;
                if (!bill.header.contract_allow_total_invoice_discount) {
                    bill.header.total_invoice_discount = 0;
                }
                bill.updated_at = new Date().toISOString();
                this.persistCache();
            } catch (err) {
                return baseRefreshContractTotals.call(this, bill);
            }
        },

        _recomputeBill(bill, options = {}) {
            const result = baseRecomputeBill.call(this, bill, options);
            if (bill?.header?.contract_id && !bill.header.contract_allow_total_invoice_discount) {
                bill.header.total_invoice_discount = 0;
            }
            return result;
        },

        _buildSubmitHeader(bill) {
            const header = baseBuildSubmitHeader.call(this, bill);
            header.total_invoice_discount = bill.header.contract_allow_total_invoice_discount
                ? (parseFloat(bill.header.total_invoice_discount || 0) || 0)
                : 0;
            return header;
        },
    });
}
