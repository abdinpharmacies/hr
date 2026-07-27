/** @odoo-module **/

import { Component, xml } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { formatFloat } from "@web/views/fields/formatters";

export class PctBarWidget extends Component {
    static template = xml`
        <span class="sd-pct-bar" t-att-style="'--pct:' + pctValue">
            <t t-esc="displayValue"/>
        </span>
    `;

    setup() {
        const raw = Number(this.props.record.data[this.props.name] || 0);
        this.pctValue = String(raw.toFixed(1));
        this.displayValue = formatFloat(raw, { digits: [false, 1] }) + '%';
    }
}

registry.category("fields").add("pct_bar", {
    component: PctBarWidget,
    fieldDependencies: [],
    supportedTypes: ["float"],
});
