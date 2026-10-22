/** @odoo-module **/
import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

class HasReturnsBadge extends Component {
    static template = "ab_sales.HasReturnsBadge";
    static props = { ...standardFieldProps };
}

registry.category("fields").add("ab_sales_has_returns", {
    component: HasReturnsBadge,
    supportedTypes: ["boolean"],
});
