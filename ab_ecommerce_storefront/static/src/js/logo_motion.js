/** @odoo-module **/

import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { Interaction } from "@web/public/interaction";

const DOUBLE_CLICK_DELAY = 430;
const LOADER_APPEAR_DELAY = 450;
const LOADER_RECOVERY_DELAY = 20000;
const LOADER_TIP_STORAGE_KEY = "ab_storefront_loader_tip";
const CHECKOUT_TOAST_STORAGE_PREFIX = "ab_storefront_checkout_success_toast:";

export class AbStorefrontPageLoader extends Interaction {
    static selector = ".ab-storefront #wrapwrap";

    setup() {
        this.body = this.el.ownerDocument.body;
        this.onNavigate = this.onNavigate.bind(this);
        this.onClick = this.onClick.bind(this);
        this.onSubmit = this.onSubmit.bind(this);
        this.onKeydown = this.onKeydown.bind(this);
        this.schedule = this.schedule.bind(this);
        this.dismiss = this.dismiss.bind(this);
    }

    start() {
        if (this.body.classList.contains("editor_enable")) {
            return;
        }
        this.loaderEl = this.body.querySelector("[data-ab-storefront-loader]");
        if (!this.loaderEl) {
            return;
        }
        this.tips = [...this.loaderEl.querySelectorAll("[data-ab-loader-tip]")];
        this.loaderEl.addEventListener("keydown", this.onKeydown);
        window.addEventListener("pageshow", this.dismiss);
        window.addEventListener("pagehide", this.dismiss);
        document.addEventListener("ab-storefront:navigation-pending", this.schedule);
        if (window.navigation) {
            window.navigation.addEventListener("navigate", this.onNavigate);
            window.navigation.addEventListener("navigateerror", this.dismiss);
        } else {
            document.addEventListener("click", this.onClick, true);
            document.addEventListener("submit", this.onSubmit, true);
        }
    }

    isPageDestination(href) {
        let target;
        try {
            target = new URL(href, window.location.href);
        } catch {
            return false;
        }
        return target.origin === window.location.origin
            && /^https?:$/.test(target.protocol)
            && !["1", "true"].includes(target.searchParams.get("download"))
            && !/\/(?:web\/(?:content|image)|report|odoo)(?:\/|$)/.test(target.pathname)
            && !/\.(?:pdf|zip|csv|xlsx?|docx?|png|jpe?g|svg|webp|mp4)$/i.test(target.pathname);
    }

    onNavigate(event) {
        if (event.destination.sameDocument || event.downloadRequest !== null
            || !this.isPageDestination(event.destination.url)) {
            return;
        }
        queueMicrotask(() => {
            if (event.defaultPrevented || event.signal.aborted || this.isDestroyed) {
                return;
            }
            this.navigationSignal = event.signal;
            event.signal.addEventListener("abort", () => {
                if (this.navigationSignal === event.signal) {
                    this.dismiss();
                }
            }, { once: true });
            this.schedule();
        });
    }

    onClick(event) {
        if (!(event.target instanceof Element) || event.button !== 0
            || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
            return;
        }
        const link = event.target.closest("a[href]");
        if (!link || link.hasAttribute("download")
            || (link.target && link.target !== "_self")
            || link.getAttribute("aria-disabled") === "true"
            || !this.isPageDestination(link.href)) {
            return;
        }
        const target = new URL(link.href, window.location.href);
        if (target.pathname === window.location.pathname && target.search === window.location.search) {
            return;
        }
        queueMicrotask(() => {
            if (!event.defaultPrevented) {
                this.schedule();
            }
        });
    }

    onSubmit(event) {
        const form = event.target;
        if (!(form instanceof HTMLFormElement)) {
            return;
        }
        const submitter = event.submitter;
        const target = submitter?.getAttribute("formtarget") ?? form.target;
        const method = submitter?.getAttribute("formmethod") ?? form.method;
        const action = submitter?.getAttribute("formaction") ?? form.action;
        if ((target && target !== "_self") || method.toLowerCase() === "dialog"
            || !this.isPageDestination(action)) {
            return;
        }
        queueMicrotask(() => {
            if (!event.defaultPrevented) {
                this.schedule();
            }
        });
    }

