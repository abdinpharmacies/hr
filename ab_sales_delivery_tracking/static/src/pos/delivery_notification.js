/** @odoo-module **/
import {Component, useState} from "@odoo/owl";
import {Dialog} from "@web/core/dialog/dialog";
import {_t} from "@web/core/l10n/translation";
import {registry} from "@web/core/registry";

// Bump with the backend requirement when the submission interface changes incompatibly.
const DELIVERY_UI_VERSION = "1";

export class DeliveryNotificationDialog extends Component {
    static template = "ab_sales_delivery_tracking.NotificationDialog";
    static components = {Dialog};
    static props = {close: Function, instructions: {type: String, optional: true}, onConfirm: Function};

    setup() {
        this.state = useState({instructions: this.props.instructions || "", error: ""});
        this.title = _t("Delivery Notification");
    }

    confirm(notify) {
        const instructions = this.state.instructions.trim();
        if (notify && !instructions) {
            this.state.error = _t("Delivery instructions are required when notifying the delivery bot.");
            return;
        }
        this.props.onConfirm({notify, instructions});
        this.props.close();
    }
}

const SalesPosAction = registry.category("actions").get("ab_sales.pos");
const SalesBeforeSubmitDialog = SalesPosAction.components.AbSalesPosSubmitDialog;

export class DeliveryBeforeSubmitDialog extends SalesBeforeSubmitDialog {
    static props = {...SalesBeforeSubmitDialog.props, requestNotification: Function};

    _onKeydown(ev) {
        if (!this.env.dialogData.isActive) {
            return;
        }
        return super._onKeydown(ev);
    }

    async submit() {
        if (this.state.submitting) {
            return;
        }
        if (!this.state.is_delivery) {
            return super.submit();
        }
        const header = this.props.bill?.header || {};
        if (!(this.state.hasCustomer || header.customer_id)) {
            this.openCustomerLookup();
            return;
        }
        if (!this._validate()) {
            return;
        }
        this.state.submitting = true;
        try {
            const choice = await this.props.requestNotification();
            if (!choice) {
                // Keep this component mounted: none of its draft values change.
                return;
            }
            await this.props.onSubmit({
                ...this._payload(),
                delivery_notify: choice.notify,
                delivery_instructions: choice.instructions,
            });
            this.props.close();
        } finally {
            this.state.submitting = false;
        }
    }
}

export class DeliveryTrackingPosAction extends SalesPosAction {
    _openSubmitDialog(bill) {
        if (!bill || this.state.submitting || this._deliveryDialogOpen) {
            return;
        }
        this.dialog.add(DeliveryBeforeSubmitDialog, {
            bill,
            preferredBillName: this.state.customerInsights?.customer?.name || "",
            preferredBillAddress: this.state.customerInsights?.customer?.last_address || "",
            defaultEmployee: this._submitDialogDefaultEmployee(bill),
            requestNotification: () => this._requestDeliveryNotification(bill),
            onSubmit: async (payload) => {
                await this._applySubmitDialog(bill, payload);
                return this._submitWithDeliveryChoice(bill, {
                    notify: payload.delivery_notify === true,
                    instructions: payload.delivery_instructions ?? bill.header.delivery_instructions ?? "",
                });
            },
            onDraft: (payload) => this._applySubmitDialog(bill, payload),
            onCustomerApply: (customer) => this.applyCustomerLookup(customer),
        });
    }

    async _requestDeliveryNotification(bill) {
        if (this._deliveryDialogOpen) {
            return null;
        }
        this._deliveryDialogOpen = true;
        try {
            return await new Promise((resolve) => {
                let choice = null;
                this.dialog.add(DeliveryNotificationDialog, {
                    instructions: bill.header.delivery_instructions || "",
                    onConfirm: (value) => { choice = value; },
                }, {onClose: () => resolve(choice)});
            });
        } finally {
            this._deliveryDialogOpen = false;
        }
    }

    _submitWithDeliveryChoice(bill, choice) {
        bill.header.delivery_notify = !!bill.header.is_delivery && choice.notify;
        bill.header.delivery_instructions = choice.instructions;
        bill.updated_at = new Date().toISOString();
        this.persistCache();
        return super._submitBillInternal(bill);
    }

    async _submitBillInternal(bill) {
        if (!bill || this.state.submitting || this._deliveryDialogOpen) {
            return;
        }
        if (!bill.header?.is_delivery) {
            return super._submitBillInternal(bill);
        }
        const choice = await this._requestDeliveryNotification(bill);
        if (choice) {
            return this._submitWithDeliveryChoice(bill, choice);
        }
    }

    _buildSubmitHeader(bill) {
        return {
            ...super._buildSubmitHeader(bill),
            delivery_ui_version: DELIVERY_UI_VERSION,
            delivery_notify: !!bill.header.is_delivery && bill.header.delivery_notify === true,
            delivery_instructions: bill.header.delivery_instructions || "",
        };
    }
}
registry.category("actions").add("ab_sales_delivery_tracking.pos", DeliveryTrackingPosAction);
