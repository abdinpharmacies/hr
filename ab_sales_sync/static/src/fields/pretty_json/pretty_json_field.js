/** @odoo-module **/

import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { Component } from "@odoo/owl";

export class AbPrettyJsonField extends Component {
    static template = "ab_sales_sync.PrettyJsonField";
    static props = { ...standardFieldProps };

    get formattedValue() {
        const rawValue = this.props.record.data[this.props.name];
        if (rawValue === undefined) {
            return "";
        }

        let value = rawValue;
        if (typeof value === "string") {
            try {
                value = JSON.parse(value);
            } catch {
                // Keep non-JSON strings visible instead of hiding source data.
            }
        }

        try {
            return JSON.stringify(value, null, 2) ?? String(value);
        } catch {
            return String(value);
        }
    }
}

registry.category("fields").add("ab_pretty_json", {
    component: AbPrettyJsonField,
    additionalClasses: ["o_ab_pretty_json_field"],
    supportedTypes: ["json"],
});
