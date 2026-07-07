/** @odoo-module **/
import { Component, useState } from "@odoo/owl";

export class CoreUISearch extends Component {
    static template = "core_ui.search";
    static props = {
        placeholder: { type: String, optional: true },
        onSearch: { type: Function },
        value: { type: String, optional: true },
    };

    static defaultProps = {
        placeholder: "Search components, tokens, patterns...",
    };

    setup() {
        this.state = useState({
            query: this.props.value || "",
            isFocused: false,
        });
    }

    onInput(ev) {
        this.state.query = ev.target.value;
        this.props.onSearch(this.state.query);
    }

    onKeydown(ev) {
        if (ev.key === 'Escape') {
            this.state.query = "";
            this.props.onSearch("");
            ev.target.blur();
        }
    }

    onFocus() {
        this.state.isFocused = true;
    }

    onBlur() {
        this.state.isFocused = false;
    }

    clear() {
        this.state.query = "";
        this.props.onSearch("");
    }
}