    schedule() {
        if (this.pending || !this.loaderEl || this.isDestroyed
            || this.body.classList.contains("editor_enable")) {
            return;
        }
        this.pending = true;
        this.appearTimer = setTimeout(() => this.show(), LOADER_APPEAR_DELAY);
        this.recoveryTimer = setTimeout(this.dismiss, LOADER_RECOVERY_DELAY);
    }

    show() {
        this.selectTip();
        this.previousFocus = document.activeElement;
        this.inertElements = [...this.body.children].filter((element) => (
            element !== this.loaderEl && !element.hasAttribute("inert")
        ));
        this.inertElements.forEach((element) => element.setAttribute("inert", ""));
        this.content = this.el;
        this.originalBusy = this.content?.getAttribute("aria-busy");
        this.content?.setAttribute("aria-busy", "true");
        this.loaderEl.hidden = false;
        this.body.classList.add("ab-storefront-is-navigating");
        this.loaderEl.focus({ preventScroll: true });
    }

    selectTip() {
        if (!this.tips.length) {
            return;
        }
        let previousIndex = this.tipIndex;
        try {
            const storedIndex = window.sessionStorage.getItem(LOADER_TIP_STORAGE_KEY);
            if (storedIndex !== null && /^\d+$/.test(storedIndex)) {
                previousIndex = Number(storedIndex);
            }
        } catch {
            previousIndex = this.tipIndex;
        }
        this.tipIndex = Number.isSafeInteger(previousIndex) && previousIndex < this.tips.length
            ? (previousIndex + 1) % this.tips.length
            : Math.floor(Math.random() * this.tips.length);
        this.tips.forEach((tip, index) => { tip.hidden = index !== this.tipIndex; });
        this.loaderEl.setAttribute("aria-describedby", this.tips[this.tipIndex].id);
        try {
            window.sessionStorage.setItem(LOADER_TIP_STORAGE_KEY, String(this.tipIndex));
        } catch {
            return;
        }
    }

    onKeydown(event) {
        if (event.key === "Escape") {
            this.dismiss();
        } else if (event.key === "Tab") {
            event.preventDefault();
            this.loaderEl.focus({ preventScroll: true });
        }
    }

    dismiss() {
        clearTimeout(this.appearTimer);
        clearTimeout(this.recoveryTimer);
        this.pending = false;
        this.navigationSignal = null;
        if (!this.loaderEl) {
            return;
        }
        const restoreFocus = this.loaderEl.contains(document.activeElement);
        this.loaderEl.hidden = true;
        this.body.classList.remove("ab-storefront-is-navigating");
        this.inertElements?.forEach((element) => element.removeAttribute("inert"));
        this.inertElements = [];
        if (this.content) {
            if (this.originalBusy === null) {
                this.content.removeAttribute("aria-busy");
            } else {
                this.content.setAttribute("aria-busy", this.originalBusy);
            }
            this.content = null;
        }
        if (restoreFocus && this.previousFocus?.isConnected) {
            this.previousFocus.focus({ preventScroll: true });
        }
        this.loaderEl.removeAttribute("aria-describedby");
    }

    destroy() {
        this.dismiss();
        this.loaderEl?.removeEventListener("keydown", this.onKeydown);
        window.removeEventListener("pageshow", this.dismiss);
        window.removeEventListener("pagehide", this.dismiss);
        window.navigation?.removeEventListener("navigate", this.onNavigate);
        window.navigation?.removeEventListener("navigateerror", this.dismiss);
        document.removeEventListener("click", this.onClick, true);
        document.removeEventListener("submit", this.onSubmit, true);
        document.removeEventListener("ab-storefront:navigation-pending", this.schedule);
    }
}

registry
    .category("public.interactions")
    .add("ab_ecommerce_storefront.page_loader", AbStorefrontPageLoader);

export class AbStorefrontLogoMotion extends Interaction {
    static selector = "[data-ab-brand-logo-motion]";

    setup() {
        this.clickCount = 0;
        this.clickTimer = null;
        this.navigationTimer = null;
        this.onClick = this.onClick.bind(this);
        this.onDoubleClick = this.onDoubleClick.bind(this);
    }

    start() {
        this.el.addEventListener("click", this.onClick);
        this.el.addEventListener("dblclick", this.onDoubleClick);
    }

    destroy() {
        clearTimeout(this.clickTimer);
        clearTimeout(this.navigationTimer);
        this.el.removeEventListener("click", this.onClick);
        this.el.removeEventListener("dblclick", this.onDoubleClick);
    }

