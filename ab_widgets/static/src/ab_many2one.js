/** @odoo-module **/

import {Component} from "@odoo/owl";
import {useChildRef} from "@web/core/utils/hooks";
import {Many2XAutocomplete} from "@web/views/fields/relational_utils";

export class ABMany2one extends Component {
    static template = "ab_widgets.ABMany2one";
    static components = {Many2XAutocomplete};
    static props = {
        relation: String,
        value: {type: [Object, Boolean], optional: true},
        update: {type: Function, optional: true},
        onUpdate: {type: Function, optional: true},
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
        nameCreateField: {type: String, optional: true},
        quickCreate: {type: Function, optional: true},
    };

    setup() {
        this.autocompleteContainerRef = useChildRef();
        this.inputId = `ab_many2one_${Math.random().toString(36).slice(2, 10)}`;
        this.getDomain = this.getDomain.bind(this);
        this.onAutocompleteUpdate = this.onAutocompleteUpdate.bind(this);
    }

    get onUpdateHandler() {
        return this.props.update || this.props.onUpdate || false;
    }

    get displayValue() {
        const value = this.props.value || false;
        return String(value?.display_name || value?.name || "").trim();
    }

    get activeActions() {
        return {
            create: !!this.props.canCreate,
            createEdit: !!this.props.canCreateEdit,
            write: this.props.canWrite !== false,
        };
    }

    getDomain() {
        const domain = this.props.domain;
        const raw = typeof domain === "function" ? domain() : domain;
        return this._normalizeDomain(raw);
    }

    _normalizeDomain(domain) {
        const items = Array.isArray(domain) ? domain : [];
        const normalized = [];
        for (const item of items) {
            if (item === null || item === undefined) {
                continue;
            }
            if (Array.isArray(item)) {
                const cleaned = item.filter((part) => part !== null && part !== undefined);
                if (cleaned.length) {
                    normalized.push(cleaned);
                }
                continue;
            }
            normalized.push(item);
        }
        return normalized;
    }

    get autocompleteProps() {
        return {
            value: this.displayValue,
            id: this.inputId,
            placeholder: this.props.placeholder || "",
            resModel: this.props.relation,
            autoSelect: true,
            fieldString: this.props.string || "",
            activeActions: this.activeActions,
            update: this.onAutocompleteUpdate,
            quickCreate: this.props.canQuickCreate ? this.props.quickCreate || null : null,
            context: this.props.context || {},
            getDomain: this.getDomain,
            nameCreateField: this.props.nameCreateField || "name",
            setInputFloats: () => {
            },
            autocomplete_container: this.autocompleteContainerRef,
            // kanbanViewId: false, // Invalid props for component 'Many2XAutocomplete': unknown key 'kanbanViewId'
            searchLimit: this.props.searchThreshold || 7,
            searchMoreLimit: 320,
        };
    }

    onAutocompleteUpdate(value) {
        const handler = this.onUpdateHandler;
        if (!handler) {
            return;
        }
        if (!value || (Array.isArray(value) && !value.length)) {
            handler(false);
            return;
        }
        const first = Array.isArray(value) ? value[0] : value;
        if (!first || typeof first !== "object") {
            handler(false);
            return;
        }
        handler({
            id: first.id || false,
            display_name: first.display_name || first.name || "",
        });
    }

    clearValue(ev) {
        ev.preventDefault();
        ev.stopPropagation();
        const handler = this.onUpdateHandler;
        if (handler) {
            handler(false);
        }
    }
}
