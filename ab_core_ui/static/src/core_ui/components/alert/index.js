/** @odoo-module **/
import { registerComponent } from "../../registry";
import { Alert } from "./alert";

registerComponent("core_ui.alert.success", {
    component: Alert,
    name: "Success Alert",
    category: "Alerts",
    version: "19.0.1.0.0",
    status: "stable",
    description: "Green success alert banner for positive outcomes and confirmations.",
    keywords: "alert, success, notification, message, banner",
    templateRef: "core_ui.alert",
    propsSchema: {
        title: { type: "string", default: "", description: "Alert title" },
        message: { type: "string", default: "", description: "Alert message body" },
        variant: { type: "string", default: "success", description: "success, warning, danger, info" },
    },
    demoData: () => ({
        title: "Inventory Updated",
        message: "Stock levels for Paracetamol 500mg have been updated successfully across all branches.",
        variant: "success",
    }),
});

registerComponent("core_ui.alert.warning", {
    component: Alert,
    name: "Warning Alert",
    category: "Alerts",
    version: "19.0.1.0.0",
    status: "stable",
    description: "Orange warning alert banner for cautionary messages and low-stock warnings.",
    keywords: "alert, warning, notification, caution, banner",
    templateRef: "core_ui.alert",
    propsSchema: null,
    demoData: () => ({
        title: "Low Stock Alert",
        message: "Amoxicillin 250mg is below minimum threshold. Please reorder from supplier.",
        variant: "warning",
    }),
});

registerComponent("core_ui.alert.danger", {
    component: Alert,
    name: "Danger Alert",
    category: "Alerts",
    version: "19.0.1.0.0",
    status: "stable",
    description: "Red danger alert banner for errors and critical system issues.",
    keywords: "alert, danger, error, critical, banner",
    templateRef: "core_ui.alert",
    propsSchema: null,
    demoData: () => ({
        title: "Transfer Failed",
        message: "The stock transfer could not be completed. Insufficient quantity in source warehouse.",
        variant: "danger",
    }),
});

registerComponent("core_ui.alert.info", {
    component: Alert,
    name: "Info Alert",
    category: "Alerts",
    version: "19.0.1.0.0",
    status: "stable",
    description: "Blue info alert banner for informational messages and system notifications.",
    keywords: "alert, info, notification, information, banner",
    templateRef: "core_ui.alert",
    propsSchema: null,
    demoData: () => ({
        title: "New Shipment Received",
        message: "Shipment #PO-2024-0042 has arrived at Warehouse A. 24 items pending inspection.",
        variant: "info",
    }),
});
