/** @odoo-module **/

import {registry} from "@web/core/registry";
import {patch} from "@web/core/utils/patch";
import {_t} from "@web/core/l10n/translation";

const PosAction = registry.category("actions").get("ab_sales.pos");
const SubmitDialog = PosAction?.components?.AbSalesPosSubmitDialog;

const normalizeChannelId = (value) => {
    const id = parseInt(value || 0, 10);
    return Number.isFinite(id) && id > 0 ? id : false;
};

if (SubmitDialog) {
    const originalSetup = SubmitDialog.prototype.setup;
    const originalValidate = SubmitDialog.prototype._validate;
    const originalPayload = SubmitDialog.prototype._payload;

    patch(SubmitDialog.prototype, {
        setup() {
            originalSetup.call(this, ...arguments);
            const header = this.props.bill?.header || {};
            const channelId = normalizeChannelId(header.sales_channel_id);
            this.state.sales_channel = channelId
                ? {
                    id: channelId,
                    display_name: header.sales_channel_name || "",
                }
                : false;
            this.onSalesChannelUpdate = this.onSalesChannelUpdate.bind(this);
            this.salesChannelDomain = this.salesChannelDomain.bind(this);
            this.salesChannelLabel = this.salesChannelLabel.bind(this);
            this.salesChannelPlaceholder = this.salesChannelPlaceholder.bind(this);
        },

        salesChannelDomain() {
            return [["active", "=", true]];
        },

        salesChannelLabel() {
            return _t("Sales Channel");
        },

        salesChannelPlaceholder() {
            return _t("Select sales channel...");
        },

        onSalesChannelUpdate(value) {
            if (value?.id) {
                this.state.sales_channel = value;
            } else {
                this.state.sales_channel = false;
            }
            if (this.state.errors?.sales_channel) {
                this.state.errors = {...this.state.errors, sales_channel: false};
            }
            this.state.message = "";
        },

        _validate() {
            const isValid = originalValidate.call(this);
            const errors = {...(this.state.errors || {})};
            if (!this.state.sales_channel?.id) {
                errors.sales_channel = true;
            }
            this.state.errors = errors;
            this.state.message = Object.values(errors).some(Boolean)
                ? _t("Please fill the required fields.")
                : "";
            return isValid && !errors.sales_channel;
        },

        _payload() {
            const payload = originalPayload.call(this);
            payload.sales_channel_id = this.state.sales_channel?.id || false;
            payload.sales_channel_name = this.state.sales_channel?.display_name || "";
            return payload;
        },
    });
}

if (PosAction) {
    const originalNormalizeBill = PosAction.prototype._normalizeBill;
    const originalCreateNewBill = PosAction.prototype.createNewBill;
    const originalApplySubmitDialog = PosAction.prototype._applySubmitDialog;
    const originalBuildSubmitHeader = PosAction.prototype._buildSubmitHeader;

    patch(PosAction.prototype, {
        _normalizeBill(bill) {
            const normalized = originalNormalizeBill.call(this, bill);
            normalized.header.sales_channel_id = normalizeChannelId(normalized.header.sales_channel_id);
            normalized.header.sales_channel_name = normalized.header.sales_channel_name || "";
            return normalized;
        },

        createNewBill(storeId) {
            const result = originalCreateNewBill.call(this, storeId);
            const bill = this.currentBill;
            if (bill?.header) {
                bill.header.sales_channel_id = normalizeChannelId(bill.header.sales_channel_id);
                bill.header.sales_channel_name = bill.header.sales_channel_name || "";
                bill.updated_at = new Date().toISOString();
                this.persistCache();
            }
            return result;
        },

        _applySubmitDialog(bill, payload) {
            originalApplySubmitDialog.call(this, bill, payload);
            if (!bill?.header) {
                return;
            }
            bill.header.sales_channel_id = normalizeChannelId(payload?.sales_channel_id);
            bill.header.sales_channel_name = (payload?.sales_channel_name || "").trim();
            bill.updated_at = new Date().toISOString();
            this.persistCache();
        },

        _buildSubmitHeader(bill) {
            const header = originalBuildSubmitHeader.call(this, bill);
            header.sales_channel_id = normalizeChannelId(bill?.header?.sales_channel_id);
            return header;
        },
    });
}
