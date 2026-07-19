/** @odoo-module **/
import {registerComponent} from "../../registry";
import {StatCard} from "./stat_card";

registerComponent("core_ui.card.statistics", {
    component: StatCard,
    name: "Statistics Card",
    category: "Statistics",
    version: "19.0.1.0.0",
    status: "stable",
    description: "KPI card with an icon, value, label, hint, and optional action.",
    keywords: "card, statistics, kpi, metric, dashboard, value",
    templateRef: "core_ui.stat_card",
    propsSchema: {
        label: {type: "string", default: "", description: "Metric label"},
        value: {type: "string", default: "0", description: "Formatted metric value"},
        icon: {type: "string", default: "fa-chart-line", description: "Font Awesome icon"},
        tone: {type: "string", default: "primary", description: "primary, success, warning, danger, info"},
        hint: {type: "string", default: "", description: "Supporting context"},
    },
    demoData: () => ({
        label: "Approved Incentives",
        value: "12,450",
        icon: "fa-check-circle",
        tone: "success",
        hint: "Current wallet period",
    }),
});

export {StatCard};
