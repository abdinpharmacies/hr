/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Interaction } from "@web/public/interaction";

const DOUBLE_CLICK_DELAY = 430;
const LOADER_FALLBACK_DELAY = 4200;
const CHECKOUT_TOAST_STORAGE_PREFIX = "ab_storefront_checkout_success_toast:";

export class AbStorefrontPageLoader extends Interaction {
    static selector = "body";

    setup() {
        this.dismiss = this.dismiss.bind(this);
    }

    start() {
        if (document.body.classList.contains("editor_enable")) {
            return;
        }
        this.loaderEl = this.createLoader();
        if (!this.loaderEl) {
            return;
        }
        document.body.prepend(this.loaderEl);
        this.fallbackTimer = setTimeout(this.dismiss, LOADER_FALLBACK_DELAY);
        if (document.readyState === "complete") {
            requestAnimationFrame(this.dismiss);
            return;
        }
        window.addEventListener("load", this.dismiss, { once: true });
    }

    destroy() {
        clearTimeout(this.fallbackTimer);
        window.removeEventListener("load", this.dismiss);
    }

    dismiss() {
        clearTimeout(this.fallbackTimer);
        if (!this.loaderEl) {
            return;
        }
        this.loaderEl.classList.add("is-hiding");
        setTimeout(() => this.loaderEl?.remove(), 420);
    }

    createLoader() {
        const logoSrc = this.getWebsiteLogoSrc();
        if (!logoSrc) {
            return null;
        }
        const loader = document.createElement("div");
        loader.className = "ab-storefront-page-loader";
        loader.dataset.abStorefrontLoader = "true";
        loader.setAttribute("aria-hidden", "true");

        const logoWrap = document.createElement("span");
        logoWrap.className = "ab-storefront-loader-logo";

        const image = document.createElement("img");
        image.src = logoSrc;
        image.alt = "";
        image.width = 176;
        image.height = 58;
        image.loading = "eager";

        logoWrap.appendChild(image);
        loader.appendChild(logoWrap);
        return loader;
    }

    getWebsiteLogoSrc() {
        const logo = document.querySelector(".ab-storefront-brand-logo img, .ab-storefront-brand img");
        return logo?.currentSrc || logo?.src || "";
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
        const isArabic = document.documentElement.lang?.startsWith("ar") || document.documentElement.dir === "rtl";
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
        heading.textContent = isArabic ? "تم تأكيد الطلب" : "Checkout complete";
        const detail = document.createElement("small");
        detail.textContent = isArabic ? "شكرا لطلبك من صيدليات عبدين" : "Thank you for ordering from Abdin Pharmacies";
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
