/** @odoo-module **/

import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";

export class StorefrontCartHold extends Interaction {
    static selector = "[data-ab-cart-hold]";

    start() {
        this.clockOffset = 0;
        this.stopped = false;
        this.updateCountdown();
        this.refreshDeadline();
        this.interval = setInterval(() => this.updateCountdown(), 1000);
        this.refreshInterval = setInterval(() => this.refreshDeadline(), 15000);
    }

    destroy() {
        this.stopped = true;
        clearInterval(this.interval);
        clearInterval(this.refreshInterval);
        this.abortController?.abort();
    }

    async refreshDeadline() {
        this.abortController?.abort();
        this.abortController = new AbortController();
        try {
            const response = await fetch("/shop/ab/cart-hold", {
                credentials: "same-origin", cache: "no-store", signal: this.abortController.signal,
            });
            if (!response.ok) {
                return;
            }
            const status = await response.json();
            if (!this.stopped) {
                this.el.dataset.expiresAt = status.expires_at || "";
                this.clockOffset = Date.parse(status.server_time) - Date.now();
                this.updateCountdown();
            }
        } catch {
            return;
        }
    }

    updateCountdown() {
        const seconds = Math.max(0, Math.ceil((Date.parse(this.el.dataset.expiresAt) - Date.now() - this.clockOffset) / 1000));
        const active = Number.isFinite(seconds) && seconds > 0;
        this.el.querySelectorAll("[data-ab-cart-hold-active]").forEach((node) => node.classList.toggle("d-none", !active));
        this.el.querySelector("[data-ab-cart-hold-expired]").classList.toggle("d-none", active);
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const remainingSeconds = seconds % 60;
        const formattedTime = [hours, minutes, remainingSeconds]
            .map((value) => String(value).padStart(2, "0"))
            .join(":");
        this.el.querySelector("[data-ab-cart-hold-countdown]").textContent = active
            ? formattedTime
            : "";
    }
}

registry.category("public.interactions").add("ab_ecommerce_storefront.cart_hold", StorefrontCartHold);
