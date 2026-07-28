/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { Component, useState } from "@odoo/owl";

class InvoiceExclusionTextField extends Component {
    static template = "ab_sales.InvoiceExclusionTextField";
    static props = { ...standardFieldProps };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            currentText: this.props.record.data[this.props.name] || "",
            pasteText: "",
            loading: false,
        });
    }

    get currentCount() {
        return this._parseSerials(this.state.currentText).length;
    }

    async addInvoices() {
        await this._updateExclusions("btn_add_invoices");
    }

    async removeInvoices() {
        await this._updateExclusions("btn_remove_invoices");
    }

    async _updateExclusions(method) {
        if (!this.state.pasteText.trim()) {
            this.notification.add("Paste at least one invoice number first.", { type: "warning" });
            return;
        }
        this.state.loading = true;
        try {
            const result = await this.orm.call(
                this.props.record.resModel,
                method,
                [[this.props.record.resId]],
                { text: this.state.pasteText }
            );
            this.state.currentText = result.value || "";
            this.state.pasteText = "";
            this._notifyResult(method, result);
        } catch (error) {
            this.notification.add(this._errorMessage(error), { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    _notifyResult(method, result) {
        if (method === "btn_add_invoices") {
            this.notification.add(
                `Added ${result.added || 0} invoice(s). ${result.existing || 0} were already listed.`,
                { type: "success" }
            );
            return;
        }
        this.notification.add(
            `Removed ${result.removed || 0} invoice(s). ${result.not_listed || 0} were not listed.`,
            { type: "success" }
        );
    }

    _parseSerials(text) {
        const seen = new Set();
        const serials = [];
        for (const token of (text || "").trim().split(/\s+/)) {
            const serial = Number.parseInt(token, 10);
            if (Number.isInteger(serial) && serial && !seen.has(serial)) {
                seen.add(serial);
                serials.push(serial);
            }
        }
        return serials;
    }

    _errorMessage(error) {
        return (
            error?.data?.message ||
            error?.message ||
            "Failed to update excluded invoices."
        );
    }
}

registry.category("fields").add("ab_invoice_exclusion_text", {
    component: InvoiceExclusionTextField,
    supportedTypes: ["text"],
});
