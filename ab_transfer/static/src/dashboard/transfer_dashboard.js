/** @odoo-module **/

import {registry} from "@web/core/registry";
import {Component, onWillStart, useState} from "@odoo/owl";
import {useService} from "@web/core/utils/hooks";
import {_t} from "@web/core/l10n/translation";

class AbTransferDashboardAction extends Component {
    static template = "ab_transfer.TransferDashboardAction";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({
            loading: true,
            payload: this.emptyPayload(),
        });

        onWillStart(async () => {
            await this.loadDashboard();
        });
    }

    emptyPayload() {
        return {
            quick_actions: [],
            metrics: [],
            request_execution: [],
            draft_transfers: 0,
        };
    }

    get requestExecutionTotal() {
        return (this.state.payload.request_execution || []).reduce(
            (total, item) => total + (Number.parseInt(item.value || 0, 10) || 0),
            0
        );
    }

    async loadDashboard() {
        this.state.loading = true;
        try {
            const payload = await this.orm.call("ab_transfer_header", "get_transfer_dashboard_payload", [], {});
            this.state.payload = {
                ...this.emptyPayload(),
                ...(payload || {}),
            };
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || _t("Transfer dashboard failed to load."), {
                type: "danger",
            });
        } finally {
            this.state.loading = false;
        }
    }

    async openAction(action) {
        if (!action) {
            return;
        }
        await this.action.doAction(action);
    }

    actionTileClass(item) {
        return `o_ab_transfer_dashboard_action is-${item?.tone || "default"}`;
    }

    metricClass(metric) {
        return `o_ab_transfer_dashboard_metric is-${metric?.tone || "default"}`;
    }

    executionClass(item) {
        return `o_ab_transfer_dashboard_execution_item is-${item?.tone || "default"}`;
    }

    iconClass(icon) {
        return `fa ${icon || "fa-circle"}`;
    }

    formatNumber(value) {
        const parsed = Number.parseInt(value || 0, 10);
        return new Intl.NumberFormat().format(Number.isFinite(parsed) ? parsed : 0);
    }

    executionShare(item) {
        const total = this.requestExecutionTotal;
        if (!total) {
            return "0%";
        }
        const value = Number.parseInt(item?.value || 0, 10) || 0;
        return `${Math.round((value / total) * 100)}%`;
    }
}

registry.category("actions").add("ab_transfer.dashboard", AbTransferDashboardAction);
