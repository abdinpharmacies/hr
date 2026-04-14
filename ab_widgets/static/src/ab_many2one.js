/** @odoo-module **/

import { Component } from "@odoo/owl";
import { Many2One } from "@web/views/fields/many2one/many2one";

export class ABMany2one extends Component {
    static template = "ab_widgets.ABMany2one";
    static components = { Many2One };
    static props = {
        relation: String,
        value: { type: [Object, Boolean], optional: true },
        onUpdate: Function,
        domain: { type: [Function, Array], optional: true },
        context: { type: Object, optional: true },
        placeholder: { type: String, optional: true },
        string: { type: String, optional: true },
        canCreate: { type: Boolean, optional: true },
        canCreateEdit: { type: Boolean, optional: true },
        canQuickCreate: { type: Boolean, optional: true },
        canOpen: { type: Boolean, optional: true },
        canWrite: { type: Boolean, optional: true },
        searchThreshold: { type: Number, optional: true },
        searchMoreLabel: { type: String, optional: true },
    };

    get domainGetter() {
        return () => {
            const domain = this.props.domain;
            if (typeof domain === "function") {
                return domain() || [];
            }
            return domain || [];
        };
    }

    clearValue(ev) {
        ev.preventDefault();
        ev.stopPropagation();
        if (this.props.onUpdate) {
            this.props.onUpdate(false);
        }
    }
}
