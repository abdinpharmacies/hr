/** @odoo-module **/
import { registerComponent } from "../../registry";
import { Badge, BadgeState } from "./badge";

registerComponent("core_ui.badge", {
    component: Badge,
    name: "Default Badge",
    category: "Badges",
    version: "19.0.1.0.0",
    status: "stable",
    description: "Standard badge/pill component for statuses, labels, and tags.",
    keywords: "badge, pill, status, label, tag",
    templateRef: "core_ui.badge",
    propsSchema: {
        label: { type: "string", default: "", description: "Badge text" },
        color: { type: "string", default: "neutral", description: "neutral, success, warning, danger, primary" },
        icon: { type: "string", default: "", description: "Font Awesome icon class" },
    },
    demoData: () => ({
        label: "In Stock",
        color: "success",
        icon: "fa-check-circle",
    }),
});

registerComponent("core_ui.badge.state", {
    component: BadgeState,
    name: "State Badge",
    category: "Badges",
    version: "19.0.1.0.0",
    status: "stable",
    description: "Colored state badge with gradient and glow effect for workflow states.",
    keywords: "badge, state, status, approved, draft, rejected, pending",
    templateRef: "core_ui.badge_state",
    propsSchema: {
        label: { type: "string", default: "", description: "State label" },
        state: { type: "string", default: "draft", description: "approved, draft, rejected, pending" },
    },
    demoData: () => ({
        label: "Approved",
        state: "approved",
    }),
});
