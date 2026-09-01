/** @odoo-module **/

import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { Interaction } from "@web/public/interaction";
import { patch } from "@web/core/utils/patch";
import { CartService } from "@website_sale/js/cart_service";
import wishlistUtils from "@website_sale_wishlist/js/website_sale_wishlist_utils";

const MIN_VIEWPORT_WIDTH = 992;
const LENS_SIZE = 230;
const ZOOM_SCALE = 3.8;
const MOVE_EASE = 0.12;
const HERO_VIEWPORT_PADDING = 48;
const HERO_PAN_EASE = 0.16;
const CART_FLY_DURATION = 760;
const SCROLL_TOP_SHOW_OFFSET = 520;
const MOBILE_SEARCH_BREAKPOINT = 992;
const MOBILE_SEARCH_STORAGE_KEY = "ab_storefront_recent_searches";

patch(CartService.prototype, {
    _showCartNotification(props = {}, options = {}) {
        if (!document.body?.classList.contains("ab-storefront")) {
            return super._showCartNotification(props, options);
        }

        if (props.warning) {
            return super._showCartNotification(props, options);
        }

        if (props.lines?.length) {
            document.dispatchEvent(new CustomEvent("ab_storefront_cart_added", {
                detail: {
                    lines: props.lines,
                    currencyId: props.currency_id,
                    options,
                },
            }));
        }
    },
});

export class AbStorefrontProductImageZoom extends Interaction {
    static selector = "#product_detail";

    setup() {
        this.image = null;
        this.lens = null;
        this.frame = null;
        this.heroOverlay = null;
        this.heroImage = null;
        this.heroCloseButton = null;
        this.heroSource = null;
        this.heroZoomed = false;
        this.heroPanFrame = null;
        this.currentHeroPan = null;
        this.targetHeroPan = null;
        this.heroDragging = false;
        this.heroDragStart = null;
        this.heroPanOffset = { x: 0, y: 0 };
        this.suppressHeroClick = false;
        this.currentZoom = null;
        this.targetZoom = null;
        this.onPointerEnter = this.onPointerEnter.bind(this);
        this.onPointerMove = this.onPointerMove.bind(this);
        this.onPointerLeave = this.onPointerLeave.bind(this);
        this.onClick = this.onClick.bind(this);
        this.onKeydown = this.onKeydown.bind(this);
        this.animateZoom = this.animateZoom.bind(this);
        this.onHeroPointerDown = this.onHeroPointerDown.bind(this);
        this.onHeroPointerMove = this.onHeroPointerMove.bind(this);
        this.onHeroPointerUp = this.onHeroPointerUp.bind(this);
        this.animateHeroPan = this.animateHeroPan.bind(this);
    }

    start() {
        this.el.addEventListener("pointerenter", this.onPointerEnter, true);
        this.el.addEventListener("pointermove", this.onPointerMove, true);
        this.el.addEventListener("pointerleave", this.onPointerLeave, true);
        this.el.addEventListener("click", this.onClick, true);
        document.addEventListener("keydown", this.onKeydown);
    }

    destroy() {
        this.el.removeEventListener("pointerenter", this.onPointerEnter, true);
        this.el.removeEventListener("pointermove", this.onPointerMove, true);
        this.el.removeEventListener("pointerleave", this.onPointerLeave, true);
        this.el.removeEventListener("click", this.onClick, true);
        document.removeEventListener("keydown", this.onKeydown);
        if (this.frame) {
            cancelAnimationFrame(this.frame);
            this.frame = null;
        }
        if (this.heroPanFrame) {
            cancelAnimationFrame(this.heroPanFrame);
            this.heroPanFrame = null;
        }
        this.closeHeroImage({ immediate: true });
        this.hideZoom();
    }

    onPointerEnter(ev) {
        const image = this.getZoomImage(ev.target);
        if (!image || !this.canZoom(ev)) {
            return;
        }
        this.showZoom(image);
        this.updateZoom(ev);
    }

    onPointerMove(ev) {
        const image = this.getZoomImage(ev.target);
        if (!image || !this.canZoom(ev)) {
            this.hideZoom();
            return;
        }
        if (image !== this.image) {
            this.showZoom(image);
        }
        this.updateZoom(ev);
    }

    onPointerLeave(ev) {
        if (!ev.target.closest(".o_wsale_product_images")) {
            return;
        }
        this.hideZoom();
    }

    onClick(ev) {
        if (ev.button !== 0 || ev.metaKey || ev.ctrlKey || ev.shiftKey || ev.altKey) {
            return;
        }
        const quantityButton = ev.target.closest?.(".css_quantity_plus, .css_quantity_minus");
        if (quantityButton && this.el.contains(quantityButton)) {
            this.animateQuantityChange(quantityButton);
            return;
        }
        const image = this.getZoomImage(ev.target);
        if (!image) {
            return;
        }
        ev.preventDefault();
        ev.stopPropagation();
        this.openHeroImage(image);
    }

    onKeydown(ev) {
        if (ev.key === "Escape" && this.heroOverlay) {
            this.closeHeroImage();
        }
    }

    canZoom(ev) {
        return ev.pointerType === "mouse" && window.innerWidth >= MIN_VIEWPORT_WIDTH;
    }

    getZoomImage(target) {
        const image = target.closest?.(".product_detail_img");
        if (!image || !this.el.querySelector(".o_wsale_product_images")?.contains(image)) {
            return null;
        }
        if (image.tagName !== "IMG" || !image.currentSrc) {
            return null;
        }
        return image;
    }

