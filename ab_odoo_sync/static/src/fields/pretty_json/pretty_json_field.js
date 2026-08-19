/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { Component } from "@odoo/owl";

export class AbPrettyJsonField extends Component {
    static template = "ab_odoo_sync.PrettyJsonField";
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

    onInput(event) {
        event.target.setCustomValidity("");
    }

    onChange(event) {
        const input = event.target;
        const text = input.value.trim();
        let value = false;
        try {
            if (text) {
                value = JSON.parse(text);
            }
        } catch {
            input.setCustomValidity(_t("Enter valid JSON before saving."));
            input.reportValidity();
            return;
        }
        input.setCustomValidity("");
        return this.props.record.update({ [this.props.name]: value });
    }
}

registry.category("fields").add("ab_pretty_json", {
    component: AbPrettyJsonField,
    additionalClasses: ["o_ab_pretty_json_field"],
    supportedTypes: ["json"],
});
