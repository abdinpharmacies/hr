/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";

const ALLOWED_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);

export class AbPrescriptionOrderForm extends Interaction {
    static selector = "[data-ab-prescription-form]";

    setup() {
        this.previewUrl = null;
        this.onChange = this.onChange.bind(this);
        this.onClick = this.onClick.bind(this);
    }

    start() {
        this.inputs = [...this.el.querySelectorAll("[data-ab-prescription-input]")];
        this.error = this.el.querySelector("[data-ab-prescription-error]");
        this.emptyState = this.el.querySelector("[data-ab-prescription-empty]");
        this.preview = this.el.querySelector("[data-ab-prescription-preview]");
        this.previewImage = this.el.querySelector("[data-ab-prescription-preview-image]");
        this.submit = this.el.querySelector("[data-ab-prescription-submit]");
        this.maxSize = Number(this.el.dataset.abPrescriptionMaxSize || 8 * 1024 * 1024);
        this.inputs.forEach((input) => input.addEventListener("change", this.onChange));
        this.el.addEventListener("click", this.onClick);
    }

    destroy() {
        this.inputs?.forEach((input) => input.removeEventListener("change", this.onChange));
        this.el.removeEventListener("click", this.onClick);
        this.revokePreviewUrl();
    }

    onChange(ev) {
        const input = ev.target.closest("[data-ab-prescription-input]");
        if (!input) {
            return;
        }
        const file = input.files?.[0];
        if (!file) {
            this.syncSubmit();
            return;
        }
        const error = this.validateFile(file);
        if (error) {
            this.showError(error);
            this.clearInputs();
            this.showEmptyState();
            return;
        }
        this.inputs.forEach((otherInput) => {
            if (otherInput !== input) {
                otherInput.value = "";
            }
        });
        this.showPreview(file);
        this.showError("");
        this.syncSubmit();
    }

    onClick(ev) {
        const remove = ev.target.closest("[data-ab-prescription-remove]");
        if (!remove) {
            return;
        }
        ev.preventDefault();
        this.clearInputs();
        this.showEmptyState();
        this.showError("");
    }

    validateFile(file) {
        if (!file) {
            return _t("Please upload a prescription image.");
        }
        if (!ALLOWED_TYPES.has(file.type)) {
            return _t("Please upload a JPG, PNG, or WebP image.");
        }
        if (file.size > this.maxSize) {
            return _t("The prescription image is too large. Please upload an image up to 8 MB.");
        }
        return "";
    }

    showPreview(file) {
        this.revokePreviewUrl();
        this.previewUrl = URL.createObjectURL(file);
        this.previewImage.src = this.previewUrl;
        this.preview.classList.remove("d-none");
        this.emptyState.classList.add("d-none");
    }

    showEmptyState() {
        this.revokePreviewUrl();
        if (this.previewImage) {
            this.previewImage.removeAttribute("src");
        }
        this.preview?.classList.add("d-none");
        this.emptyState?.classList.remove("d-none");
        this.syncSubmit();
    }

    showError(message) {
        if (!this.error) {
            return;
        }
        this.error.textContent = message;
        this.error.classList.toggle("d-none", !message);
    }

    clearInputs() {
        this.inputs.forEach((input) => {
            input.value = "";
        });
    }

    syncSubmit() {
        const hasImage = this.inputs.some((input) => Boolean(input.files?.[0]));
        if (this.submit) {
            this.submit.disabled = !hasImage;
        }
    }

    revokePreviewUrl() {
        if (this.previewUrl) {
            URL.revokeObjectURL(this.previewUrl);
            this.previewUrl = null;
        }
    }
}

registry.category("public.interactions").add("ab_ecommerce_storefront.prescription_order_form", AbPrescriptionOrderForm);