    showZoom(image) {
        this.image = image;
        const wrapper = image.closest(".o_product_detail_img_wrapper") || image.parentElement;
        wrapper?.classList.add("ab-storefront-zoom-source");

        if (!this.lens) {
            this.lens = document.createElement("div");
            this.lens.className = "ab-storefront-zoom-lens";
        }
        if (wrapper && this.lens.parentElement !== wrapper) {
            wrapper.appendChild(this.lens);
        }

        this.lens.style.backgroundImage = `url("${this.getZoomSource(image)}")`;
        this.lens.classList.add("is-visible");
    }

    hideZoom() {
        this.el.querySelectorAll(".ab-storefront-zoom-source").forEach((source) => {
            source.classList.remove("ab-storefront-zoom-source");
        });
        this.image = null;
        this.targetZoom = null;
        this.currentZoom = null;
        if (this.frame) {
            cancelAnimationFrame(this.frame);
            this.frame = null;
        }
        this.lens?.classList.remove("is-visible");
    }

    updateZoom(ev) {
        if (!this.image || !this.lens) {
            return;
        }

        const rect = this.image.getBoundingClientRect();
        const x = Math.min(Math.max(ev.clientX - rect.left, 0), rect.width);
        const y = Math.min(Math.max(ev.clientY - rect.top, 0), rect.height);
        const lensSize = Math.min(LENS_SIZE, Math.max(130, Math.min(rect.width, rect.height) * 0.48));
        const bgWidth = rect.width * ZOOM_SCALE;
        const bgHeight = rect.height * ZOOM_SCALE;
        const bgX = Math.max(0, Math.min(bgWidth - lensSize, x * ZOOM_SCALE - lensSize / 2));
        const bgY = Math.max(0, Math.min(bgHeight - lensSize, y * ZOOM_SCALE - lensSize / 2));

        this.targetZoom = {
            left: x - lensSize / 2,
            top: y - lensSize / 2,
            bgX,
            bgY,
            lensSize,
            bgWidth,
            bgHeight,
        };
        if (!this.currentZoom) {
            this.currentZoom = { ...this.targetZoom };
            this.renderZoom(this.currentZoom);
        }
        if (!this.frame) {
            this.frame = requestAnimationFrame(this.animateZoom);
        }
    }

    animateZoom() {
        this.frame = null;
        if (!this.lens || !this.targetZoom || !this.currentZoom) {
            return;
        }

        for (const key of ["left", "top", "bgX", "bgY", "lensSize", "bgWidth", "bgHeight"]) {
            this.currentZoom[key] += (this.targetZoom[key] - this.currentZoom[key]) * MOVE_EASE;
        }
        this.renderZoom(this.currentZoom);

        const delta = Math.abs(this.targetZoom.left - this.currentZoom.left)
            + Math.abs(this.targetZoom.top - this.currentZoom.top)
            + Math.abs(this.targetZoom.bgX - this.currentZoom.bgX)
            + Math.abs(this.targetZoom.bgY - this.currentZoom.bgY);
        if (delta > 0.35) {
            this.frame = requestAnimationFrame(this.animateZoom);
        } else {
            this.currentZoom = { ...this.targetZoom };
            this.renderZoom(this.currentZoom);
        }
    }

    renderZoom(zoom) {
        this.lens.style.width = `${zoom.lensSize}px`;
        this.lens.style.height = `${zoom.lensSize}px`;
        this.lens.style.left = `${zoom.left}px`;
        this.lens.style.top = `${zoom.top}px`;
        this.lens.style.backgroundSize = `${zoom.bgWidth}px ${zoom.bgHeight}px`;
        this.lens.style.backgroundPosition = `-${zoom.bgX}px -${zoom.bgY}px`;
    }

    openHeroImage(image) {
        if (this.heroOverlay) {
            this.closeHeroImage({ immediate: true });
        }
        this.hideZoom();
        this.heroSource = image;
        const startRect = image.getBoundingClientRect();
        const targetRect = this.getHeroTargetRect(startRect);

        this.heroOverlay = document.createElement("div");
        this.heroOverlay.className = "ab-storefront-image-hero";
        this.heroOverlay.addEventListener("click", () => this.closeHeroImage());
        this.heroOverlay.addEventListener("pointermove", this.onHeroPointerMove);
        this.heroOverlay.addEventListener("pointerup", this.onHeroPointerUp);
        this.heroOverlay.addEventListener("pointercancel", this.onHeroPointerUp);

        this.heroCloseButton = document.createElement("button");
        this.heroCloseButton.className = "ab-storefront-image-hero-close";
        this.heroCloseButton.type = "button";
        this.heroCloseButton.setAttribute("aria-label", "Close image");
        this.heroCloseButton.innerHTML = "&times;";
        this.heroCloseButton.addEventListener("click", (ev) => {
            ev.stopPropagation();
            this.closeHeroImage();
        });

        this.heroImage = document.createElement("img");
        this.heroImage.className = "ab-storefront-image-hero-img";
        this.heroImage.src = image.currentSrc;
        this.heroImage.alt = image.alt || "";
        this.heroImage.addEventListener("click", (ev) => this.toggleHeroZoom(ev));
        this.heroImage.addEventListener("pointerdown", this.onHeroPointerDown);
        this.heroOverlay.appendChild(this.heroImage);
        this.heroOverlay.appendChild(this.heroCloseButton);
        document.body.appendChild(this.heroOverlay);
        document.body.classList.add("ab-storefront-image-hero-open");

        this.setHeroImageRect(startRect);
        image.classList.add("ab-storefront-image-hero-source-hidden");
        requestAnimationFrame(() => {
            this.heroOverlay?.classList.remove("is-closing");
            this.heroOverlay?.classList.add("is-visible");
            this.setHeroImageRect(targetRect);
        });
        this.preloadHeroImage(image);
    }

