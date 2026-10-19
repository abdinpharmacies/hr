/** @odoo-module **/

import "@ab_sales_cashier/cashier/cashier_action";
import "@ab_employee_access_sales/cashier/ab_employee_access_sales_cashier_patch";

import {registry} from "@web/core/registry";
import {_t} from "@web/core/l10n/translation";

const Cashier = registry.category("actions").get("ab_sales.cashier");

class ShiftCashier extends Cashier {
    static template = "ab_sales_cash_shift.Cashier";

    async openDrawerOperation(invoice = false) {
        try {
            const action = await this.orm.call("ab_sales_cashier_api", "open_cash_shift_operation", [], {
                session_token: this.state.sessionToken || false,
                store_id: this.state.selectedStoreId || false,
                invoice_id: invoice?.id || false,
                document_type: invoice?.documentType || "sale",
            });
            await this.action.doAction(action, {onClose: async () => {
                this.clearSelection();
                await this.refreshPending({manual: true});
            }});
        } catch (error) {
            this.notification.add(this._rpcError(error, _t("Unable to open the cash operation.")), {type: "danger"});
        }
    }

    async saveSelectedInvoice() {
        if (this.state.isSaving || !this.state.selectedInvoiceSnapshot?.id) {
            return;
        }
        this.state.isSaving = true;
        try {
            await this.openDrawerOperation(this.state.selectedInvoiceSnapshot);
        } finally {
            this.state.isSaving = false;
        }
    }
}

registry.category("actions").add("ab_sales_cash_shift.cashier", ShiftCashier);
