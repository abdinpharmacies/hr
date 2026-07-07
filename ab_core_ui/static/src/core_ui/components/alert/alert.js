/** @odoo-module **/
import { Component } from "@odoo/owl";

export class Alert extends Component {
    static template = "core_ui.alert";
    static props = {
        title: { type: String, optional: true },
        message: { type: String, optional: true },
        variant: { type: String, optional: true },
    };
    static defaultProps = {
        title: "",
        message: "",
        variant: "info",
    };

    static ICONS = {
        success: "fa-check-circle",
        warning: "fa-exclamation-triangle",
        danger: "fa-times-circle",
        info: "fa-info-circle",
    };

    get iconClass() {
        return Alert.ICONS[this.props.variant] || "fa-info-circle";
    }
}