    closeHeroImage(options = {}) {
        if (!this.heroOverlay || !this.heroImage) {
            return;
        }
        const overlay = this.heroOverlay;
        const source = this.heroSource;
        let removed = false;
        const removeHero = () => {
            if (removed) {
                return;
            }
            removed = true;
            if (this.heroPanFrame) {
                cancelAnimationFrame(this.heroPanFrame);
                this.heroPanFrame = null;
            }
            overlay.remove();
            source?.classList.remove("ab-storefront-image-hero-source-hidden");
            if (this.heroOverlay === overlay) {
                this.heroOverlay = null;
                this.heroImage = null;
                this.heroCloseButton = null;
                this.heroSource = null;
                this.heroZoomed = false;
                this.currentHeroPan = null;
                this.targetHeroPan = null;
                this.heroDragging = false;
                this.heroDragStart = null;
                this.heroPanOffset = { x: 0, y: 0 };
                this.suppressHeroClick = false;
            }
            document.body.classList.remove("ab-storefront-image-hero-open");
        };
        if (options.immediate) {
            removeHero();
            return;
        }

        this.resetHeroZoom();
        const sourceRect = this.heroSource?.getBoundingClientRect();
        if (sourceRect?.width && sourceRect?.height) {
            this.setHeroImageRect(sourceRect);
        }
        overlay.classList.add("is-closing");
        requestAnimationFrame(() => overlay.classList.remove("is-visible"));
        setTimeout(removeHero, 980);
    }

    preloadHeroImage(source) {
        const heroSrc = this.getZoomSource(source);
        if (!heroSrc || heroSrc === source.currentSrc) {
            return;
        }
        const preload = new Image();
        preload.addEventListener("load", () => {
            if (this.heroImage && this.heroSource === source) {
                this.heroImage.src = heroSrc;
            }
        }, { once: true });
        preload.src = heroSrc;
    }

    toggleHeroZoom(ev) {
        ev.stopPropagation();
        if (this.suppressHeroClick) {
            this.suppressHeroClick = false;
            return;
        }
        if (!this.heroImage) {
            return;
        }
        if (this.heroZoomed) {
            this.resetHeroZoom();
            return;
        }

        const rect = this.heroImage.getBoundingClientRect();
        const xRatio = Math.min(Math.max((ev.clientX - rect.left) / rect.width, 0), 1);
        const yRatio = Math.min(Math.max((ev.clientY - rect.top) / rect.height, 0), 1);
        this.currentHeroPan = { x: xRatio * 100, y: yRatio * 100 };
        this.targetHeroPan = { ...this.currentHeroPan };
        this.renderHeroPan(this.currentHeroPan);
        this.heroPanOffset = { x: 0, y: 0 };
        this.renderHeroPanOffset(this.heroPanOffset);
        this.heroImage.classList.add("is-zoomed");
        this.heroZoomed = true;
    }

    onHeroPointerDown(ev) {
        if (!this.heroZoomed || !this.heroImage || ev.pointerType === "mouse") {
            return;
        }
        ev.preventDefault();
        ev.stopPropagation();
        this.heroDragging = true;
        this.suppressHeroClick = false;
        this.heroDragStart = {
            pointerId: ev.pointerId,
            x: ev.clientX,
            y: ev.clientY,
            panX: this.heroPanOffset.x,
            panY: this.heroPanOffset.y,
        };
        this.heroImage.setPointerCapture?.(ev.pointerId);
        this.heroImage.classList.add("is-panning");
    }

    onHeroPointerMove(ev) {
        if (this.heroDragging && this.heroImage && this.heroDragStart?.pointerId === ev.pointerId) {
            ev.preventDefault();
            ev.stopPropagation();
            const deltaX = ev.clientX - this.heroDragStart.x;
            const deltaY = ev.clientY - this.heroDragStart.y;
            if (Math.abs(deltaX) + Math.abs(deltaY) > 8) {
                this.suppressHeroClick = true;
            }
            this.heroPanOffset = this.constrainHeroPanOffset({
                x: this.heroDragStart.panX + deltaX,
                y: this.heroDragStart.panY + deltaY,
            });
            this.renderHeroPanOffset(this.heroPanOffset);
            return;
        }
        if (!this.heroZoomed || !this.heroImage || ev.pointerType !== "mouse") {
            return;
        }

        const rect = this.getHeroImageBaseRect();
        if (!rect.width || !rect.height) {
            return;
        }
        const xRatio = Math.min(Math.max((ev.clientX - rect.left) / rect.width, 0), 1);
        const yRatio = Math.min(Math.max((ev.clientY - rect.top) / rect.height, 0), 1);
        this.targetHeroPan = { x: xRatio * 100, y: yRatio * 100 };
        if (!this.currentHeroPan) {
            this.currentHeroPan = { ...this.targetHeroPan };
            this.renderHeroPan(this.currentHeroPan);
        }
        if (!this.heroPanFrame) {
            this.heroPanFrame = requestAnimationFrame(this.animateHeroPan);
        }
    }

    onHeroPointerUp(ev) {
        if (!this.heroDragging || this.heroDragStart?.pointerId !== ev.pointerId) {
            return;
        }
        ev.preventDefault();
        ev.stopPropagation();
        this.heroDragging = false;
        this.heroDragStart = null;
        this.heroImage?.releasePointerCapture?.(ev.pointerId);
        this.heroImage?.classList.remove("is-panning");
    }

