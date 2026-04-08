/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

class AbRequestStateFieldBase extends Component {
    static props = { ...standardFieldProps };
    static supportedTypes = ["selection"];

    get value() {
        return this.props.record.data[this.props.name];
    }

    get label() {
        const selection = this.props.record.fields[this.props.name]?.selection || [];
        return selection.find(([value]) => value === this.value)?.[1] || this.value || "";
    }

    get stateClass() {
        return this.value || "unknown";
    }

    get isOverdue() {
        return Boolean(this.props.record.data.is_overdue);
    }
}

export class AbRequestStateDotField extends AbRequestStateFieldBase {
    static template = "ab_request_management.AbRequestStateDotField";
}

export class AbRequestStateLabelField extends AbRequestStateFieldBase {
    static template = "ab_request_management.AbRequestStateLabelField";
}

export class AbRequestSubjectStateField extends AbRequestStateFieldBase {
    static template = "ab_request_management.AbRequestSubjectStateField";
    static supportedTypes = ["char"];

    get subject() {
        return this.props.record.data[this.props.name] || "";
    }
}

registry.category("fields").add("ab_request_state_dot", {
    component: AbRequestStateDotField,
});

registry.category("fields").add("ab_request_state_label", {
    component: AbRequestStateLabelField,
});

registry.category("fields").add("ab_request_subject_state", {
    component: AbRequestSubjectStateField,
});
