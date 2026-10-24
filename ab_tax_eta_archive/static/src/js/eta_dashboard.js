/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

class EtaDashboard extends Component {
    static template = "ab_tax_eta_archive.Dashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            dateFrom: "",
            dateTo: "",
            configId: "",
            data: null,
            loading: false,
            error: "",
        });
        onWillStart(() => this.load());
    }

    get labels() {
        return {
            eyebrow: _t("ETA archive overview"),
            title: _t("Tax archive dashboard"),
            subtitle: _t("Issue-date reports and submission-day retrieval health"),
            refresh: _t("Refresh"),
            apply: _t("Apply filters"),
            from: _t("Issue date from"),
            to: _t("Issue date to"),
            connection: _t("Connection"),
            allConnections: _t("All connections"),
            filters: _t("Dashboard filters"),
            archiveLists: _t("Archive lists"),
            loading: _t("Loading archive data…"),
            retry: _t("Try again"),
            documents: _t("Archived documents"),
            trend: _t("Documents by issue date"),
            trendNote: _t("Last 14 days of the selected period"),
            invoices: _t("Invoices"),
            receipts: _t("Receipts"),
            retrievals: _t("Submission-day retrievals"),
            lastSuccess: _t("Last successful retrieval"),
            noneYet: _t("None yet"),
            done: _t("Done"),
            pending: _t("Pending"),
            notStarted: _t("Not started"),
            errors: _t("Errors"),
            files: _t("Daily Excel files"),
            generated: _t("Generated"),
            sent: _t("Sent to Telegram"),
            corrections: _t("Corrections"),
            posDevices: _t("Receipts by POS"),
            posNote: _t("Distinct receipt UUIDs for each POS serial"),
            unknownPos: _t("Unidentified POS"),
            noPos: _t("No POS receipts in this period."),
            recentErrors: _t("Recent retrieval errors"),
            noErrors: _t("No retrieval errors in this period."),
            attention: _t("Retrievals need attention"),
            attentionBody: _t("Some ETA streams failed. Reports may be incomplete until those retrievals succeed."),
            viewAll: _t("View all"),
            viewInvoices: _t("View invoices"),
            viewReceipts: _t("View receipts"),
            viewFiles: _t("View daily files"),
            empty: _t("No archived documents in this period."),
            records: _t("records"),
        };
    }

    get cards() {
        const categories = this.state.data?.categories || {};
        return [
            { key: "sent_invoice", label: _t("Sent invoices"), tone: "blue" },
            { key: "received_invoice", label: _t("Purchase invoices"), tone: "violet" },
            { key: "sent_receipt", label: _t("Sent receipts"), tone: "teal" },
            { key: "received_receipt", label: _t("Purchase receipts"), tone: "amber" },
        ].map((card) => ({ ...card, ...(categories[card.key] || { count: 0 }) }));
    }

    get bars() {
        const days = this.state.data?.daily || [];
        const maximum = Math.max(1, ...days.map((day) => Math.max(day.invoices, day.receipts)));
        return days.map((day) => ({
            ...day,
            label: day.date.slice(5),
            invoiceHeight: day.invoices ? Math.max(5, Math.round(day.invoices / maximum * 100)) : 0,
            receiptHeight: day.receipts ? Math.max(5, Math.round(day.receipts / maximum * 100)) : 0,
        }));
    }

    get documentCount() {
        return this.cards.reduce((sum, card) => sum + card.count, 0);
    }

    get posDevices() {
        const devices = this.state.data?.pos_devices || [];
        const maximum = Math.max(1, ...devices.map((device) => device.count));
        return devices.map((device) => ({
            ...device,
            label: device.serial || this.labels.unknownPos,
            width: Math.max(3, Math.round(device.count / maximum * 100)),
        }));
    }

    formatCount(value) {
        return new Intl.NumberFormat().format(value || 0);
    }

    formatServerDateTime(value) {
        return value ? new Date(value.replace(" ", "T") + "Z").toLocaleString() : this.labels.noneYet;
    }

    streamLabel(error) {
        const kind = error.kind === "invoice" ? _t("Invoice") : _t("Receipt");
        const direction = error.direction === "sent" ? _t("Sent") : _t("Received");
        return `${kind} · ${direction}`;
    }

    async load() {
        this.state.loading = true;
        this.state.error = "";
        try {
            const data = await this.orm.call("ab_tax_eta_archive_sync", "get_dashboard_data", [
                this.state.dateFrom || false,
                this.state.dateTo || false,
                this.state.configId || false,
            ]);
            this.state.data = data;
            if (!this.state.dateFrom) {
                this.state.dateFrom = data.period.from;
            }
            if (!this.state.dateTo) {
                this.state.dateTo = data.period.to;
            }
        } catch (error) {
            this.state.error = error.message || _t("The dashboard could not load.");
        } finally {
            this.state.loading = false;
        }
    }

    onDateFromChange(event) {
        this.state.dateFrom = event.target.value;
    }

    onDateToChange(event) {
        this.state.dateTo = event.target.value;
    }

    onConfigChange(event) {
        this.state.configId = event.target.value;
    }

    openList(model, name) {
        const domain = [
            ["report_date", ">=", this.state.dateFrom],
            ["report_date", "<=", this.state.dateTo],
        ];
        if (this.state.configId) {
            domain.push(["config_id", "=", Number(this.state.configId)]);
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            name,
            res_model: model,
            views: model === "ab_tax_eta_archive_invoice" || model === "ab_tax_eta_archive_receipt"
                ? [[false, "list"]] : [[false, "list"], [false, "form"]],
            domain,
            target: "current",
        });
    }

    openInvoices() {
        this.openList("ab_tax_eta_archive_invoice", _t("ETA Invoices"));
    }

    openReceipts() {
        this.openList("ab_tax_eta_archive_receipt", _t("ETA Receipts"));
    }

    openFiles() {
        this.openList("ab_tax_eta_archive_export", _t("ETA Daily Files"));
    }

    openRetrievals() {
        this.openList("ab_tax_eta_archive_sync", _t("ETA Retrievals"));
    }

    openError(error) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "ab_tax_eta_archive_sync",
            res_id: error.id,
            views: [[false, "form"]],
            target: "current",
        });
    }
}

registry.category("actions").add("ab_tax_eta_archive.dashboard", EtaDashboard);
