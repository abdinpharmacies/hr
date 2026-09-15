/** @odoo-module **/

import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

export class AbBusinessPartnershipForm extends Interaction {
    static selector = "[data-ab-business-form]";

    setup() {
        this.onChange = this.onChange.bind(this);
        this.onSubmit = this.onSubmit.bind(this);
        this.onResultChange = this.onResultChange.bind(this);
    }

    start() {
        this.el.addEventListener("change", this.onChange);
        this.el.addEventListener("submit", this.onSubmit, { capture: true });
        this.resultObserver = new MutationObserver(this.onResultChange);
        const result = this.el.querySelector("#s_website_form_result");
        if (result) {
            this.resultObserver.observe(result, { childList: true, subtree: true, characterData: true });
        }
        this.syncFields();
        this.el.dataset.abBusinessReady = "true";
    }

    destroy() {
        this.el.removeEventListener("change", this.onChange);
        this.el.removeEventListener("submit", this.onSubmit, { capture: true });
        this.resultObserver?.disconnect();
    }

    onChange(event) {
        if (event.target.name === "partnership_type") {
            this.syncFields();
        }
    }

    syncFields() {
        const type = this.el.querySelector('[name="partnership_type"]:checked')?.value;
        this.el.querySelector("#ab_business_details").hidden = !type;
        const productFields = this.el.querySelector("[data-ab-product-fields]");
        productFields.hidden = type !== "product";
        productFields.querySelectorAll("input").forEach((input) => {
            input.disabled = type !== "product";
        });
    }

    onSubmit() {
        if (this.el.classList.contains("ab-contact-form-submitting")) {
            return;
        }
        this.el.classList.add("ab-contact-form-submitting");
        this.el.setAttribute("aria-busy", "true");
        const button = this.el.querySelector(".s_website_form_send");
        if (button) {
            button.dataset.abOriginalHtml = button.innerHTML;
            button.disabled = true;
            button.innerHTML = `<span class="ab-contact-submit-spinner" aria-hidden="true"></span><span>${_t("Sending request...")}</span>`;
        }
    }

    onResultChange() {
        const resultText = this.el.querySelector("#s_website_form_result")?.textContent?.trim();
        if (resultText) {
            this.restoreSubmitState();
        }
    }

    restoreSubmitState() {
        this.el.classList.remove("ab-contact-form-submitting");
        this.el.removeAttribute("aria-busy");
        const button = this.el.querySelector(".s_website_form_send");
        if (button?.dataset.abOriginalHtml) {
            button.disabled = false;
            button.innerHTML = button.dataset.abOriginalHtml;
            delete button.dataset.abOriginalHtml;
        }
    }
}

registry.category("public.interactions").add("ab_ecommerce_storefront.business_partnership", AbBusinessPartnershipForm);
