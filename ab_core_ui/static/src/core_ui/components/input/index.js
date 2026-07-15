/** @odoo-module **/
import { registerComponent } from "../../registry";
import {
    CoreCheckbox,
    CoreInput,
    CoreRadio,
    CoreSearchSelect,
    CoreSelect,
    CoreTextarea,
    CoreToggle,
} from "./input";

const INPUT_PROPS = {
    label: { type: "string", default: "Field Label", description: "Visible field label" },
    value: { type: "string", default: "", description: "Current field value" },
    placeholder: { type: "string", default: "", description: "Placeholder text" },
    icon: { type: "string", default: "", description: "Optional Font Awesome icon class" },
    disabled: { type: "boolean", default: false, description: "Disable the field" },
    error: { type: "string", default: "", description: "Validation error message" },
};

registerComponent("core_ui.input.text", {
    component: CoreInput,
    name: "Text Input",
    category: "Inputs",
    version: "19.0.1.0.0",
    status: "stable",
    description: "Clean labeled text input with optional icon, help text, and error state.",
    keywords: "input, text, form, field, control",
    templateRef: "core_ui.input",
    propsSchema: INPUT_PROPS,
    demoData: () => ({
        label: "Product Name",
        value: "Paracetamol 500mg",
        placeholder: "Enter product name",
        icon: "fa fa-capsules",
        help: "Use the public display name.",
    }),
});

registerComponent("core_ui.input.search", {
    component: CoreInput,
    name: "Search Input",
    category: "Inputs",
    version: "19.0.1.0.0",
    status: "stable",
    description: "Search input with a leading icon for filter bars and tables.",
    keywords: "input, search, filter, table, lookup",
    templateRef: "core_ui.input",
    propsSchema: INPUT_PROPS,
    demoData: () => ({
        type: "search",
        placeholder: "Search products",
        ariaLabel: "Search products",
        icon: "oi oi-search",
    }),
});

registerComponent("core_ui.input.date", {
    component: CoreInput,
    name: "Date Input",
    category: "Inputs",
    version: "19.0.1.0.0",
    status: "stable",
    description: "Date picker field for dashboards, reports, and operational filters.",
    keywords: "input, date, filter, range, calendar",
    templateRef: "core_ui.input",
    propsSchema: INPUT_PROPS,
    demoData: () => ({
        type: "date",
        label: "Date From",
        value: "2026-07-14",
    }),
});

registerComponent("core_ui.input.number", {
    component: CoreInput,
    name: "Number Input",
    category: "Inputs",
    version: "19.0.1.0.0",
    status: "stable",
    description: "Numeric input with min, max, and step support.",
    keywords: "input, number, numeric, amount, quantity",
    templateRef: "core_ui.input",
    propsSchema: INPUT_PROPS,
    demoData: () => ({
        type: "number",
        label: "Reorder Quantity",
        value: 24,
        min: 0,
        step: 1,
    }),
});

registerComponent("core_ui.input.select", {
    component: CoreSelect,
    name: "Select Input",
    category: "Inputs",
    version: "19.0.1.0.0",
    status: "stable",
    description: "Modern select field for compact option lists.",
    keywords: "input, select, dropdown, options, form",
    templateRef: "core_ui.select",
    propsSchema: {
        label: { type: "string", default: "Store", description: "Visible field label" },
        value: { type: "string", default: "", description: "Selected value" },
        placeholder: { type: "string", default: "Choose an option", description: "Empty option label" },
        options: { type: "array", default: [], description: "Option objects with value and label" },
    },
    demoData: () => ({
        label: "Store",
        placeholder: "All Stores",
        value: "nasr",
        options: [
            { value: "nasr", label: "Nasr City" },
            { value: "maadi", label: "Maadi" },
            { value: "zayed", label: "Sheikh Zayed" },
        ],
    }),
});

registerComponent("core_ui.input.search_select", {
    component: CoreSearchSelect,
    name: "Search Select",
    category: "Inputs",
    version: "19.0.1.0.0",
    status: "stable",
    description: "Searchable dropdown selector with all, clear, loading, empty, result count, and selected states.",
    keywords: "input, search, select, dropdown, autocomplete, filter",
    templateRef: "core_ui.search_select",
    propsSchema: {
        searchValue: { type: "string", default: "", description: "Visible search text" },
        value: { type: "string", default: "", description: "Selected option value" },
        allLabel: { type: "string", default: "All Stores", description: "Optional all-records label" },
        options: { type: "array", default: [], description: "Option objects with id/name or value/label" },
    },
    demoData: () => ({
        searchValue: "Nasr",
        value: 1,
        allLabel: "All Stores",
        placeholder: "Search stores",
        options: [
            { id: 1, name: "Nasr City" },
            { id: 2, name: "Maadi" },
            { id: 3, name: "Sheikh Zayed" },
        ],
        open: true,
    }),
});

registerComponent("core_ui.input.textarea", {
    component: CoreTextarea,
    name: "Textarea",
    category: "Inputs",
    version: "19.0.1.0.0",
    status: "stable",
    description: "Multi-line text input for notes and descriptions.",
    keywords: "input, textarea, notes, description, multi-line",
    templateRef: "core_ui.textarea",
    propsSchema: INPUT_PROPS,
    demoData: () => ({
        label: "Review Notes",
        value: "Approved for branch manager review.",
        rows: 4,
    }),
});

registerComponent("core_ui.input.checkbox", {
    component: CoreCheckbox,
    name: "Checkbox",
    category: "Inputs",
    version: "19.0.1.0.0",
    status: "stable",
    description: "Checkbox control with label and helper text.",
    keywords: "input, checkbox, boolean, option, form",
    templateRef: "core_ui.checkbox",
    propsSchema: null,
    demoData: () => ({
        label: "Require manager approval",
        help: "Recommended for stock-sensitive changes.",
        checked: true,
    }),
});

registerComponent("core_ui.input.radio", {
    component: CoreRadio,
    name: "Radio",
    category: "Inputs",
    version: "19.0.1.0.0",
    status: "stable",
    description: "Radio option for mutually exclusive choices.",
    keywords: "input, radio, choice, option, form",
    templateRef: "core_ui.radio",
    propsSchema: null,
    demoData: () => ({
        label: "Daily",
        name: "range",
        value: "day",
        checked: true,
    }),
});

registerComponent("core_ui.input.toggle", {
    component: CoreToggle,
    name: "Toggle",
    category: "Inputs",
    version: "19.0.1.0.0",
    status: "stable",
    description: "Switch-style boolean input for compact settings.",
    keywords: "input, toggle, switch, boolean, setting",
    templateRef: "core_ui.toggle",
    propsSchema: null,
    demoData: () => ({
        label: "Auto refresh",
        help: "Refresh dashboard data automatically.",
        checked: true,
    }),
});

export { CoreCheckbox, CoreInput, CoreRadio, CoreSearchSelect, CoreSelect, CoreTextarea, CoreToggle };
