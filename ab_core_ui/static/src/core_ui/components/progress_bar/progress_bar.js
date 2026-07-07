/** @odoo-module **/
import { Component } from "@odoo/owl";

export class ProgressBar extends Component {
    static template = "core_ui.progress_bar";
    static props = {
        value: { type: Number, optional: true },
        label: { type: String, optional: true },
        show_value: { type: Boolean, optional: true },
        color: { type: String, optional: true },
    };
    static defaultProps = {
        value: 0,
        label: "",
        show_value: false,
        color: "",
    };
}
