/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { Component } from "@odoo/owl";

const STATE_LABELS = {
    under_review: _t("Under Review"),
    scheduled: _t("Scheduled"),
    in_progress: _t("In Progress"),
    under_requester_confirmation: _t("Under Requester Confirmation"),
    satisfied: _t("Satisfied"),
    rejected: _t("Rejected"),
    closed: _t("Closed"),
};

export class AbRequestSummaryWidget extends Component {
    static template = "ab_request_management_ab_request_summary_widget";
    static props = { ...standardFieldProps };
    static supportedTypes = ["char"];

    get request() {
        return this.props.record.data;
    }

    get stateLabel() {
        return STATE_LABELS[this.request.state] || this.request.state || _t("Unknown");
    }

    get stateClass() {
        return this.request.state || "unknown";
    }
}

export const abRequestSummaryWidget = {
    component: AbRequestSummaryWidget,
};

registry.category("fields").add("ab_request_summary", abRequestSummaryWidget);
