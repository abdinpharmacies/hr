/** @odoo-module **/
import { Component } from "@odoo/owl";

export class SyncProgressPanel extends Component {
    static template = "core_ui.progress.sync_panel";
    static props = {
        label: { type: String, optional: true },
        value: { type: Number, optional: true },
        title: { type: String, optional: true },
        detail: { type: String, optional: true },
        icon: { type: String, optional: true },
        completeLabel: { type: String, optional: true },
    };
    static defaultProps = {
        label: "",
        value: 0,
        title: "",
        detail: "",
        icon: "fa-check",
        completeLabel: "100%",
    };

    get safeValue() {
        return Math.max(0, Math.min(100, Number(this.props.value || 0)));
    }

    get progressStyle() {
        return `width: ${this.safeValue.toFixed(2)}%;`;
    }

    get percentLabel() {
        return `${Math.round(this.safeValue)}%`;
    }

    get iconClass() {
        return `core_ui_sync_status_icon fa ${this.props.icon || "fa-check"}`;
    }
}
