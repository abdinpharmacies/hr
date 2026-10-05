/** @odoo-module **/

import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";

const TOAST_DURATION = 6500;
const TELEGRAM_OPENED_TOAST_DURATION = 15000;
const ICON_CLASSES = {
    info: "fa-info-circle",
    success: "fa-check-circle",
    warning: "fa-exclamation-triangle",
    error: "fa-exclamation-circle",
};

export class AuthPhoneVerification extends Interaction {
    static selector = "[data-ab-phone-verification]";

    setup() {
        this.hideTimer = null;
        this.onClick = this.onClick.bind(this);
    }

    start() {
        this.el.addEventListener("click", this.onClick);
        const toast = this.el.querySelector("[data-ab-phone-toast].is-visible");
        if (toast) {
            this.scheduleHide(toast);
        }
    }

    destroy() {
        this.el.removeEventListener("click", this.onClick);
        window.clearTimeout(this.hideTimer);
    }

    onClick(event) {
        const closeButton = event.target.closest("[data-ab-phone-toast-close]");
        if (closeButton && this.el.contains(closeButton)) {
            this.hideToast(closeButton.closest("[data-ab-phone-toast]"));
            return;
        }
        const telegramLink = event.target.closest("[data-ab-telegram-link]");
        if (telegramLink && this.el.contains(telegramLink)) {
            const telegramAppLink = this.getTelegramAppLink(telegramLink.href);
            if (telegramAppLink) {
                event.preventDefault();
                window.location.assign(telegramAppLink);
            }
            this.showToast(
                telegramLink.dataset.abToastMessage,
                "info",
                TELEGRAM_OPENED_TOAST_DURATION
            );
        }
    }

    getTelegramAppLink(href) {
        try {
            const webLink = new URL(href, window.location.origin);
            if (webLink.hostname.toLowerCase() !== "t.me") {
                return null;
            }
            const [botUsername] = webLink.pathname.split("/").filter(Boolean);
            if (!botUsername) {
                return null;
            }
            const appLink = new URL("tg://resolve");
            appLink.searchParams.set("domain", botUsername);
            const startToken = webLink.searchParams.get("start");
            if (startToken) {
                appLink.searchParams.set("start", startToken);
            }
            return appLink.toString();
        } catch {
            return null;
        }
    }

    showToast(message, type, duration = TOAST_DURATION) {
        const toast = this.el.querySelector("[data-ab-phone-toast]");
        if (!toast || !message) {
            return;
        }
        const messageElement = toast.querySelector("[data-ab-phone-toast-message]");
        const icon = toast.querySelector("[data-ab-phone-toast-icon]");
        for (const toastType of Object.keys(ICON_CLASSES)) {
            toast.classList.remove(`is-${toastType}`);
        }
        toast.classList.add(`is-${type}`);
        if (messageElement) {
            messageElement.textContent = message;
        }
        if (icon) {
            for (const iconClass of Object.values(ICON_CLASSES)) {
                icon.classList.remove(iconClass);
            }
            icon.classList.add(ICON_CLASSES[type]);
        }
        toast.hidden = false;
        window.requestAnimationFrame(() => toast.classList.add("is-visible"));
        this.scheduleHide(toast, duration);
    }

    scheduleHide(toast, duration = TOAST_DURATION) {
        window.clearTimeout(this.hideTimer);
        this.hideTimer = window.setTimeout(() => this.hideToast(toast), duration);
    }

    hideToast(toast) {
        if (!toast) {
            return;
        }
        window.clearTimeout(this.hideTimer);
        toast.classList.remove("is-visible");
        window.setTimeout(() => {
            if (!toast.classList.contains("is-visible")) {
                toast.hidden = true;
            }
        }, 220);
    }
}

registry.category("public.interactions").add("ab_ecommerce_storefront.auth_phone_verification", AuthPhoneVerification);
