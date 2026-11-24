/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

class OfferTermChoices extends Component {
    static template = "ab_ecommerce_storefront.OfferTermChoices";
    static props = standardFieldProps;

    get choices() {
        return this.props.record.context.ab_draft_term_choices || [];
    }

    selected(choice) {
        return Object.entries(choice.values).every(([field, value]) => this.props.record.data[field] === value);
    }

    select(choice) {
        return this.props.record.update(choice.values);
    }
}

registry.category("fields").add("ab_offer_term_choices", {
    component: OfferTermChoices,
    supportedTypes: ["float"],
});
