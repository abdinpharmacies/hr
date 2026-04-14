/** @odoo-module **/

import {Component, useState} from "@odoo/owl";
import {ABMany2one} from "@ab_widgets/ab_many2one";

export class ABMany2many extends Component {
    static template = "ab_widgets.ABMany2many";
    static components = {ABMany2one};
    static props = {
        relation: String,
        value: {type: Array, optional: true},
        onUpdate: Function,
        domain: {type: [Function, Array], optional: true},
        context: {type: Object, optional: true},
        placeholder: {type: String, optional: true},
        string: {type: String, optional: true},
        canCreate: {type: Boolean, optional: true},
        canCreateEdit: {type: Boolean, optional: true},
        canQuickCreate: {type: Boolean, optional: true},
        canOpen: {type: Boolean, optional: true},
        canWrite: {type: Boolean, optional: true},
        searchThreshold: {type: Number, optional: true},
        searchMoreLabel: {type: String, optional: true},
    };

    setup() {
        this.state = useState({input: false});
        this.onInputUpdate = this.onInputUpdate.bind(this);
        this.removeValue = this.removeValue.bind(this);
    }

    get selected() {
        return Array.isArray(this.props.value) ? this.props.value : [];
    }

    onInputUpdate(value) {
        if (!value || !value.id) {
            this.state.input = false;
            return;
        }
        const current = this.selected;
        const exists = current.some((row) => row.id === value.id);
        if (!exists) {
            const next = current.concat([{
                id: value.id,
                display_name: value.display_name || value.name || "",
            }]);
            if (this.props.onUpdate) {
                this.props.onUpdate(next);
            }
        }
        this.state.input = false;
    }

    removeValue(id) {
        const next = this.selected.filter((row) => row.id !== id);
        if (this.props.onUpdate) {
            this.props.onUpdate(next);
        }
    }
}
