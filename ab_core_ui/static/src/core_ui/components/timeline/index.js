/** @odoo-module **/
import { registerComponent } from "../../registry";
import { Timeline } from "./timeline";

registerComponent("core_ui.timeline", {
    component: Timeline,
    name: "Timeline",
    category: "Data Display",
    version: "19.0.1.0.0",
    status: "stable",
    description: "Workflow timeline with stage progress, event markers, detail cards, and overdue badges.",
    keywords: "timeline, workflow, stage, progress, history, event",
    templateRef: "core_ui.timeline",
    propsSchema: {
        stages: {
            type: "array",
            description: "Array of timeline stages",
            required: false,
        },
        detail: {
            type: "object",
            description: "Detail card config with title, status, badge, and fields",
            required: false,
        },
    },
    demoData: () => ({
        stages: [
            { label: "Claim Registered", status: "completed", meta: "2024-01-15 09:30", notes: "Initial claim filed by supplier" },
            { label: "Document Review", status: "completed", meta: "2024-01-17 14:15" },
            { label: "Quality Inspection", status: "current", meta: "Due: 2024-01-22", notes: "Pending sample collection" },
            { label: "Supplier Response", status: "pending", meta: "Expected: 2024-01-29" },
            { label: "Final Decision", status: "pending", meta: "Expected: 2024-02-05" },
        ],
        detail: {
            title: "Current Stage: Quality Inspection",
            status: "",
            badge: "",
            fields: [
                { label: "Assigned To", value: "Ahmed Hassan" },
                { label: "Priority", value: "High" },
                { label: "Target Date", value: "2024-01-22" },
                { label: "Status", value: "In Progress" },
            ],
        },
    }),
});