    animateHeroPan() {
        this.heroPanFrame = null;
        if (!this.heroImage || !this.heroZoomed || !this.currentHeroPan || !this.targetHeroPan) {
            return;
        }

        this.currentHeroPan.x += (this.targetHeroPan.x - this.currentHeroPan.x) * HERO_PAN_EASE;
        this.currentHeroPan.y += (this.targetHeroPan.y - this.currentHeroPan.y) * HERO_PAN_EASE;
        this.renderHeroPan(this.currentHeroPan);

        const delta = Math.abs(this.targetHeroPan.x - this.currentHeroPan.x)
            + Math.abs(this.targetHeroPan.y - this.currentHeroPan.y);
        if (delta > 0.12) {
            this.heroPanFrame = requestAnimationFrame(this.animateHeroPan);
        } else {
            this.currentHeroPan = { ...this.targetHeroPan };
            this.renderHeroPan(this.currentHeroPan);
        }
    }

    renderHeroPan(pan) {
        if (!this.heroImage) {
            return;
        }
        this.heroImage.style.transformOrigin = `${pan.x}% ${pan.y}%`;
    }

    constrainHeroPanOffset(offset) {
        const rect = this.getHeroImageBaseRect();
        const scale = 2.15;
        const maxX = Math.max(0, (rect.width * (scale - 1)) / 2);
        const maxY = Math.max(0, (rect.height * (scale - 1)) / 2);
        return {
            x: Math.min(Math.max(offset.x, -maxX), maxX),
            y: Math.min(Math.max(offset.y, -maxY), maxY),
        };
    }

    renderHeroPanOffset(offset) {
        if (!this.heroImage) {
            return;
        }
        this.heroImage.style.setProperty("--ab-hero-pan-x", `${offset.x}px`);
        this.heroImage.style.setProperty("--ab-hero-pan-y", `${offset.y}px`);
    }

    resetHeroZoom() {
        if (!this.heroImage) {
            return;
        }
        if (this.heroPanFrame) {
            cancelAnimationFrame(this.heroPanFrame);
            this.heroPanFrame = null;
        }
        this.heroImage.classList.remove("is-zoomed");
        this.heroImage.style.transformOrigin = "center center";
        this.heroImage.classList.remove("is-panning");
        this.heroPanOffset = { x: 0, y: 0 };
        this.renderHeroPanOffset(this.heroPanOffset);
        this.heroZoomed = false;
        this.heroDragging = false;
        this.heroDragStart = null;
        this.currentHeroPan = null;
        this.targetHeroPan = null;
    }

    setHeroImageRect(rect) {
        if (!this.heroImage) {
            return;
        }
        Object.assign(this.heroImage.style, {
            width: `${rect.width}px`,
            height: `${rect.height}px`,
            left: `${rect.left}px`,
            top: `${rect.top}px`,
        });
    }

    getHeroTargetRect(sourceRect) {
        const maxWidth = window.innerWidth - HERO_VIEWPORT_PADDING * 2;
        const maxHeight = window.innerHeight - HERO_VIEWPORT_PADDING * 2;
        const scale = Math.min(maxWidth / sourceRect.width, maxHeight / sourceRect.height, 1.7);
        const width = sourceRect.width * scale;
        const height = sourceRect.height * scale;
        return {
            width,
            height,
            left: (window.innerWidth - width) / 2,
            top: (window.innerHeight - height) / 2,
        };
    }

    getHeroImageBaseRect() {
        if (!this.heroImage) {
            return { width: 0, height: 0, left: 0, top: 0 };
        }
        return {
            width: parseFloat(this.heroImage.style.width) || 0,
            height: parseFloat(this.heroImage.style.height) || 0,
            left: parseFloat(this.heroImage.style.left) || 0,
            top: parseFloat(this.heroImage.style.top) || 0,
        };
    }

    animateQuantityChange(button) {
        const quantity = button.closest(".css_quantity")?.querySelector(".quantity");
        if (!quantity) {
            return;
        }
        const previousValue = this.getQuantityNumber(quantity);
        const isIncrease = button.classList.contains("css_quantity_plus");
        setTimeout(() => {
            const nextValue = this.getQuantityNumber(quantity);
            const className = this.isQuantityBlocked(quantity, button, previousValue, nextValue)
                ? "ab-storefront-quantity-shake"
                : isIncrease
                    ? "ab-storefront-quantity-slide-next"
                    : "ab-storefront-quantity-slide-prev";
            quantity.classList.remove(
                "ab-storefront-quantity-slide-next",
                "ab-storefront-quantity-slide-prev",
                "ab-storefront-quantity-shake"
            );
            void quantity.offsetWidth;
            quantity.classList.add(className);
        }, 80);
    }

    getQuantityNumber(quantity) {
        const value = parseFloat(quantity.value);
        return Number.isFinite(value) ? value : 0;
    }

    getQuantityLimit(quantity, name, fallback) {
        const rawValue = quantity.dataset[name] ?? quantity.getAttribute(name);
        const value = parseFloat(rawValue);
        return Number.isFinite(value) ? value : fallback;
    }

    isQuantityBlocked(quantity, button, previousValue, nextValue) {
        if (button.classList.contains("disabled") || button.getAttribute("aria-disabled") === "true") {
            return true;
        }
        if (button.classList.contains("css_quantity_minus")) {
            const minValue = this.getQuantityLimit(quantity, "min", 1);
            return previousValue <= minValue && nextValue <= minValue;
        }
        const maxValue = this.getQuantityLimit(quantity, "max", Infinity);
        if (previousValue >= maxValue && nextValue >= maxValue) {
            return true;
        }
        return nextValue === previousValue;
    }

    getZoomSource(image) {
        return image.currentSrc.replace(/\/image_(?:\d+|1024|512|256|128)(?=\/|$|\?)/, "/image_1920");
    }
}

registry
    .category("public.interactions")
    .add("ab_ecommerce_storefront.product_image_zoom", AbStorefrontProductImageZoom);

