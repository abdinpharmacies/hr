/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { formatFloat } from "@web/views/fields/formatters";

class PurchaseDashboard extends Component {
    static template = "ab_purchase.PurchaseDashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({
            loading: true,
            data: { store_ids: [], pending_count: 0, saved_count: 0, posted_receipts: 0, observed: [], recent: [], notice: "" },
        });
        onWillStart(() => this.refresh());
    }

    async refresh() {
        this.state.loading = true;
        try {
            this.state.data = await this.orm.call("ab_purchase_header", "get_purchase_dashboard_payload", []);
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || _t("Purchase overview could not load."), {
                type: "danger",
            });
        } finally {
            this.state.loading = false;
        }
    }

    openInvoices(domain = []) {
        const storeDomain = this.state.data.store_ids === null
            ? [] : [["store_id", "in", this.state.data.store_ids || []]];
        return this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Purchase Invoices"),
            res_model: "ab_purchase_header",
            view_mode: "list,form",
            views: [[false, "list"], [false, "form"]],
            domain: [...storeDomain, ...domain],
        });
    }

    openInvoice(id) {
        return this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "ab_purchase_header",
            res_id: id,
            view_mode: "form",
            views: [[false, "form"]],
        });
    }

    openReturns() {
        return this.action.doAction({
            type: "ir.actions.act_window", name: _t("Returns"),
            res_model: "ab_purchase_notice_header", views: [[false, "list"], [false, "form"]],
            domain: [["store_id", "in", this.state.data.store_ids || []]],
        });
    }

    money(value) {
        return formatFloat(value || 0, { digits: [16, 3] });
    }

    statusLabel(status) {
        return {
            prepending: _t("Draft"),
            pending: _t("Pending"),
            saved: _t("Saved"),
            rejected: _t("Rejected"),
        }[status] || status;
    }
}

registry.category("actions").add("ab_purchase.dashboard", PurchaseDashboard);
