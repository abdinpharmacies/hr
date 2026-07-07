/** @odoo-module **/
import { Component } from "@odoo/owl";

export class Button extends Component {
    static template = "core_ui.button";
    static props = {
        label: { type: String, optional: true },
        icon: { type: String, optional: true },
        variant: { type: String, optional: true },
        size: { type: String, optional: true },
        tooltip: { type: String, optional: true },
        disabled: { type: Boolean, optional: true },
    };
    static defaultProps = {
        label: "Button",
        icon: "",
        variant: "primary",
        size: "",
        tooltip: "",
        disabled: false,
    };
}