export class AbStorefrontScrollToTop extends Interaction {
    static selector = "body.ab-storefront";

    setup() {
        this.onScroll = this.onScroll.bind(this);
        this.onClick = this.onClick.bind(this);
    }

    start() {
        this.button = document.createElement("button");
        this.button.type = "button";
        this.button.className = "ab-storefront-scroll-top";
        this.button.setAttribute("aria-label", "العودة إلى أعلى الصفحة");
        this.button.setAttribute("title", "العودة إلى أعلى الصفحة");
        this.button.innerHTML = '<i class="fa fa-chevron-up" aria-hidden="true"></i>';
        document.body.appendChild(this.button);

        this.button.addEventListener("click", this.onClick);
        window.addEventListener("scroll", this.onScroll, { passive: true });
        this.onScroll();
    }

    destroy() {
        window.removeEventListener("scroll", this.onScroll);
        this.button?.removeEventListener("click", this.onClick);
        this.button?.remove();
    }

    onScroll() {
        this.button?.classList.toggle("is-visible", window.scrollY > SCROLL_TOP_SHOW_OFFSET);
    }

    onClick() {
        const prefersReducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches;
        window.scrollTo({
            top: 0,
            behavior: prefersReducedMotion ? "auto" : "smooth",
        });
    }
}

registry
    .category("public.interactions")
    .add("ab_ecommerce_storefront.scroll_to_top", AbStorefrontScrollToTop);

export class AbStorefrontOffersNavState extends Interaction {
    static selector = "body.ab-storefront";

    setup() {
        this.syncState = this.syncState.bind(this);
    }

    start() {
        window.addEventListener("hashchange", this.syncState);
        this.syncState();
    }

    destroy() {
        window.removeEventListener("hashchange", this.syncState);
    }

    syncState() {
        const offersActive = window.location.hash === "#ab-storefront-offers";
        const normalizedPath = window.location.pathname.replace(/\/$/, "") || "/";
        const homeActive = (normalizedPath === "/" || normalizedPath === "/ar") && !offersActive;

        this.el
            .querySelectorAll(".ab-storefront-offers-link, .ab-storefront-mobile-offers-link")
            .forEach((link) => {
                link.classList.toggle("active", offersActive);
                if (offersActive) {
                    link.setAttribute("aria-current", "page");
                } else {
                    link.removeAttribute("aria-current");
                }
            });

        this.el
            .querySelectorAll(".ab-storefront-home-link, .ab-storefront-mobile-secondary-link")
            .forEach((link) => {
                link.classList.toggle("active", homeActive);
            });
    }
}

registry
    .category("public.interactions")
    .add("ab_ecommerce_storefront.offers_nav_state", AbStorefrontOffersNavState);

export class AbStorefrontMobileSearch extends Interaction {
    static selector = "body.ab-storefront";

    setup() {
        this.panel = null;
        this.sourceInput = null;
        this.searchInput = null;
        this.recentSection = null;
        this.recentList = null;
        this.lastFocus = null;
        this.onOpenRequest = this.onOpenRequest.bind(this);
        this.onClose = this.onClose.bind(this);
        this.onKeydown = this.onKeydown.bind(this);
        this.onSubmit = this.onSubmit.bind(this);
        this.onRecentClick = this.onRecentClick.bind(this);
    }

    start() {
        this.panel = this.el.querySelector("[data-ab-mobile-search-panel]");
        this.sourceInput = this.el.querySelector(
            ".ab-storefront-search-wrap.d-lg-none .ab-storefront-search input[name='search']"
        );
        this.searchInput = this.panel?.querySelector("[data-ab-mobile-search-input]");
        this.recentSection = this.panel?.querySelector("[data-ab-mobile-recent-section]");
        this.recentList = this.panel?.querySelector("[data-ab-mobile-recent-list]");
        if (!this.panel || !this.sourceInput || !this.searchInput) {
            return;
        }

        this.sourceInput.addEventListener("focus", this.onOpenRequest);
        this.sourceInput.addEventListener("pointerdown", this.onOpenRequest);
        this.panel.querySelector("[data-ab-mobile-search-close]")?.addEventListener("click", this.onClose);
        this.panel.querySelector("[data-ab-mobile-search-form]")?.addEventListener("submit", this.onSubmit);
        this.recentList?.addEventListener("click", this.onRecentClick);
        document.addEventListener("keydown", this.onKeydown);
        this.renderRecentSearches();
    }

    destroy() {
        this.sourceInput?.removeEventListener("focus", this.onOpenRequest);
        this.sourceInput?.removeEventListener("pointerdown", this.onOpenRequest);
        this.panel?.querySelector("[data-ab-mobile-search-close]")?.removeEventListener("click", this.onClose);
        this.panel?.querySelector("[data-ab-mobile-search-form]")?.removeEventListener("submit", this.onSubmit);
        this.recentList?.removeEventListener("click", this.onRecentClick);
        document.removeEventListener("keydown", this.onKeydown);
        document.body.classList.remove("ab-storefront-mobile-search-open");
    }

    onOpenRequest(ev) {
        if (!window.matchMedia(`(max-width: ${MOBILE_SEARCH_BREAKPOINT - 0.02}px)`).matches) {
            return;
        }
        ev.preventDefault();
        this.open();
    }

    open() {
        this.lastFocus = document.activeElement;
        this.searchInput.value = this.sourceInput.value || "";
        this.panel.classList.add("is-open");
        this.panel.setAttribute("aria-hidden", "false");
        document.body.classList.add("ab-storefront-mobile-search-open");
        this.renderRecentSearches();
        requestAnimationFrame(() => this.searchInput.focus({ preventScroll: true }));
    }

