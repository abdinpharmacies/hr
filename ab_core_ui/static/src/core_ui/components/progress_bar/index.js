/** @odoo-module **/
import { registerComponent } from "../../registry";
import { ProgressBar } from "./progress_bar";

registerComponent("core_ui.progress.bar", {
    component: ProgressBar,
    name: "Progress Bar",
    category: "Progress",
    version: "19.0.1.0.0",
    status: "stable",
    description: "Horizontal progress bar with percentage label for tracking completion metrics.",
    keywords: "progress, bar, loading, percentage, metric, completion",
    templateRef: "core_ui.progress_bar",
    propsSchema: {
        value: { type: "number", default: 0, description: "Progress percentage (0-100)" },
        label: { type: "string", default: "", description: "Label text above the bar" },
        show_value: { type: "boolean", default: true, description: "Show percentage value" },
        color: { type: "string", default: "", description: "Bar color variant: primary, success, warning, danger" },
    },
    demoData: () => ({
        value: 68,
        label: "Inventory Audit Progress",
        show_value: true,
    }),
});
