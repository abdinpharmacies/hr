/** @odoo-module **/

import "@ab_sales_cashier/cashier/cashier_action";
import "@ab_employee_access_sales_cashier/cashier/cashier_patch";

import {registry} from "@web/core/registry";
import {patch} from "@web/core/utils/patch";
import {_t} from "@web/core/l10n/translation";

const Cashier = registry.category("actions").get("ab_sales.cashier");

patch(Cashier.prototype, {
    async openDrawerOperation(invoice = false) {
        try {
            const action = await this.orm.call("ab_sales_cashier_api", "open_cash_shift_operation", [], {
                session_token: this.state.sessionToken || false,
                store_id: this.state.selectedStoreId || false,
                invoice_id: invoice?.id || false,
                document_type: invoice?.documentType || "sale",
            });
            if (!action) {
                return false;
            }
            await this.action.doAction(action, {onClose: async () => {
                this.clearSelection();
                await this.refreshPending({manual: true});
            }});
            return true;
        } catch (error) {
            this.notification.add(this._rpcError(error, _t("Unable to open the cash operation.")), {type: "danger"});
            return true;
        }
    },

    async openCloseCashierDialog() {
        const handled = await this.openDrawerOperation();
        if (!handled) {
            return super.openCloseCashierDialog(...arguments);
        }
    },
});
