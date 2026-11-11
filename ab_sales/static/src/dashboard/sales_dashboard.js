/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

class AbSalesDashboardAction extends Component {
    static template = "ab_sales.SalesDashboardAction";

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
        };
    }

    async loadDashboard() {
        this.state.loading = true;
        try {
            const payload = await this.orm.call("ab_sales_header", "get_sales_dashboard_payload", [], {});
            this.state.payload = {
                ...this.emptyPayload(),
                ...(payload || {}),
            };
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || _t("Sales dashboard failed to load."), {
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
        return `o_ab_sales_dashboard_action is-${item?.tone || "default"}`;
    }

    metricClass(metric) {
        return `o_ab_sales_dashboard_metric is-${metric?.tone || "default"}`;
    }

    iconClass(icon) {
        return `fa ${icon || "fa-circle"}`;
    }

    formatNumber(value) {
        const parsed = Number.parseInt(value || 0, 10);
        return new Intl.NumberFormat().format(Number.isFinite(parsed) ? parsed : 0);
    }
}

registry.category("actions").add("ab_sales.dashboard", AbSalesDashboardAction);
