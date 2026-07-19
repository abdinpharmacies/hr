/** @odoo-module **/
import {Component} from "@odoo/owl";

export class StatCard extends Component {
    static template = "core_ui.stat_card";
    static props = {
        label: String,
        value: {type: [String, Number]},
        icon: {type: String, optional: true},
        tone: {type: String, optional: true},
        hint: {type: String, optional: true},
        trend: {type: String, optional: true},
        trendDirection: {type: String, optional: true},
        onClick: {type: Function, optional: true},
    };
    static defaultProps = {
        icon: "fa-chart-line",
        tone: "primary",
        hint: "",
        trend: "",
        trendDirection: "",
    };

    onActivate() {
        this.props.onClick?.();
    }
}
