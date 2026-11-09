/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";

const CARDS = [
    { key: "new", label: _t("New Orders"), icon: "fa fa-shopping-cart", tone: "blue" },
    { key: "unpaid", label: _t("Unpaid Orders"), icon: "fa fa-credit-card", tone: "violet" },
    { key: "processing", label: _t("In Processing"), icon: "fa fa-cogs", tone: "amber" },
    { key: "assigned", label: _t("Assigned Orders"), icon: "fa fa-user-circle-o", tone: "blue" },
    { key: "deliveries", label: _t("Delivered Today"), icon: "fa fa-check-circle-o", tone: "green" },
    { key: "cancelled", label: _t("Cancelled Orders"), icon: "fa fa-times-circle-o", tone: "rose" },
];

export class OrderOverview extends Component {
    static template = "ab_ecommerce_storefront.OrderOverview";
    static props = { ...standardActionServiceProps };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.cards = CARDS;
        this.direction = user.lang?.startsWith("ar") ? "rtl" : "ltr";
        this.state = useState({ loading: true, counts: {}, recent: [], error: false });
        onWillStart(() => this.loadOverview());
    }

    async loadOverview() {
        this.state.loading = true;
        this.state.error = false;
        try {
            const result = await this.orm.call("sale.order", "get_ab_order_overview", []);
            this.state.counts = result.counts;
            this.state.recent = result.recent;
        } catch {
            this.state.error = true;
            this.notification.add(_t("Could not load the order overview."), { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    async openBucket(bucket) {
        const action = await this.orm.call("sale.order", "action_ab_order_overview_bucket", [bucket]);
        await this.action.doAction(action);
    }

    async openOrder(orderId) {
        const action = await this.orm.call("sale.order", "action_ab_order_overview_open", [orderId]);
        await this.action.doAction(action);
    }

    openOrderLabel(name) {
        return _t("Open order %s", name);
    }

    onOrderKeydown(event, orderId) {
        if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            this.openOrder(orderId);
        }
    }
}

registry.category("actions").add("ab_ecommerce_storefront.order_overview", OrderOverview);
