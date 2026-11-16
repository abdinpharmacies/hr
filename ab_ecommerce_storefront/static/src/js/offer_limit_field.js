/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class OfferLimitField extends Component {
    static template = "ab_ecommerce_storefront.OfferLimitField";
    static props = { ...standardFieldProps };

    setup() {
        this.state = useState({ custom: false });
        this.presets = [1, 2, 3, 5, 10];
        this.noLimitLabel = _t("No limit");
        this.customLabel = _t("Custom number");
    }

    get value() {
        return this.props.record.data[this.props.name] || 0;
    }

    get selectedValue() {
        if (this.state.custom || (this.value && !this.presets.includes(this.value))) {
            return "custom";
        }
        return this.value ? String(this.value) : "unlimited";
    }

    get selectedPreset() {
        return this.selectedValue === "custom" ? -1 : this.value;
    }

    onSelect(event) {
        const value = event.target.value;
        this.state.custom = value === "custom";
        if (value !== "custom") {
            this.props.record.update({ [this.props.name]: value === "unlimited" ? 0 : Number(value) });
        }
    }

    onCustomChange(event) {
        const value = Number(event.target.value);
        if (Number.isSafeInteger(value) && value > 0) {
            this.props.record.update({ [this.props.name]: value });
        } else {
            event.target.value = this.value > 0 ? String(this.value) : "";
        }
    }
}

registry.category("fields").add("ab_offer_limit", {
    component: OfferLimitField,
    supportedTypes: ["integer"],
});