    onClose() {
        this.close();
    }

    close() {
        this.panel?.classList.remove("is-open");
        this.panel?.setAttribute("aria-hidden", "true");
        document.body.classList.remove("ab-storefront-mobile-search-open");
        if (this.lastFocus && document.contains(this.lastFocus)) {
            this.lastFocus.focus({ preventScroll: true });
        }
    }

    onKeydown(ev) {
        if (ev.key === "Escape" && this.panel?.classList.contains("is-open")) {
            ev.preventDefault();
            this.close();
        }
    }

    onSubmit(ev) {
        const query = this.searchInput.value.trim();
        if (!query) {
            ev.preventDefault();
            return;
        }
        this.storeRecentSearch(query);
    }

    onRecentClick(ev) {
        const button = ev.target.closest("[data-ab-mobile-recent-query]");
        if (!button) {
            return;
        }
        this.searchInput.value = button.dataset.abMobileRecentQuery || "";
        this.panel.querySelector("[data-ab-mobile-search-form]")?.requestSubmit();
    }

    getRecentSearches() {
        try {
            const searches = JSON.parse(localStorage.getItem(MOBILE_SEARCH_STORAGE_KEY) || "[]");
            return Array.isArray(searches) ? searches.filter(Boolean).slice(0, 5) : [];
        } catch {
            return [];
        }
    }

    storeRecentSearch(query) {
        const nextSearches = [
            query,
            ...this.getRecentSearches().filter((item) => item.toLowerCase() !== query.toLowerCase()),
        ].slice(0, 5);
        localStorage.setItem(MOBILE_SEARCH_STORAGE_KEY, JSON.stringify(nextSearches));
    }

    renderRecentSearches() {
        if (!this.recentSection || !this.recentList) {
            return;
        }
        const searches = this.getRecentSearches();
        this.recentSection.classList.toggle("d-none", !searches.length);
        this.recentList.replaceChildren(...searches.map((query) => this.createRecentItem(query)));
    }

    createRecentItem(query) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "ab-storefront-mobile-search-recent-item";
        button.dataset.abMobileRecentQuery = query;
        button.innerHTML = `
            <i class="fa fa-search" aria-hidden="true"></i>
            <span>${this.escapeHTML(query)}</span>
            <i class="fa fa-angle-left" aria-hidden="true"></i>
        `;
        return button;
    }

    escapeHTML(value) {
        const span = document.createElement("span");
        span.textContent = value;
        return span.innerHTML;
    }
}

registry
    .category("public.interactions")
    .add("ab_ecommerce_storefront.mobile_search", AbStorefrontMobileSearch);

export class AbStorefrontWishlistToggle extends Interaction {
    static selector = "body";

    setup() {
        this.observer = null;
        this.onClick = this.onClick.bind(this);
    }

    start() {
        this.el.addEventListener("click", this.onClick, true);
        this.enableWishlistedButtons();
        this.observer = new MutationObserver(() => this.enableWishlistedButtons());
        this.observer.observe(this.el, {
            attributes: true,
            attributeFilter: ["class", "disabled"],
            subtree: true,
        });
    }

    destroy() {
        this.el.removeEventListener("click", this.onClick, true);
        this.observer?.disconnect();
        this.observer = null;
    }

    async onClick(ev) {
        if (ev.button !== 0 || ev.metaKey || ev.ctrlKey || ev.shiftKey || ev.altKey) {
            return;
        }
        const button = ev.target.closest?.(".o_add_wishlist, .o_add_wishlist_dyn, [data-action='o_wishlist']");
        if (!button || !this.el.contains(button)) {
            return;
        }
        const productId = parseInt(button.dataset.productProductId);
        if (!productId || !this.isWishlisted(button, productId)) {
            return;
        }

        ev.preventDefault();
        ev.stopImmediatePropagation();

        const wishId = await this.waitFor(this.getWishId(productId));
        if (!wishId) {
            this.updateProductButtons(productId, true);
            return;
        }
        await this.waitFor(rpc(`/shop/wishlist/remove/${wishId}`));
        if (button.closest(".wishlist-section")) {
            const article = button.closest("article");
            if (article) {
                article.style.display = "none";
            }
        }
        wishlistUtils.removeWishlistProduct(productId);
        wishlistUtils.updateWishlistNavBar();
        this.updateProductButtons(productId, false);
    }

    async getWishId(productId) {
        const response = await fetch("/shop/wishlist", {
            credentials: "same-origin",
            headers: { "X-Requested-With": "XMLHttpRequest" },
        });
        if (!response.ok) {
            return null;
        }
        const html = await response.text();
        const doc = new DOMParser().parseFromString(html, "text/html");
        const item = doc.querySelector(`article[data-product-id="${productId}"][data-wish-id]`);
        if (!item?.dataset.wishId) {
            return null;
        }
        const wishId = parseInt(item.dataset.wishId);
        if (!Number.isFinite(wishId)) {
            return null;
        }
        return wishId;
    }

    isWishlisted(button, productId) {
        return button.classList.contains("o_in_wishlist")
            || wishlistUtils.getWishlistProductIds().includes(productId);
    }

    enableWishlistedButtons() {
        const productIds = wishlistUtils.getWishlistProductIds();
        this.el.querySelectorAll(".o_add_wishlist, .o_add_wishlist_dyn, [data-action='o_wishlist']").forEach((button) => {
            const productId = parseInt(button.dataset.productProductId);
            const isWishlisted = button.classList.contains("o_in_wishlist") || productIds.includes(productId);
            if (!isWishlisted) {
                return;
            }
            this.updateProductButton(button, true);
        });
    }