    onClick(ev) {
        if (ev.button !== 0 || ev.metaKey || ev.ctrlKey || ev.shiftKey || ev.altKey) {
            return;
        }
        this.clickCount += 1;
        if (this.clickCount === 1) {
            const link = this.el.closest("a");
            this.play("is-awake", 720);
            if (link?.href) {
                ev.preventDefault();
                this.navigationTimer = setTimeout(() => {
                    document.dispatchEvent(new Event("ab-storefront:navigation-pending"));
                    window.location.assign(link.href);
                }, DOUBLE_CLICK_DELAY);
            }
            this.clickTimer = setTimeout(() => {
                this.clickCount = 0;
            }, DOUBLE_CLICK_DELAY);
            return;
        }
        ev.preventDefault();
        ev.stopPropagation();
        this.clickCount = 0;
        clearTimeout(this.clickTimer);
        clearTimeout(this.navigationTimer);
        this.play("is-celebrating", 1150);
    }

    onDoubleClick(ev) {
        ev.preventDefault();
        ev.stopPropagation();
        this.clickCount = 0;
        clearTimeout(this.clickTimer);
        clearTimeout(this.navigationTimer);
        this.play("is-celebrating", 1150);
    }

    play(className, duration) {
        this.el.classList.remove(className);
        void this.el.offsetWidth;
        this.el.classList.add(className);
        setTimeout(() => this.el.classList.remove(className), duration);
    }
}

registry
    .category("public.interactions")
    .add("ab_ecommerce_storefront.logo_motion", AbStorefrontLogoMotion);

export class AbStorefrontCheckoutSuccessMotion extends Interaction {
    static selector = "body";

    start() {
        if (!this.isCheckoutSuccessPage() || this.wasShown()) {
            return;
        }
        this.markShown();
        setTimeout(() => this.showToast(), 520);
    }

    isCheckoutSuccessPage() {
        return window.location.pathname.replace(/\/$/, "").endsWith("/shop/confirmation");
    }

    wasShown() {
        try {
            return window.sessionStorage.getItem(this.storageKey) === "1";
        } catch {
            return false;
        }
    }

    markShown() {
        try {
            window.sessionStorage.setItem(this.storageKey, "1");
        } catch {
            return;
        }
    }

    get storageKey() {
        return `${CHECKOUT_TOAST_STORAGE_PREFIX}${window.location.pathname}${window.location.search}`;
    }

    showToast() {
        const toast = document.createElement("div");
        toast.className = "ab-storefront-action-toast ab-storefront-action-toast-cart";

        const media = document.createElement("span");
        media.className = "ab-storefront-action-toast-media ab-storefront-toast-logo-motion";
        const logoSrc = this.getWebsiteLogoSrc();
        if (logoSrc) {
            const image = document.createElement("img");
            image.src = logoSrc;
            image.alt = "";
            image.loading = "lazy";
            media.appendChild(image);
        } else {
            const iconWrap = document.createElement("span");
            iconWrap.className = "ab-storefront-action-toast-icon";
            const icon = document.createElement("i");
            icon.className = "fa fa-check";
            iconWrap.appendChild(icon);
            media.appendChild(iconWrap);
        }

        const copy = document.createElement("span");
        copy.className = "ab-storefront-action-toast-copy";
        const heading = document.createElement("strong");
        heading.textContent = _t("Checkout complete");
        const detail = document.createElement("small");
        detail.textContent = _t("Thank you for ordering from Abdin Pharmacies");
        copy.append(heading, detail);

        const check = document.createElement("span");
        check.className = "ab-storefront-action-toast-check";
        const checkIcon = document.createElement("i");
        checkIcon.className = "fa fa-check";
        check.appendChild(checkIcon);

        toast.append(media, copy, check);
        document.body.appendChild(toast);
        requestAnimationFrame(() => toast.classList.add("is-visible"));
        setTimeout(() => {
            toast.classList.remove("is-visible");
            setTimeout(() => toast.remove(), 260);
        }, 3200);
    }

    getWebsiteLogoSrc() {
        const logo = document.querySelector(".ab-storefront-brand-logo img, .ab-storefront-brand img");
        return logo?.currentSrc || logo?.src || "";
    }
}

registry
    .category("public.interactions")
    .add("ab_ecommerce_storefront.checkout_success_motion", AbStorefrontCheckoutSuccessMotion);
