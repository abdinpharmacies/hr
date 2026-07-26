/** @odoo-module **/
import { _t } from "@web/core/l10n/translation";
import { Component, xml } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";

export class SccCloseErrorDialog extends Component {
    static template = xml`
        <Dialog size="'md'">
            <div class="scc-close-error-dialog">
                <div class="scc-close-error-hero">
                    <div class="scc-close-error-icon" aria-hidden="true">
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M9 11l3 3L22 4"/>
                            <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>
                        </svg>
                    </div>
                    <div class="scc-close-error-copy">
                        <div class="scc-close-error-title" t-esc="titleText"/>
                        <div class="scc-close-error-subtitle" t-esc="subtitleText"/>
                    </div>
                </div>
                <div class="scc-close-error-list" role="list">
                    <div t-foreach="checklistItems" t-as="item" t-key="item.key" class="scc-close-error-item" role="listitem">
                        <span class="scc-close-error-marker" aria-hidden="true">○</span>
                        <span class="scc-close-error-item-icon" t-esc="item.icon" aria-hidden="true"/>
                        <span class="scc-close-error-item-text" t-esc="item.text"/>
                    </div>
                </div>
            </div>
            <t t-set-slot="footer">
                <button class="btn btn-primary scc-close-error-btn" t-on-click="onClose" t-esc="understoodText"/>
            </t>
        </Dialog>
    `;
    static components = { Dialog };
    static props = {
        errors: { type: Array },
        close: { type: Function, optional: true },
    };

    get titleText() {
        return _t("Cannot Close Claim");
    }

    get subtitleText() {
        return _t("A few actions are still required before this claim can be closed.");
    }

    get understoodText() {
        return _t("Understood");
    }

    get checklistItems() {
        return (this.props.errors || []).map((error, index) => ({
            key: `${index}-${error}`,
            icon: this.iconForError(error),
            text: this.translateError(error),
        }));
    }

    iconForError(error) {
        if (error.includes("WhatsApp")) {
            return "💬";
        }
        if (error.includes("delivery") || error.includes("Delivery")) {
            return "🚚";
        }
        if (error.includes("cheque") || error.includes("supplier ID")) {
            return "📎";
        }
        if (error.includes("notified")) {
            return "📣";
        }
        return "•";
    }

    translateError(error) {
        if (error === "Supplier must be marked as notified before closing the claim.") {
            return _t("Mark supplier as notified");
        }
        if (error === "Please send the WhatsApp message to the supplier before closing the claim.") {
            return _t("Send WhatsApp message to supplier");
        }
        if (error === "Cheque Delivery Status must be set before closing the claim.") {
            return _t("Set cheque delivery status");
        }
        if (error === "Please select a sub status (Delivered or Shipped) for cheque delivery.") {
            return _t("Choose delivery sub-status");
        }
        if (error === "Please complete the Delivery stage before closing the claim.") {
            return _t("Complete the Delivery stage");
        }
        if (error === "Please set the delivery status to Delivered before closing the claim.") {
            return _t("Mark delivery status as Delivered");
        }
        if (error === "Please set the delivery status to Ready before closing the claim.") {
            return _t("Mark delivery status as Ready");
        }
        if (error === "Please attach the cheque image before confirming cheque delivery.") {
            return _t("Attach cheque image");
        }
        if (error === "Please attach the supplier ID image before confirming cheque delivery.") {
            return _t("Attach supplier ID image");
        }
        return error;
    }

    onClose() {
        if (this.props.close) {
            this.props.close();
        }
    }
}
