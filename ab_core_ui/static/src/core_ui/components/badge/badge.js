/** @odoo-module **/
import { Component } from "@odoo/owl";

class Badge extends Component {
    static template = "core_ui.badge";
    static props = {
        label: { type: String, optional: true },
        color: { type: String, optional: true },
        icon: { type: String, optional: true },
    };
    static defaultProps = {
        label: "",
        color: "neutral",
        icon: "",
    };
}

class BadgeState extends Component {
    static template = "core_ui.badge_state";
    static props = {
        label: { type: String, optional: true },
        state: { type: String, optional: true },
    };
    static defaultProps = {
        label: "",
        state: "draft",
    };
}

export { Badge, BadgeState };
