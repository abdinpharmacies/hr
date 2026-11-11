/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService, useSpellCheck } from "@web/core/utils/hooks";
import { useInputField } from "@web/views/fields/input_field_hook";
import { TextField, textField } from "@web/views/fields/text/text_field";

import { useEffect, useRef } from "@odoo/owl";

export const MAX_PRODUCT_IMPORT_LINES = 1000;

export class SmartProductImportTextField extends TextField {
    static template = "web.TextField";

    setup() {
        this.divRef = useRef("div");
        this.textareaRef = useRef("textarea");
        this.notification = useService("notification");
        useInputField({
            getValue: () => this.props.record.data[this.props.name] || "",
            refName: "textarea",
            parse: (v) => this.parse(v),
            preventLineBreaks: !this.props.lineBreaks,
        });
        useSpellCheck({ refName: "textarea" });

        useEffect(
            (textarea) => {
                if (textarea) {
                    textarea.setAttribute("wrap", "off");
                    textarea.setAttribute("rows", "2");
                    textarea.classList.add("ab_smart_product_import_textarea");
                    this.updateDuplicateWarning(textarea);
                    textarea.addEventListener("input", this.onProductImportInput);
                    return () =>
                        textarea.removeEventListener("input", this.onProductImportInput);
                }
            },
            () => [this.textareaRef.el]
        );

        this.selectionStart = this.props.record.data[this.props.name]?.length || 0;
    }

    onProductImportInput = (ev) => {
        const textarea = ev.target;
        const truncated = this.truncateProductImportText(
            textarea.value,
            MAX_PRODUCT_IMPORT_LINES
        );
        if (truncated !== textarea.value) {
            textarea.value = truncated;
            textarea.dispatchEvent(new InputEvent("input", { bubbles: true }));
            this.notification.add(
                _t("Only 1000 product lines are allowed. Extra lines have been ignored."),
                {
                    type: "warning",
                    title: _t("Product Import"),
                }
            );
        }
        this.updateDuplicateWarning(textarea);
        this.scrollToImportEnd(textarea);
    };

    updateDuplicateWarning(textarea) {
        const duplicateWarning = this.getDuplicateWarningElement(textarea);
        if (!duplicateWarning) {
            return;
        }
        duplicateWarning.classList.toggle("d-none", !this.hasDuplicateProductLines(textarea.value));
    }

    getDuplicateWarningElement(textarea) {
        const container = textarea.closest(".o_field_widget");
        if (!container) {
            return null;
        }
        let duplicateWarning = container.querySelector(".ab_smart_product_import_duplicate_warning");
        if (!duplicateWarning) {
            duplicateWarning = document.createElement("div");
            duplicateWarning.className =
                "ab_smart_product_import_duplicate_warning text-warning small mt-1 text-nowrap d-none";
            duplicateWarning.textContent = _t("Duplicate products detected in the entered list.");
            container.appendChild(duplicateWarning);
        }
        return duplicateWarning;
    }

    hasDuplicateProductLines(value) {
        const productCodes = new Set();
        for (const rawLine of (value || "").split("\n")) {
            const line = rawLine.trim();
            if (!line) {
                continue;
            }
            const code = this.getProductCodeFromLine(line);
            if (!code) {
                continue;
            }
            if (productCodes.has(code)) {
                return true;
            }
            productCodes.add(code);
        }
        return false;
    }

    getProductCodeFromLine(line) {
        const separatedParts = line.split(/[\t,;]+/).map((part) => part.trim()).filter(Boolean);
        if (separatedParts.length >= 2) {
            return separatedParts[0];
        }
        const whitespaceParts = line.split(/\s+/).filter(Boolean);
        if (whitespaceParts.length >= 2) {
            return whitespaceParts.slice(0, -1).join(" ").trim();
        }
        return "";
    }

    truncateProductImportText(value, maxLines) {
        let productLines = 0;
        let lineStart = 0;
        for (let index = 0; index <= value.length; index++) {
            if (index < value.length && value[index] !== "\n") {
                continue;
            }
            const line = value.slice(lineStart, index);
            if (line.trim()) {
                productLines += 1;
                if (productLines > maxLines) {
                    return value.slice(0, lineStart);
                }
            }
            lineStart = index + 1;
        }
        return value;
    }

    scrollToImportEnd(textarea) {
        requestAnimationFrame(() => {
            textarea.scrollTop = textarea.scrollHeight;
        });
    }
}

export const smartProductImportTextField = {
    ...textField,
    component: SmartProductImportTextField,
};

registry.category("fields").add("ab_smart_product_import_text", smartProductImportTextField);
