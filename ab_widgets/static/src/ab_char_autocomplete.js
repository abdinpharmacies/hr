/** @odoo-module **/

import { AutoComplete } from "@web/core/autocomplete/autocomplete";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { pick } from "@web/core/utils/objects";
import { formatChar } from "@web/views/fields/formatters";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { Component, useState } from "@odoo/owl";

const DROPDOWN_LIMIT = 7;
const SEARCH_MORE_LIMIT = 40;

export class AbCharAutocompleteSearchMoreDialog extends Component {
    static template = "ab_widgets.AbCharAutocompleteSearchMoreDialog";
    static components = { Dialog };
    static props = {
        close: Function,
        modelName: String,
        fieldName: String,
        currentId: { type: [Number, Boolean], optional: true },
        searchTerm: { type: String, optional: true },
        onSelect: Function,
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            searchTerm: this.props.searchTerm || "",
            values: [],
            offset: 0,
            hasMore: false,
            loading: false,
        });
        this.requestSeq = 0;
        this.loadPage(0);
    }

    get pageNumber() {
        return Math.floor(this.state.offset / SEARCH_MORE_LIMIT) + 1;
    }

    get pageLabel() {
        return _t("Page %s", this.pageNumber);
    }

    get canGoPrevious() {
        return this.state.offset > 0 && !this.state.loading;
    }

    get canGoNext() {
        return this.state.hasMore && !this.state.loading;
    }

    async loadPage(offset) {
        const requestSeq = ++this.requestSeq;
        this.state.loading = true;
        try {
            const result = await this.orm.call(
                "ab.char.autocomplete.service",
                "get_suggestions",
                [],
                {
                    model_name: this.props.modelName,
                    field_name: this.props.fieldName,
                    search_term: this.state.searchTerm,
                    current_id: this.props.currentId || false,
                    limit: SEARCH_MORE_LIMIT,
                    offset,
                }
            );
            if (requestSeq !== this.requestSeq) {
                return;
            }
            this.state.values = result.values || [];
            this.state.offset = result.offset || 0;
            this.state.hasMore = !!result.has_more;
        } catch {
            if (requestSeq === this.requestSeq) {
                this.state.values = [];
                this.state.hasMore = false;
                this.notification.add(_t("Could not load suggestions."), { type: "warning" });
            }
        } finally {
            if (requestSeq === this.requestSeq) {
                this.state.loading = false;
            }
        }
    }

    onSearchInput(ev) {
        this.state.searchTerm = ev.target.value;
    }

    onSearchChange() {
        this.loadPage(0);
    }

    selectValue(value) {
        this.props.onSelect(value);
        this.props.close();
    }

    previousPage() {
        if (this.canGoPrevious) {
            this.loadPage(Math.max(0, this.state.offset - SEARCH_MORE_LIMIT));
        }
    }

    nextPage() {
        if (this.canGoNext) {
            this.loadPage(this.state.offset + SEARCH_MORE_LIMIT);
        }
    }
}

export class AbCharAutocompleteField extends Component {
    static template = "ab_widgets.AbCharAutocompleteField";
    static components = { AutoComplete };
    static props = {
        ...standardFieldProps,
        autocomplete: { type: String, optional: true },
        placeholder: { type: String, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        this.notification = useService("notification");
        this.requestSeq = 0;
    }

    get currentValue() {
        return this.props.record.data[this.props.name] || "";
    }

    get formattedValue() {
        return formatChar(this.currentValue);
    }

    get currentId() {
        return this.props.record.resId || false;
    }

    get maxLength() {
        return this.props.record.fields[this.props.name].size;
    }

    get autocompleteProps() {
        return {
            value: this.currentValue,
            id: this.props.id,
            placeholder: this.props.placeholder || "",
            autocomplete: this.props.autocomplete || "off",
            autoSelect: false,
            inputDebounceDelay: 250,
            searchOnInputClick: false,
            onChange: ({ inputValue }) => this.commitValue(inputValue),
            onBlur: ({ inputValue }) => this.commitValue(inputValue),
            onFocus: (ev) => this.onAutocompleteFocus(ev),
            sources: [
                {
                    placeholder: _t("Loading..."),
                    options: (term) => this.loadDropdownOptions(term),
                },
            ],
            menuCssClass: "o_ab_char_autocomplete_menu",
        };
    }

    async loadDropdownOptions(term) {
        const requestSeq = ++this.requestSeq;
        try {
            const result = await this.fetchSuggestions(term, DROPDOWN_LIMIT, 0);
            if (requestSeq !== this.requestSeq) {
                return [];
            }
            const options = (result.values || []).map((row) => ({
                label: row.value,
                onSelect: () => this.commitValue(row.value),
            }));
            if (result.has_more) {
                options.push({
                    label: _t("Search More..."),
                    cssClass: "o_ab_char_autocomplete_search_more",
                    onSelect: () => this.openSearchMore(term),
                });
            }
            return options;
        } catch {
            if (requestSeq === this.requestSeq) {
                this.notification.add(_t("Could not load suggestions."), { type: "warning" });
            }
            return [];
        }
    }

    fetchSuggestions(searchTerm, limit, offset) {
        return this.orm.call(
            "ab.char.autocomplete.service",
            "get_suggestions",
            [],
            {
                model_name: this.props.record.resModel,
                field_name: this.props.name,
                search_term: searchTerm || "",
                current_id: this.currentId,
                limit,
                offset,
            }
        );
    }

    openSearchMore(searchTerm) {
        this.dialog.add(AbCharAutocompleteSearchMoreDialog, {
            modelName: this.props.record.resModel,
            fieldName: this.props.name,
            currentId: this.currentId,
            searchTerm: searchTerm || "",
            onSelect: (value) => this.commitValue(value),
        });
    }

    onAutocompleteFocus(ev) {
        if (this.maxLength > 0) {
            ev.target.setAttribute("maxlength", this.maxLength);
        }
        ev.target.dispatchEvent(new InputEvent("input", { bubbles: true }));
    }

    commitValue(value) {
        const nextValue = value || "";
        if (nextValue !== this.currentValue) {
            return this.props.record.update({ [this.props.name]: nextValue });
        }
    }
}

export const abCharAutocompleteField = {
    component: AbCharAutocompleteField,
    displayName: _t("Char Autocomplete"),
    supportedTypes: ["char"],
    extractProps: ({ attrs, placeholder }) => ({
        ...pick(attrs, "autocomplete"),
        placeholder,
    }),
};

registry.category("fields").add("ab_char_autocomplete", abCharAutocompleteField);
