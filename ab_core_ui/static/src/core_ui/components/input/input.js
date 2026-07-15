/** @odoo-module **/
import { Component } from "@odoo/owl";

let nextInputId = 1;

function callOptional(callback, ...args) {
    if (callback) {
        callback(...args);
    }
}

export class CoreInput extends Component {
    static template = "core_ui.input";
    static props = {
        id: { type: String, optional: true },
        name: { type: String, optional: true },
        type: { type: String, optional: true },
        value: { type: [String, Number], optional: true },
        label: { type: String, optional: true },
        placeholder: { type: String, optional: true },
        help: { type: String, optional: true },
        error: { type: String, optional: true },
        icon: { type: String, optional: true },
        trailingIcon: { type: String, optional: true },
        size: { type: String, optional: true },
        variant: { type: String, optional: true },
        className: { type: String, optional: true },
        inputClass: { type: String, optional: true },
        bare: { type: Boolean, optional: true },
        disabled: { type: Boolean, optional: true },
        readonly: { type: Boolean, optional: true },
        required: { type: Boolean, optional: true },
        min: { type: [String, Number], optional: true },
        max: { type: [String, Number], optional: true },
        step: { type: [String, Number], optional: true },
        autocomplete: { type: String, optional: true },
        inputMode: { type: String, optional: true },
        ariaLabel: { type: String, optional: true },
        title: { type: String, optional: true },
        onInput: { type: Function, optional: true },
        onChange: { type: Function, optional: true },
        onFocus: { type: Function, optional: true },
        onBlur: { type: Function, optional: true },
    };
    static defaultProps = {
        type: "text",
        value: "",
        label: "",
        placeholder: "",
        help: "",
        error: "",
        icon: "",
        trailingIcon: "",
        size: "",
        variant: "",
        className: "",
        inputClass: "",
        bare: false,
        disabled: false,
        readonly: false,
        required: false,
    };

    setup() {
        this.generatedId = `core_ui_input_${nextInputId++}`;
    }

    get inputId() {
        return this.props.id || this.generatedId;
    }

    get normalizedValue() {
        return this.props.value ?? "";
    }

    get minValue() {
        return this.props.min === undefined ? undefined : this.props.min;
    }

    get maxValue() {
        return this.props.max === undefined ? undefined : this.props.max;
    }

    get stepValue() {
        return this.props.step === undefined ? undefined : this.props.step;
    }

    get fieldClasses() {
        const classes = ["core_ui_field"];
        if (this.props.size) {
            classes.push(`core_ui_field_${this.props.size}`);
        }
        if (this.props.variant) {
            classes.push(`core_ui_field_${this.props.variant}`);
        }
        if (this.props.icon) {
            classes.push("core_ui_field_has_icon");
        }
        if (this.props.trailingIcon) {
            classes.push("core_ui_field_has_trailing_icon");
        }
        if (this.props.error) {
            classes.push("core_ui_field_error");
        }
        if (this.props.disabled) {
            classes.push("core_ui_field_disabled");
        }
        if (this.props.className) {
            classes.push(this.props.className);
        }
        return classes.join(" ");
    }

    get controlClasses() {
        const classes = ["core_ui_input_control"];
        if (this.props.inputClass) {
            classes.push(this.props.inputClass);
        }
        return classes.join(" ");
    }

    onInput(ev) {
        callOptional(this.props.onInput, ev.target.value, ev);
    }

    onChange(ev) {
        callOptional(this.props.onChange, ev.target.value, ev);
    }

    onFocus(ev) {
        callOptional(this.props.onFocus, ev.target.value, ev);
    }

    onBlur(ev) {
        callOptional(this.props.onBlur, ev.target.value, ev);
    }
}

export class CoreTextarea extends CoreInput {
    static template = "core_ui.textarea";
    static props = {
        ...CoreInput.props,
        rows: { type: Number, optional: true },
    };
    static defaultProps = {
        ...CoreInput.defaultProps,
        rows: 3,
    };
}