    updateProductButtons(productId, isWishlisted) {
        this.el.querySelectorAll(`[data-product-product-id="${productId}"]`).forEach((button) => {
            if (!button.matches(".o_add_wishlist, .o_add_wishlist_dyn, [data-action='o_wishlist']")) {
                return;
            }
            this.updateProductButton(button, isWishlisted);
        });
    }

    updateProductButton(button, isWishlisted) {
        wishlistUtils.updateDisabled(button, false);
        button.classList.toggle("o_in_wishlist", isWishlisted);
        button.removeAttribute("disabled");
        button.removeAttribute("aria-disabled");
        button.title = this.getWishlistTitle(isWishlisted);
        const icon = button.querySelector(".fa");
        icon?.classList.toggle("fa-heart", isWishlisted);
        icon?.classList.toggle("fa-heart-o", !isWishlisted);
    }

    getWishlistTitle(isWishlisted) {
        const isArabic = document.documentElement.lang?.startsWith("ar") || document.documentElement.dir === "rtl";
        if (isWishlisted) {
            return isArabic ? "إزالة من المفضلة" : "Remove from wishlist";
        }
        return isArabic ? "إضافة إلى المفضلة" : "Add to wishlist";
    }
}

registry
    .category("public.interactions")
    .add("ab_ecommerce_storefront.wishlist_toggle", AbStorefrontWishlistToggle);

export class AbStorefrontAddToCartFly extends Interaction {
    static selector = "body";

    setup() {
        this.onClick = this.onClick.bind(this);
        this.onPointerDown = this.onPointerDown.bind(this);
        this.onPointerUp = this.onPointerUp.bind(this);
        this.onCartAdded = this.onCartAdded.bind(this);
        this.pendingCartContext = null;
    }

    start() {
        this.el.addEventListener("pointerdown", this.onPointerDown, true);
        this.el.addEventListener("pointerup", this.onPointerUp, true);
        this.el.addEventListener("pointercancel", this.onPointerUp, true);
        this.el.addEventListener("pointerleave", this.onPointerUp, true);
        this.el.addEventListener("click", this.onClick, true);
        document.addEventListener("ab_storefront_cart_added", this.onCartAdded);
    }

    destroy() {
        this.el.removeEventListener("pointerdown", this.onPointerDown, true);
        this.el.removeEventListener("pointerup", this.onPointerUp, true);
        this.el.removeEventListener("pointercancel", this.onPointerUp, true);
        this.el.removeEventListener("pointerleave", this.onPointerUp, true);
        this.el.removeEventListener("click", this.onClick, true);
        document.removeEventListener("ab_storefront_cart_added", this.onCartAdded);
        this.pendingCartContext = null;
    }

    onPointerDown(ev) {
        const button = this.getActionButton(ev.target);
        if (!button) {
            return;
        }
        button.classList.add("ab-storefront-addcart-press");
    }

    onPointerUp(ev) {
        const button = this.getActionButton(ev.target);
        if (!button) {
            return;
        }
        button.classList.remove("ab-storefront-addcart-press");
    }

    onClick(ev) {
        if (ev.button !== 0 || ev.metaKey || ev.ctrlKey || ev.shiftKey || ev.altKey) {
            return;
        }
        const button = this.getActionButton(ev.target);
        if (!button) {
            return;
        }

        const action = this.getActionType(button);
        const image = this.getProductImage(button);
        const target = action === "wishlist" ? this.getWishlistTarget() : this.getCartTarget();

        if (action === "cart") {
            this.pendingCartContext = {
                button,
                image,
                target,
                title: this.getProductName(button),
            };
            return;
        }

        this.showButtonSuccess(button);
        this.showToast({
            image,
            title: this.getProductName(button),
            action,
        });
        if (image && target) {
            this.flyImageToTarget(image, target);
        } else if (target) {
            this.bounceTarget(target);
        }
    }

    onCartAdded(ev) {
        const context = this.pendingCartContext || {};
        this.pendingCartContext = null;
        const line = ev.detail?.lines?.find((item) => !item.linked_line_id) || ev.detail?.lines?.[0] || {};
        const image = context.image || null;
        const target = context.target || this.getCartTarget();

        if (context.button) {
            this.showButtonSuccess(context.button);
        }

        this.showToast({
            image,
            imageSrc: line.image_url,
            title: context.title || line.name,
            action: "cart",
        });

        if (image && target) {
            this.flyImageToTarget(image, target);
        } else if (target) {
            this.bounceTarget(target);
        }
    }

    getActionButton(target) {
        const button = target.closest?.(
            "#add_to_cart, .o_wsale_product_btn_primary.a-submit, .o_add_wishlist, .o_add_wishlist_dyn, [data-action='o_wishlist']"
        );
        if (!button || !this.el.contains(button) || button.disabled || button.classList.contains("disabled")) {
            return null;
        }
        return button;
    }

    getActionType(button) {
        return button.matches(".o_add_wishlist, .o_add_wishlist_dyn, [data-action='o_wishlist']")
            ? "wishlist"
            : "cart";
    }

    getProductImage(button) {
        const productCard = button.closest(".oe_product_cart, .ab-storefront-product-card");
        const cardImage = productCard?.querySelector(".ab-storefront-product-media img, .oe_product_image img");
        if (cardImage?.currentSrc && this.hasVisibleRect(cardImage)) {
            return cardImage;
        }

        const detail = button.closest("#product_detail") || document.querySelector("#product_detail");
        const detailImage = detail?.querySelector(".product_detail_img");
        if (detailImage?.currentSrc && this.hasVisibleRect(detailImage)) {
            return detailImage;
        }
        return null;
    }

