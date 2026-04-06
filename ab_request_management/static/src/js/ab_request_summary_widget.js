/** @odoo-module **/

import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { Component } from "@odoo/owl";

const STATE_LABELS = {
    under_review: "Under Review",
    scheduled: "Scheduled",
    in_progress: "In Progress",
    under_requester_confirmation: "Under Requester Confirmation",
    satisfied: "Satisfied",
    rejected: "Rejected",
    closed: "Closed",
};

const PRIORITY_LABELS = {
    low: "Low",
    medium: "Medium",
    high: "High",
};

export class AbRequestSummaryWidget extends Component {
    static template = "ab_request_management_ab_request_summary_widget";
    static props = { ...standardFieldProps };
    static supportedTypes = ["char"];

    get request() {
        return this.props.record.data;
    }

    get stateLabel() {
        return STATE_LABELS[this.request.state] || this.request.state || "Unknown";
    }

    get priorityLabel() {
        return PRIORITY_LABELS[this.request.priority] || this.request.priority || "Not Set";
    }

    get stateClass() {
        return this.request.state || "unknown";
    }

    get priorityClass() {
        return this.request.priority || "unset";
    }
}

export const abRequestSummaryWidget = {
    component: AbRequestSummaryWidget,
};

registry.category("fields").add("ab_request_summary", abRequestSummaryWidget);