export class CoreSelect extends Component {
    static template = "core_ui.select";
    static props = {
        id: { type: String, optional: true },
        name: { type: String, optional: true },
        value: { type: [String, Number], optional: true },
        label: { type: String, optional: true },
        placeholder: { type: String, optional: true },
        help: { type: String, optional: true },
        error: { type: String, optional: true },
        options: { type: Array, optional: true },
        size: { type: String, optional: true },
        variant: { type: String, optional: true },
        className: { type: String, optional: true },
        selectClass: { type: String, optional: true },
        disabled: { type: Boolean, optional: true },
        required: { type: Boolean, optional: true },
        ariaLabel: { type: String, optional: true },
        title: { type: String, optional: true },
        onChange: { type: Function, optional: true },
    };
    static defaultProps = {
        value: "",
        label: "",
        placeholder: "",
        help: "",
        error: "",
        options: [],
        size: "",
        variant: "",
        className: "",
        selectClass: "",
        disabled: false,
        required: false,
    };

    setup() {
        this.generatedId = `core_ui_select_${nextInputId++}`;
    }

    get inputId() {
        return this.props.id || this.generatedId;
    }

    get normalizedValue() {
        return String(this.props.value ?? "");
    }

    get fieldClasses() {
        const classes = ["core_ui_field", "core_ui_field_select"];
        if (this.props.size) {
            classes.push(`core_ui_field_${this.props.size}`);
        }
        if (this.props.variant) {
            classes.push(`core_ui_field_${this.props.variant}`);
        }
        if (this.props.error) {
            classes.push("core_ui_field_error");
        }
        if (this.props.disabled) {
            classes.push("core_ui_field_disabled");
        }
        if (this.props.className) {
            classes.push(this.props.className);
        }
        return classes.join(" ");
    }

    get controlClasses() {
        const classes = ["core_ui_input_control", "core_ui_select_control"];
        if (this.props.selectClass) {
            classes.push(this.props.selectClass);
        }
        return classes.join(" ");
    }

    optionValue(option) {
        return typeof option === "object" ? option.value : option;
    }

    optionLabel(option) {
        return typeof option === "object" ? option.label : option;
    }

    optionDisabled(option) {
        return typeof option === "object" && Boolean(option.disabled);
    }

    optionKey(option, index) {
        return `${this.optionValue(option)}_${index}`;
    }

    isOptionSelected(option) {
        return String(this.optionValue(option)) === this.normalizedValue;
    }

    onChange(ev) {
        callOptional(this.props.onChange, ev.target.value, ev);
    }
}

export class CoreSearchSelect extends Component {
    static template = "core_ui.search_select";
    static props = {
        id: { type: String, optional: true },
        value: { type: [String, Number], optional: true },
        searchValue: { type: String, optional: true },
        placeholder: { type: String, optional: true },
        allLabel: { type: String, optional: true },
        emptyText: { type: String, optional: true },
        loadingText: { type: String, optional: true },
        resultsLabel: { type: String, optional: true },
        clearLabel: { type: String, optional: true },
        options: { type: Array, optional: true },
        maxVisibleOptions: { type: Number, optional: true },
        icon: { type: String, optional: true },
        clearable: { type: Boolean, optional: true },
        open: { type: Boolean, optional: true },
        disabled: { type: Boolean, optional: true },
        loading: { type: Boolean, optional: true },
        className: { type: String, optional: true },
        inputClass: { type: String, optional: true },
        menuClass: { type: String, optional: true },
        ariaLabel: { type: String, optional: true },
        onInput: { type: Function, optional: true },
        onFocus: { type: Function, optional: true },
        onToggle: { type: Function, optional: true },
        onSelect: { type: Function, optional: true },
        onClear: { type: Function, optional: true },
    };
    static defaultProps = {
        value: "",
        searchValue: "",
        placeholder: "",
        allLabel: "",
        emptyText: "No results found",
        loadingText: "Loading...",
        resultsLabel: "results",
        clearLabel: "Clear",
        options: [],
        maxVisibleOptions: 50,
        icon: "oi oi-search",
        clearable: true,
        open: false,
        disabled: false,
        loading: false,
        className: "",
        inputClass: "",
        menuClass: "",
    };

