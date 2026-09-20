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
        window.clearTimeout(this.toastTimer);
    }

    async onClick(ev) {
        const button = ev.target.closest("[data-ab-copy-value]");
        if (!button || !navigator.clipboard) {
            return;
        }
        ev.preventDefault();
        const copiedValue = button.dataset.abCopyValue || "";
        await navigator.clipboard.writeText(copiedValue);
        const label = button.querySelector("span");
        const originalLabel = label?.textContent || "";
        button.classList.add("is-copied");
        if (label) {
            label.textContent = _t("Copied");
        }
        this.showCopyToast({
            title: button.classList.contains("ab-payment-order-copy")
                ? _t("Order number copied")
                : _t("Payment reference copied"),
            detail: button.classList.contains("ab-payment-order-copy")
                ? _t("The order number is ready to paste.")
                : _t("The payment reference is ready to paste."),
            value: copiedValue,
        });
        window.clearTimeout(this.feedbackTimer);
        this.feedbackTimer = window.setTimeout(() => {
            button.classList.remove("is-copied");
            if (label) {
                label.textContent = originalLabel || _t("Copy");
            }
        }, 1600);
    }

    showCopyToast({ title, detail, value }) {
        document.querySelector(".ab-storefront-copy-toast")?.remove();
        window.clearTimeout(this.toastTimer);

        const toast = document.createElement("div");
        toast.className = "ab-storefront-action-toast ab-storefront-copy-toast";
        toast.setAttribute("role", "status");
        toast.setAttribute("aria-live", "polite");

        const media = document.createElement("span");
        media.className = "ab-storefront-action-toast-media";

        const iconWrap = document.createElement("span");
        iconWrap.className = "ab-storefront-action-toast-icon";
        const icon = document.createElement("i");
        icon.className = "fa fa-copy";
        icon.setAttribute("aria-hidden", "true");
        iconWrap.appendChild(icon);
        media.appendChild(iconWrap);

        const copy = document.createElement("span");
        copy.className = "ab-storefront-action-toast-copy";
        const heading = document.createElement("strong");
        heading.textContent = title;
        const message = document.createElement("small");
        message.textContent = value ? `${detail} ${value}` : detail;
        copy.append(heading, message);

        const check = document.createElement("span");
        check.className = "ab-storefront-action-toast-check";
        const checkIcon = document.createElement("i");
        checkIcon.className = "fa fa-check";
        checkIcon.setAttribute("aria-hidden", "true");
        check.appendChild(checkIcon);

        toast.append(media, copy, check);
        document.body.appendChild(toast);
        window.requestAnimationFrame(() => toast.classList.add("is-visible"));
        this.toastTimer = window.setTimeout(() => {
            toast.classList.remove("is-visible");
            window.setTimeout(() => toast.remove(), 260);
        }, 2400);
    }
}

registry
    .category("public.interactions")
    .add("ab_ecommerce_storefront.payment_reference_copy", AbPaymentReferenceCopy);
