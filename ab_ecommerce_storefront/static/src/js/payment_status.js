/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";

export class AbPaymentReferenceCopy extends Interaction {
    static selector = ".ab-payment-status-page";

    setup() {
        this.onClick = this.onClick.bind(this);
    }

    start() {
        this.el.addEventListener("click", this.onClick);
    }

    destroy() {
        this.el.removeEventListener("click", this.onClick);
        window.clearTimeout(this.feedbackTimer);
    }

    async onClick(ev) {
        const button = ev.target.closest("[data-ab-copy-value]");
        if (!button || !navigator.clipboard) {
            return;
        }
        ev.preventDefault();
        await navigator.clipboard.writeText(button.dataset.abCopyValue || "");
        const label = button.querySelector("span");
        const originalLabel = label?.textContent || "";
        button.classList.add("is-copied");
        if (label) {
            label.textContent = _t("Copied");
        }
        window.clearTimeout(this.feedbackTimer);
        this.feedbackTimer = window.setTimeout(() => {
            button.classList.remove("is-copied");
            if (label) {
                label.textContent = originalLabel || _t("Copy");
            }
        }, 1600);
    }
}

registry
    .category("public.interactions")
    .add("ab_ecommerce_storefront.payment_reference_copy", AbPaymentReferenceCopy);