    setup() {
        this.generatedId = `core_ui_search_select_${nextInputId++}`;
    }

    get inputId() {
        return this.props.id || this.generatedId;
    }

    get normalizedValue() {
        return String(this.props.value ?? "");
    }

    get normalizedSearchValue() {
        return this.props.searchValue || "";
    }

    get visibleOptions() {
        return (this.props.options || []).slice(0, this.props.maxVisibleOptions);
    }

    get hasSelection() {
        return Boolean(Number(this.normalizedValue || 0));
    }

    get showClear() {
        return this.props.clearable && !this.props.disabled && (this.hasSelection || this.normalizedSearchValue);
    }

    get wrapperClasses() {
        const classes = ["core_ui_search_select"];
        if (this.props.open) {
            classes.push("core_ui_search_select_open");
        }
        if (this.props.disabled) {
            classes.push("core_ui_search_select_disabled");
        }
        if (this.props.className) {
            classes.push(this.props.className);
        }
        return classes.join(" ");
    }

    get inputClasses() {
        const classes = ["core_ui_search_select_input"];
        if (this.props.inputClass) {
            classes.push(this.props.inputClass);
        }
        return classes.join(" ");
    }

    get menuClasses() {
        const classes = ["core_ui_search_select_menu"];
        if (this.props.menuClass) {
            classes.push(this.props.menuClass);
        }
        return classes.join(" ");
    }

    optionValue(option) {
        if (typeof option !== "object") {
            return option;
        }
        return option.value ?? option.id ?? "";
    }

    optionLabel(option) {
        if (typeof option !== "object") {
            return option;
        }
        return option.label ?? option.name ?? "";
    }

    optionKey(option, index) {
        return `${this.optionValue(option)}_${index}`;
    }

    isSelected(option) {
        return String(this.optionValue(option)) === this.normalizedValue;
    }

    onInput(ev) {
        callOptional(this.props.onInput, ev.target.value, ev);
    }

    onFocus(ev) {
        callOptional(this.props.onFocus, ev.target.value, ev);
    }

    onToggle(ev) {
        callOptional(this.props.onToggle, ev);
    }

    onSelect(option, ev) {
        callOptional(this.props.onSelect, this.optionValue(option), this.optionLabel(option), option, ev);
    }

    onSelectAll(ev) {
        callOptional(this.props.onSelect, 0, this.props.allLabel, null, ev);
    }

    onClear(ev) {
        if (this.props.onClear) {
            this.props.onClear(ev);
        } else {
            this.onSelectAll(ev);
        }
    }
}

export class CoreCheckbox extends Component {
    static template = "core_ui.checkbox";
    static props = {
        id: { type: String, optional: true },
        name: { type: String, optional: true },
        value: { type: [String, Number], optional: true },
        checked: { type: Boolean, optional: true },
        label: { type: String, optional: true },
        help: { type: String, optional: true },
        className: { type: String, optional: true },
        disabled: { type: Boolean, optional: true },
        required: { type: Boolean, optional: true },
        onChange: { type: Function, optional: true },
    };
    static defaultProps = {
        value: "",
        checked: false,
        label: "",
        help: "",
        className: "",
        disabled: false,
        required: false,
    };

    setup() {
        this.generatedId = `core_ui_check_${nextInputId++}`;
    }

    get inputId() {
        return this.props.id || this.generatedId;
    }

    get fieldClasses() {
        const classes = ["core_ui_choice"];
        if (this.props.disabled) {
            classes.push("core_ui_choice_disabled");
        }
        if (this.props.className) {
            classes.push(this.props.className);
        }
        return classes.join(" ");
    }

    onChange(ev) {
        callOptional(this.props.onChange, ev.target.checked, this.props.value, ev);
    }
}

export class CoreRadio extends CoreCheckbox {
    static template = "core_ui.radio";
}

export class CoreToggle extends CoreCheckbox {
    static template = "core_ui.toggle";
}
