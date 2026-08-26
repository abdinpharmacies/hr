/** @odoo-module **/

import { Component, onMounted, onWillDestroy, useEffect, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { getPopoverForTarget } from "@web/core/popover/popover";
import { useService } from "@web/core/utils/hooks";
import { useDebounced } from "@web/core/utils/timing";
import { AbCharAutocompleteSearchMoreDialog } from "@ab_widgets/ab_char_autocomplete";

const AUTOCOMPLETE_ATTRIBUTE = "data-ab-char-autocomplete";
const DROPDOWN_LIMIT = 7;
const INPUT_DEBOUNCE_DELAY = 250;
const SUPPORTED_INPUT_TYPES = new Set(["", "text", "search", "email", "tel", "url"]);
const MODEL_NAME_RE = /^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*$/;
const FIELD_NAME_RE = /^[A-Za-z_][A-Za-z0-9_]*$/;
const AUTOCOMPLETE_SOURCE_REGISTRY = registry.category("ab_char_autocomplete_sources");

let nextAutocompleteId = 0;

function parseAutocompleteSource(input, warn = false) {
    const source = String(input.getAttribute(AUTOCOMPLETE_ATTRIBUTE) || "").trim();
    const separatorIndex = source.lastIndexOf(".");
    if (
        !source ||
        /\s/.test(source) ||
        separatorIndex <= 0 ||
        separatorIndex === source.length - 1
    ) {
        if (warn && source) {
            console.warn(`Invalid ${AUTOCOMPLETE_ATTRIBUTE} value:`, source);
        }
        return false;
    }
    const modelName = source.slice(0, separatorIndex);
    const fieldName = source.slice(separatorIndex + 1);
    if (!MODEL_NAME_RE.test(modelName) || !FIELD_NAME_RE.test(fieldName)) {
        if (warn) {
            console.warn(`Invalid ${AUTOCOMPLETE_ATTRIBUTE} value:`, source);
        }
        return false;
    }
    return { modelName, fieldName };
}

function normalizeText(text) {
    return String(text || "").replace(/\s+/g, " ").trim().toLowerCase();
}

function getInputLabelText(input) {
    const labels = [];
    if (input.id && window.CSS?.escape) {
        const label = document.querySelector(`label[for="${window.CSS.escape(input.id)}"]`);
        if (label) {
            labels.push(label.textContent);
        }
    }
    const fieldContainer = input.closest(".col-12, .col-md-4, .o_wrap_field, .o_field_widget");
    const localLabel = fieldContainer?.querySelector?.("label");
    if (localLabel) {
        labels.push(localLabel.textContent);
    }
    return normalizeText(labels.join(" "));
}

function getOdooFieldName(input) {
    const field = input.closest(".o_field_widget[name], .o_field_char[name], [data-name]");
    return field?.getAttribute("name") || field?.dataset?.name || input.getAttribute("name") || "";
}

function getOdooModelName(input) {
    const holder = input.closest("[data-res-model], [data-model]");
    return holder?.dataset?.resModel || holder?.dataset?.model || "";
}

function isDoctorSpecialtyInput(input) {
    const labelText = getInputLabelText(input);
    if (input.closest(".ab_sales_doctor_create_dialog")) {
        return labelText.includes("specialty");
    }
    if (getOdooFieldName(input) !== "specialty") {
        return false;
    }
    const modelName = getOdooModelName(input);
    return !modelName || modelName === "ab_doctor";
}

function getRegisteredAutocompleteSource(input) {
    for (const source of AUTOCOMPLETE_SOURCE_REGISTRY.getAll()) {
        if (source?.match?.(input)) {
            return {
                modelName: source.modelName,
                fieldName: source.fieldName,
            };
        }
    }
    return false;
}

function getAutocompleteSource(input, warn = false) {
    if (input.hasAttribute(AUTOCOMPLETE_ATTRIBUTE)) {
        return parseAutocompleteSource(input, warn);
    }
    return getRegisteredAutocompleteSource(input);
}

function isEligibleInput(target) {
    if (!(target instanceof HTMLInputElement)) {
        return false;
    }
    const inputType = String(target.getAttribute("type") || "").toLowerCase();
    return (
        !!getAutocompleteSource(target) &&
        !target.disabled &&
        !target.readOnly &&
        SUPPORTED_INPUT_TYPES.has(inputType)
    );
}

AUTOCOMPLETE_SOURCE_REGISTRY.add(
    "ab_doctor.specialty",
    {
        modelName: "ab_doctor",
        fieldName: "specialty",
        match: isDoctorSpecialtyInput,
    },
    { force: true }
);

export class AbCharAutocompleteInputPopover extends Component {
    static template = "ab_widgets.AbCharAutocompleteInputPopover";
    static props = {
        close: Function,
        target: Object,
        modelName: String,
        fieldName: String,
        onSelect: Function,
    };

    setup() {
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        this.notification = useService("notification");
        this.state = useState({
            activeIndex: -1,
            hasMore: false,
            loading: true,
            resultsTransition: false,
            searchTerm: "",
            values: [],
        });
        this.requestSeq = 0;
        this.isSelecting = false;
        this.instanceId = ++nextAutocompleteId;
        this.listId = `ab_char_autocomplete_input_${this.instanceId}`;
        this.resultsTransitionTimer = 0;
        this.originalInputAttributes = new Map();
        this.debouncedSearch = useDebounced(
            () => this.loadSuggestions(this.props.target.value),
            INPUT_DEBOUNCE_DELAY
        );

        this.onTargetInput = this.onTargetInput.bind(this);
        this.onTargetKeydown = this.onTargetKeydown.bind(this);

        useEffect(
            () => this.updateInputAria(),
            () => [this.state.activeIndex, this.state.loading, this.state.values.length]
        );

        onMounted(() => {
            this.enhanceInput();
            this.props.target.addEventListener("input", this.onTargetInput);
            this.props.target.addEventListener("keydown", this.onTargetKeydown);
            this.loadSuggestions(this.props.target.value);
        });

        onWillDestroy(() => {
            this.requestSeq++;
            this.clearResultsTransitionTimer();
            this.props.target.removeEventListener("input", this.onTargetInput);
            this.props.target.removeEventListener("keydown", this.onTargetKeydown);
            this.restoreInput();
        });
    }

    get optionCount() {
        return this.state.values.length + (this.state.hasMore ? 1 : 0);
    }

    optionId(index) {
        return `${this.listId}_option_${index}`;
    }

    rememberInputAttribute(name) {
        if (!this.originalInputAttributes.has(name)) {
            this.originalInputAttributes.set(name, this.props.target.getAttribute(name));
        }
    }

    enhanceInput() {
        for (const attributeName of [
            "autocomplete",
            "role",
            "aria-autocomplete",
            "aria-controls",
            "aria-expanded",
            "aria-activedescendant",
        ]) {
            this.rememberInputAttribute(attributeName);
        }
        this.props.target.setAttribute("autocomplete", "off");
        this.props.target.setAttribute("role", "combobox");
        this.props.target.setAttribute("aria-autocomplete", "list");
        this.props.target.setAttribute("aria-controls", this.listId);
        this.props.target.setAttribute("aria-expanded", "true");
        this.updateInputAria();
    }

    restoreInput() {
        for (const [name, value] of this.originalInputAttributes) {
            if (value === null) {
                this.props.target.removeAttribute(name);
            } else {
                this.props.target.setAttribute(name, value);
            }
        }
    }

    updateInputAria() {
        const input = this.props.target;
        if (!input?.isConnected) {
            return;
        }
        input.setAttribute("aria-expanded", "true");
        if (this.state.activeIndex >= 0) {
            input.setAttribute("aria-activedescendant", this.optionId(this.state.activeIndex));
        } else {
            input.removeAttribute("aria-activedescendant");
        }
    }

    onTargetInput() {
        if (!this.isSelecting) {
            this.state.activeIndex = -1;
            this.state.searchTerm = String(this.props.target.value || "").trim();
            this.debouncedSearch();
        }
    }

    onTargetKeydown(ev) {
        if (ev.key === "ArrowDown") {
            if (!this.optionCount) {
                return;
            }
            ev.preventDefault();
            ev.stopPropagation();
            this.state.activeIndex = Math.min(this.state.activeIndex + 1, this.optionCount - 1);
            return;
        }
        if (ev.key === "ArrowUp") {
            if (!this.optionCount) {
                return;
            }
            ev.preventDefault();
            ev.stopPropagation();
            this.state.activeIndex =
                this.state.activeIndex < 0
                    ? this.optionCount - 1
                    : Math.max(this.state.activeIndex - 1, 0);
            return;
        }
        if (ev.key === "Enter" && this.state.activeIndex >= 0) {
            ev.preventDefault();
            ev.stopPropagation();
            if (this.state.activeIndex < this.state.values.length) {
                this.selectValue(this.state.values[this.state.activeIndex].value);
            } else {
                this.openSearchMore();
            }
            return;
        }
        if (ev.key === "Escape") {
            ev.preventDefault();
            ev.stopPropagation();
            this.props.close();
            return;
        }
        if (ev.key === "Tab") {
            this.props.close();
        }
    }

    async loadSuggestions(searchTerm) {
        const requestSeq = ++this.requestSeq;
        this.setResultsTransition(false);
        this.state.loading = true;
        this.state.searchTerm = String(searchTerm || "").trim();
        this.state.activeIndex = -1;
        try {
            const result = await this.orm.call(
                "ab.char.autocomplete.service",
                "get_suggestions",
                [],
                {
                    model_name: this.props.modelName,
                    field_name: this.props.fieldName,
                    search_term: this.state.searchTerm,
                    current_id: false,
                    limit: DROPDOWN_LIMIT,
                    offset: 0,
                }
            );
            if (requestSeq !== this.requestSeq) {
                return;
            }
            this.setResultsTransition(true);
            this.state.values = result.values || [];
            this.state.hasMore = !!result.has_more;
            this.state.activeIndex = -1;
            this.clearResultsTransitionSoon();
        } catch {
            if (requestSeq === this.requestSeq) {
                this.state.values = [];
                this.state.hasMore = false;
                this.state.activeIndex = -1;
                this.clearResultsTransitionSoon();
                this.notification.add(_t("Could not load suggestions."), { type: "warning" });
            }
        } finally {
            if (requestSeq === this.requestSeq) {
                this.state.loading = false;
            }
        }
    }

    setActiveIndex(index) {
        this.state.activeIndex = index;
    }

    setResultsTransition(active) {
        this.clearResultsTransitionTimer();
        this.state.resultsTransition = active;
    }

    clearResultsTransitionSoon() {
        if (!this.state.resultsTransition) {
            return;
        }
        this.clearResultsTransitionTimer();
        this.resultsTransitionTimer = setTimeout(() => {
            this.state.resultsTransition = false;
            this.resultsTransitionTimer = 0;
        }, 240);
    }

    clearResultsTransitionTimer() {
        if (this.resultsTransitionTimer) {
            clearTimeout(this.resultsTransitionTimer);
            this.resultsTransitionTimer = 0;
        }
    }

    selectValue(value) {
        this.isSelecting = true;
        this.props.onSelect(value);
        this.props.close();
    }

    openSearchMore() {
        const searchTerm = this.state.searchTerm;
        this.props.close();
        this.dialog.add(AbCharAutocompleteSearchMoreDialog, {
            modelName: this.props.modelName,
            fieldName: this.props.fieldName,
            currentId: false,
            searchTerm,
            onSelect: this.props.onSelect,
        });
    }
}

export const abCharAutocompleteInputService = {
    dependencies: ["popover"],

    start(_env, { popover }) {
        let active = null;
        const invalidInputs = new WeakSet();
        const committingInputs = new WeakSet();

        function closeActive() {
            const close = active?.close;
            active = null;
            close?.();
        }

        function commitValue(input, value) {
            if (!input?.isConnected) {
                return;
            }
            committingInputs.add(input);
            try {
                input.value = String(value || "");
                let inputEvent;
                try {
                    inputEvent = new InputEvent("input", {
                        bubbles: true,
                        data: input.value,
                        inputType: "insertReplacementText",
                    });
                } catch {
                    inputEvent = new Event("input", { bubbles: true });
                }
                input.dispatchEvent(inputEvent);
                input.dispatchEvent(new Event("change", { bubbles: true }));
                input.focus({ preventScroll: true });
            } finally {
                committingInputs.delete(input);
            }
        }

        function activate(input) {
            if (!isEligibleInput(input) || committingInputs.has(input)) {
                return;
            }
            if (active?.input === input) {
                return;
            }
            const source = getAutocompleteSource(input, true);
            if (!source) {
                if (!invalidInputs.has(input)) {
                    invalidInputs.add(input);
                }
                return;
            }

            closeActive();
            const token = {};
            const close = popover.add(
                input,
                AbCharAutocompleteInputPopover,
                {
                    target: input,
                    modelName: source.modelName,
                    fieldName: source.fieldName,
                    onSelect: (value) => commitValue(input, value),
                },
                {
                    arrow: false,
                    animation: false,
                    closeOnEscape: true,
                    popoverClass: "o_ab_char_autocomplete_input_popover",
                    position: "bottom-start",
                    setActiveElement: false,
                    onClose: () => {
                        if (active?.token === token) {
                            active = null;
                        }
                    },
                    onPositioned: (element) => {
                        const inputRect = input.getBoundingClientRect();
                        const width = Math.max(180, inputRect.width);
                        const availableBelow = Math.max(140, window.innerHeight - inputRect.bottom - 8);
                        const options = element.querySelector(".o_ab_char_autocomplete_input_options");
                        element.style.minWidth = `${width}px`;
                        element.style.top = `${inputRect.bottom + 4}px`;
                        element.style.maxHeight = `${availableBelow}px`;
                        if (options) {
                            options.style.maxHeight = `${availableBelow}px`;
                        }
                    },
                }
            );
            active = { close, input, token };
        }

        function onFocusIn(ev) {
            if (isEligibleInput(ev.target)) {
                activate(ev.target);
                return;
            }
            if (!active) {
                return;
            }
            const popoverElement = getPopoverForTarget(active.input);
            if (!popoverElement?.contains(ev.target)) {
                closeActive();
            }
        }

        function onInput(ev) {
            if (isEligibleInput(ev.target) && !committingInputs.has(ev.target)) {
                activate(ev.target);
            }
        }

        function onClick(ev) {
            if (isEligibleInput(ev.target)) {
                activate(ev.target);
            }
        }

        document.addEventListener("focusin", onFocusIn, true);
        document.addEventListener("input", onInput, true);
        document.addEventListener("click", onClick, true);

        return {
            close: closeActive,
        };
    },
};

registry.category("services").add("ab_char_autocomplete_input", abCharAutocompleteInputService);
