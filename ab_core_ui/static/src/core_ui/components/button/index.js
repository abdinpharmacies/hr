/** @odoo-module **/
import { registerComponent } from "../../registry";
import { Button } from "./button";

registerComponent("core_ui.button.primary", {
    component: Button,
    name: "Primary Button",
    category: "Buttons",
    version: "19.0.1.0.0",
    status: "stable",
    description: "Primary action button with filled background style for main call-to-action.",
    keywords: "button, primary, action, submit, cta",
    templateRef: "core_ui.button",
    propsSchema: {
        label: { type: "string", default: "Save Changes", description: "Button label" },
        icon: { type: "string", default: "", description: "Font Awesome icon class" },
        variant: { type: "string", default: "primary", description: "primary, secondary, ghost, danger, icon" },
        size: { type: "string", default: "", description: "sm, lg, or empty for default" },
        tooltip: { type: "string", default: "", description: "Tooltip text" },
        disabled: { type: "boolean", default: false },
    },
    demoData: () => ({
        label: "Save Changes",
        icon: "fa-save",
        variant: "primary",
    }),
});

registerComponent("core_ui.button.secondary", {
    component: Button,
    name: "Secondary Button",
    category: "Buttons",
    version: "19.0.1.0.0",
    status: "stable",
    description: "Secondary outlined button for less prominent actions.",
    keywords: "button, secondary, cancel, outline",
    templateRef: "core_ui.button",
    propsSchema: null,
    demoData: () => ({ label: "Cancel", variant: "secondary" }),
});

registerComponent("core_ui.button.ghost", {
    component: Button,
    name: "Ghost Button",
    category: "Buttons",
    version: "19.0.1.0.0",
    status: "stable",
    description: "Minimal ghost button with no border or background until hover.",
    keywords: "button, ghost, subtle, minimal",
    templateRef: "core_ui.button",
    propsSchema: null,
    demoData: () => ({ label: "More Details", variant: "ghost" }),
});

registerComponent("core_ui.button.danger", {
    component: Button,
    name: "Danger Button",
    category: "Buttons",
    version: "19.0.1.0.0",
    status: "stable",
    description: "Red danger button for destructive actions.",
    keywords: "button, danger, delete, destructive, remove",
    templateRef: "core_ui.button",
    propsSchema: null,
    demoData: () => ({ label: "Delete Record", icon: "fa-trash", variant: "danger" }),
});

registerComponent("core_ui.button.icon", {
    component: Button,
    name: "Icon Button",
    category: "Buttons",
    version: "19.0.1.0.0",
    status: "stable",
    description: "Circular icon-only button for compact toolbars and icon actions.",
    keywords: "button, icon, tooltip, compact",
    templateRef: "core_ui.button",
    propsSchema: null,
    demoData: () => ({ icon: "fa-cog", tooltip: "Settings", variant: "icon" }),
});
