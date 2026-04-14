/** @odoo-module **/

import {AutoComplete} from "@web/core/autocomplete/autocomplete";
import {getActiveHotkey} from "@web/core/hotkeys/hotkey_service";
import {patch} from "@web/core/utils/patch";
import {Many2XAutocomplete} from "@web/views/fields/relational_utils";

const SEARCH_MORE_HOTKEYS = new Set(["f1", "f6"]);

patch(AutoComplete, {
    props: {
        ...AutoComplete.props,
        onSearchMoreHotkey: {type: Function, optional: true},
    },
});

patch(AutoComplete.prototype, {
    async onInputKeydown(ev) {
        const hotkey = getActiveHotkey(ev);
        if (SEARCH_MORE_HOTKEYS.has(hotkey) && this.props.onSearchMoreHotkey) {
            ev.preventDefault();
            ev.stopPropagation();
            await this.props.onSearchMoreHotkey();
            return;
        }
        return super.onInputKeydown(ev);
    },
});

patch(Many2XAutocomplete.prototype, {
    get autoCompleteProps() {
        return {
            ...super.autoCompleteProps,
            onSearchMoreHotkey: () => this.onSearchMoreHotkey(),
        };
    },

    async onSearchMoreHotkey() {
        const inputEl = this.autoCompleteContainer?.el?.querySelector("input");
        const request = inputEl ? inputEl.value : "";
        return this.onSearchMore(request);
    },
});
