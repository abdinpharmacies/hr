import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { isValidEgyptianMobile } from "@ab_ecommerce_storefront/js/auth";

class WhatsAppStart extends Interaction {
    static selector = ".ab-auth-page";
    dynamicContent = {
        _root: {
            "t-on-input": this.updateVisibility,
            "t-on-change": this.updateVisibility,
            "t-on-click": this.startVerification,
        },
    };

    start() {
        this.updateVisibility();
        this.observer = new MutationObserver(() => this.updateVisibility());
        this.observer.observe(this.el, {childList: true, subtree: true});
        this.el.dataset.abWhatsappReady = "true";
    }

    updateVisibility() {
        const button = this.el.querySelector("[data-ab-whatsapp-start]");
        if (!button) {
            return;
        }
        const form = button.closest("form");
        const login = form.elements.login.value.trim();
        const phoneMode = Boolean(login && !login.includes("@") && /^[+\d\s().\-٠-٩۰-۹]+$/.test(login));
        button.classList.toggle("d-none", !phoneMode);
        button.disabled = Boolean(this.isSubmitting || !isValidEgyptianMobile(login) || form.querySelector("[data-ab-rate-limit-seconds]"));
        button.dataset.abWhatsappReady = "true";
    }

    destroy() {
        this.observer?.disconnect();
    }

    startVerification(event) {
        const button = event.target.closest("[data-ab-whatsapp-start]");
        if (!button || !this.el.contains(button) || button.disabled || this.isSubmitting) {
            return;
        }
        event.preventDefault();
        const form = button.closest("form");
        const fields = ["name", "login"];
        for (const name of fields) {
            if (!form.elements[name]?.reportValidity()) {
                return;
            }
        }
        const target = document.createElement("form");
        target.method = "post";
        target.action = "/ab_storefront/auth/whatsapp";
        for (const name of [...fields, "csrf_token", "action"]) {
            const input = document.createElement("input");
            input.type = "hidden";
            input.name = name;
            input.value = name === "action" ? "start" : form.elements[name].value;
            target.append(input);
        }
        this.isSubmitting = true;
        button.disabled = true;
        button.textContent = _t("Continuing...");
        document.body.append(target);
        target.submit();
    }
}

class WhatsAppCountdown extends Interaction {
    static selector = "[data-ab-wa-countdown]";

    start() {
        this.deadline = Date.now() + Number(this.el.dataset.abWaCountdown || 0) * 1000;
        this.timer = setInterval(() => {
            const remaining = Math.max(0, Math.ceil((this.deadline - Date.now()) / 1000));
            this.el.disabled = remaining > 0;
            this.el.textContent = remaining ? `${_t("Resend code")} (${remaining})` : _t("Resend code");
            if (!remaining) {
                clearInterval(this.timer);
            }
        }, 1000);
    }

    destroy() {
        clearInterval(this.timer);
    }
}

registry.category("public.interactions").add("ab_storefront_whatsapp_auth.start", WhatsAppStart);
registry.category("public.interactions").add("ab_storefront_whatsapp_auth.countdown", WhatsAppCountdown);
