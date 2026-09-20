/** @odoo-module **/
import { registerComponent } from "../../registry";
import { SyncProgressPanel } from "./sync_progress_panel";

registerComponent("core_ui.progress.sync_panel", {
    component: SyncProgressPanel,
    name: "Sync Progress Panel",
    category: "Progress",
    version: "19.0.1.0.0",
    status: "stable",
    description: "Dashboard-style synchronization progress panel with completion badge and status message.",
    keywords: "progress, sync, dashboard, batch, status, eplus",
    templateRef: "core_ui.progress.sync_panel",
    propsSchema: {
        label: { type: "string", default: "", description: "Progress label" },
        value: { type: "number", default: 0, description: "Progress percentage from 0 to 100" },
        title: { type: "string", default: "", description: "Status title" },
        detail: { type: "string", default: "", description: "Status description" },
        icon: { type: "string", default: "fa-check", description: "Font Awesome icon class without the fa prefix" },
        completeLabel: { type: "string", default: "100%", description: "Badge label when complete" },
    },
    demoData: () => ({
        label: "Synced products: 18,761 / 18,761",
        value: 100,
        title: "Inventory Fully Synchronized",
        detail: "All required products are synchronized with Odoo Inventory.",
        icon: "fa-check",
        completeLabel: "100%",
    }),
});

export { SyncProgressPanel };