    getCartTarget() {
        const targets = [
            ...document.querySelectorAll(".o_wsale_my_cart .ab-storefront-action, .o_wsale_my_cart a"),
        ];
        return targets.find((target) => this.hasVisibleRect(target)) || null;
    }

    getWishlistTarget() {
        const targets = [
            ...document.querySelectorAll(".o_wsale_my_wish .ab-storefront-action, .o_wsale_my_wish a"),
        ];
        return targets.find((target) => this.hasVisibleRect(target)) || null;
    }

    hasVisibleRect(element) {
        const rect = element.getBoundingClientRect();
        const style = window.getComputedStyle(element);
        return rect.width > 0 && rect.height > 0 && style.visibility !== "hidden" && style.display !== "none";
    }

    flyImageToTarget(image, targetElement) {
        const start = image.getBoundingClientRect();
        const target = targetElement.getBoundingClientRect();
        const flyer = image.cloneNode(false);
        const endSize = Math.max(26, Math.min(46, Math.min(start.width, start.height) * 0.24));
        const startCenterX = start.left + start.width / 2;
        const startCenterY = start.top + start.height / 2;
        const endX = target.left + target.width / 2 - startCenterX;
        const endY = target.top + target.height / 2 - startCenterY;
        const liftY = Math.min(-90, endY * 0.28 - 70);

        flyer.className = "ab-storefront-cart-flyer";
        flyer.alt = "";
        Object.assign(flyer.style, {
            left: `${start.left}px`,
            top: `${start.top}px`,
            width: `${start.width}px`,
            height: `${start.height}px`,
        });
        document.body.appendChild(flyer);

        const animation = flyer.animate([
            {
                opacity: 1,
                transform: "translate3d(0, 0, 0) scale(1)",
                offset: 0,
            },
            {
                opacity: .96,
                transform: `translate3d(${endX * .34}px, ${liftY}px, 0) scale(.72) rotate(-2deg)`,
                offset: .38,
            },
            {
                opacity: .92,
                transform: `translate3d(${endX * .78}px, ${endY * .74}px, 0) scale(.34) rotate(3deg)`,
                offset: .78,
            },
            {
                opacity: 0,
                transform: `translate3d(${endX}px, ${endY}px, 0) scale(${endSize / Math.max(start.width, start.height)}) rotate(0deg)`,
                offset: 1,
            },
        ], {
            duration: CART_FLY_DURATION,
            easing: "cubic-bezier(.16, 1, .3, 1)",
            fill: "forwards",
        });

        animation.addEventListener("finish", () => {
            flyer.remove();
            this.bounceTarget(targetElement);
        }, { once: true });
        animation.addEventListener("cancel", () => flyer.remove(), { once: true });
    }

    bounceTarget(target) {
        target.classList.remove("ab-storefront-cart-bounce");
        void target.offsetWidth;
        target.classList.add("ab-storefront-cart-bounce");
        setTimeout(() => target.classList.remove("ab-storefront-cart-bounce"), 620);
    }

    showButtonSuccess(button) {
        button.classList.remove("ab-storefront-addcart-press", "ab-storefront-addcart-success");
        void button.offsetWidth;
        button.classList.add("ab-storefront-addcart-success");
        setTimeout(() => button.classList.remove("ab-storefront-addcart-success"), 820);
    }

    showToast({ image, imageSrc, title, action }) {
        const toast = document.createElement("div");
        toast.className = `ab-storefront-action-toast ab-storefront-action-toast-${action}`;

        const isArabic = document.documentElement.lang?.startsWith("ar") || document.documentElement.dir === "rtl";
        const labels = {
            cart: isArabic ? "تمت الإضافة إلى السلة" : "Added to cart",
            wishlist: isArabic ? "تمت الإضافة إلى المفضلة" : "Added to wishlist",
            fallback: isArabic ? "تم حفظ المنتج" : "Product saved",
        };

        const media = document.createElement("span");
        media.className = "ab-storefront-action-toast-media ab-storefront-toast-logo-motion";
        const logoSrc = this.getWebsiteLogoSrc();
        if (logoSrc || imageSrc || image?.currentSrc) {
            const toastImage = document.createElement("img");
            toastImage.src = logoSrc || imageSrc || image.currentSrc;
            toastImage.alt = "";
            toastImage.loading = "lazy";
            media.appendChild(toastImage);
        } else {
            const iconWrap = document.createElement("span");
            iconWrap.className = "ab-storefront-action-toast-icon";
            const icon = document.createElement("i");
            icon.className = `fa ${action === "wishlist" ? "fa-heart" : "fa-shopping-cart"}`;
            iconWrap.appendChild(icon);
            media.appendChild(iconWrap);
        }

        const copy = document.createElement("span");
        copy.className = "ab-storefront-action-toast-copy";
        const heading = document.createElement("strong");
        heading.textContent = labels[action] || labels.cart;
        const detail = document.createElement("small");
        detail.textContent = title || labels.fallback;
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
        }, 2400);
    }

    getWebsiteLogoSrc() {
        const logo = document.querySelector(".ab-storefront-brand-logo img, .ab-storefront-brand img");
        return logo?.currentSrc || logo?.src || "";
    }

    getProductName(button) {
        const productCard = button.closest(".oe_product_cart, .ab-storefront-product-card");
        const cardName = productCard?.querySelector(
            ".o_wsale_products_item_title, .ab-storefront-product-name, [aria-label]"
        );
        const detailName = document.querySelector("#product_detail .ab-storefront-product-title, #product_detail h1");
        return cardName?.textContent?.trim() || detailName?.textContent?.trim() || "";
    }
}

registry
    .category("public.interactions")
    .add("ab_ecommerce_storefront.add_to_cart_fly", AbStorefrontAddToCartFly);
