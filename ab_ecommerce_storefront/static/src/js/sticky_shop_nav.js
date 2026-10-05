/** @odoo-module ignore **/
(function () {
    "use strict";

    const HEADER_SELECTOR = ".ab-storefront-header";
    const STUCK_CLASS = "is-stuck";
    const MORPHING_CLASS = "is-morphing";
    const HIDDEN_CLASS = "is-scroll-hidden";
    const STICKY_DISABLED_CLASS = "is-sticky-disabled";
    const STUCK_OFFSET = 18;
    const SCROLL_DELTA_THRESHOLD = 2;
    const SCROLL_UP_REVEAL_DISTANCE = 28;
    const MORPH_DURATION = 280;

    let header = null;
    let stickyShop = null;
    let ticking = false;
    let morphTimer = null;
    let transitionAnimations = [];
    let lastScrollY = 0;
    let upwardTravel = 0;

    function isCartPage() {
        const pathParts = window.location.pathname.replace(/\/+$/, "").split("/").filter(Boolean);
        return pathParts.slice(-2).join("/") === "shop/cart";
    }

    function setScrollHidden(nextHidden) {
        if (!header) {
            return;
        }
        header.classList.toggle(HIDDEN_CLASS, Boolean(nextHidden));
    }

    function captureLayout() {
        const nodes = [stickyShop, ...header.querySelectorAll(
            ".ab-storefront-brand, .ab-storefront-desktop-search, .ab-storefront-mobile-search-row, .ab-storefront-actions, .ab-storefront-category-nav, .ab-storefront-search"
        )];
        return new Map(nodes.map(node => [node, {
            rect: node.getBoundingClientRect(),
            opacity: Number(window.getComputedStyle(node).opacity),
            borderRadius: window.getComputedStyle(node).borderRadius,
        }]));
    }

    function setStuck(nextStuck) {
        if (!header || nextStuck === header.classList.contains(STUCK_CLASS)) {
            return;
        }
        const before = captureLayout();
        const wasHidden = header.classList.contains(HIDDEN_CLASS);
        window.clearTimeout(morphTimer);
        transitionAnimations.forEach(animation => animation.cancel());
        transitionAnimations = [];
        header.classList.toggle(STUCK_CLASS, nextStuck);
        header.classList.remove(MORPHING_CLASS);
        if (!nextStuck) {
            header.classList.remove(HIDDEN_CLASS);
        }
        const after = captureLayout();
        if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
            syncPlaceholderHeight();
            return;
        }
        header.classList.add(MORPHING_CLASS);
        const oldShop = before.get(stickyShop).rect;
        const newShop = after.get(stickyShop).rect;
        const options = { duration: MORPH_DURATION, easing: "cubic-bezier(.4, 0, .2, 1)" };
        const animate = (node, frames) => {
            transitionAnimations.push(node.animate(frames, options));
        };
        animate(stickyShop, [
            {
                width: `${oldShop.width}px`,
                maxWidth: `${oldShop.width}px`,
                height: `${oldShop.height}px`,
                transform: `translateY(${wasHidden ? -4 : oldShop.top - newShop.top}px)`,
                opacity: wasHidden ? 0 : before.get(stickyShop).opacity,
                borderRadius: before.get(stickyShop).borderRadius,
            },
            {
                width: `${newShop.width}px`,
                maxWidth: `${newShop.width}px`,
                height: `${newShop.height}px`,
                transform: "translateY(0)",
                opacity: after.get(stickyShop).opacity,
                borderRadius: after.get(stickyShop).borderRadius,
            },
        ]);
        for (const [node, current] of after) {
            if (node === stickyShop || !current.rect.width || !current.rect.height) {
                continue;
            }
            const previous = before.get(node);
            if (node.matches(".ab-storefront-search")) {
                if (previous.rect.width && previous.rect.height) {
                    animate(node, [{ width: `${previous.rect.width}px` }, { width: `${current.rect.width}px` }]);
                }
                continue;
            }
            if (!previous.rect.width || !previous.rect.height) {
                animate(node, [{ opacity: 0 }, { opacity: current.opacity }]);
                continue;
            }
            const deltaX = previous.rect.left - oldShop.left - (current.rect.left - newShop.left);
            const deltaY = previous.rect.top - oldShop.top - (current.rect.top - newShop.top);
            animate(node, [
                { transform: `translate(${deltaX}px, ${deltaY}px)` },
                { transform: "translate(0, 0)" },
            ]);
        }
        morphTimer = window.setTimeout(() => {
            transitionAnimations.forEach(animation => animation.cancel());
            transitionAnimations = [];
            header.classList.remove(MORPHING_CLASS);
            syncPlaceholderHeight();
        }, MORPH_DURATION);
    }

    function updateFromScroll() {
        ticking = false;
        syncPlaceholderHeight();

        const currentScrollY = Math.max(window.scrollY, 0);
        const scrollDelta = currentScrollY - lastScrollY;

        if (currentScrollY <= STUCK_OFFSET) {
            upwardTravel = 0;
            setStuck(false);
            lastScrollY = currentScrollY;
            return;
        }

        if (scrollDelta > SCROLL_DELTA_THRESHOLD) {
            upwardTravel = 0;
            setScrollHidden(true);
        }

        setStuck(true);

        if (scrollDelta < -SCROLL_DELTA_THRESHOLD) {
            upwardTravel += Math.abs(scrollDelta);
            if (upwardTravel >= SCROLL_UP_REVEAL_DISTANCE) {
                setScrollHidden(false);
            }
        }

        lastScrollY = currentScrollY;
    }

    function requestScrollUpdate() {
        if (ticking) {
            return;
        }
        ticking = true;
        window.requestAnimationFrame(updateFromScroll);
    }

    function start() {
        header = document.querySelector(HEADER_SELECTOR);
        if (!header) {
            return;
        }
        if (isCartPage()) {
            header.classList.add(STICKY_DISABLED_CLASS);
            header.classList.remove(STUCK_CLASS, MORPHING_CLASS, HIDDEN_CLASS);
            header.style.removeProperty("--ab-sticky-placeholder-height");
            return;
        }
        stickyShop = header.querySelector("[data-ab-sticky-shop]");
        lastScrollY = Math.max(window.scrollY, 0);
        syncPlaceholderHeight();
        updateFromScroll();
        window.addEventListener("scroll", requestScrollUpdate, { passive: true });
        window.addEventListener("resize", requestScrollUpdate, { passive: true });
    }

    function syncPlaceholderHeight() {
        if (!header || !stickyShop || (header.classList.contains(STUCK_CLASS) || header.classList.contains(MORPHING_CLASS))) {
            return;
        }
        header.style.setProperty("--ab-sticky-placeholder-height", `${header.offsetHeight}px`);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", start, { once: true });
    } else {
        start();
    }
}());

(function () {
    "use strict";

    class AbStorefrontNavigationScroll {
        constructor(element) {
            this.el = element;
            for (const [type, method] of [
                ["pointerdown", "onPointerDown"],
                ["pointermove", "onPointerMove"],
                ["pointerup", "onPointerEnd"],
                ["pointercancel", "onPointerEnd"],
                ["lostpointercapture", "onPointerEnd"],
            ]) {
                element.addEventListener(type, event => this[method](event));
            }
            element.addEventListener("dragstart", event => {
                if (this.canScroll()) {
                    event.preventDefault();
                }
            });
            element.addEventListener("click", event => this.onClick(event), true);
            element.addEventListener("wheel", event => this.onWheel(event), { passive: false });
        }

        canScroll() {
            return this.el.scrollWidth > this.el.clientWidth + 1 &&
                window.getComputedStyle(this.el).overflowX === "auto";
        }

        onPointerDown(event) {
            this.suppressClick = false;
            if (event.pointerType !== "mouse" || event.button !== 0 || !this.canScroll()) {
                return;
            }
            this.drag = {
                pointerId: event.pointerId,
                startX: event.clientX,
                scrollLeft: this.el.scrollLeft,
                active: false,
            };
        }

        onPointerMove(event) {
            if (!this.drag || this.drag.pointerId !== event.pointerId) {
                return;
            }
            const distance = event.clientX - this.drag.startX;
            if (!this.drag.active && Math.abs(distance) < 6) {
                return;
            }
            if (!this.drag.active) {
                this.drag.active = true;
                this.suppressClick = true;
                this.el.setPointerCapture(event.pointerId);
                this.el.classList.add("ab-storefront-nav-dragging");
            }
            event.preventDefault();
            this.el.scrollLeft = this.drag.scrollLeft - distance;
        }

        onPointerEnd(event) {
            if (!this.drag || this.drag.pointerId !== event.pointerId) {
                return;
            }
            this.drag = null;
            this.el.classList.remove("ab-storefront-nav-dragging");
            if (this.el.hasPointerCapture(event.pointerId)) {
                this.el.releasePointerCapture(event.pointerId);
            }
        }

        onClick(event) {
            if (this.suppressClick && event.detail > 0) {
                this.suppressClick = false;
                event.preventDefault();
                event.stopImmediatePropagation();
            }
        }

        onWheel(event) {
            if (event.ctrlKey || !this.canScroll()) {
                return;
            }
            const direction = window.getComputedStyle(this.el).direction === "rtl" ? -1 : 1;
            const delta = Math.abs(event.deltaX) > Math.abs(event.deltaY)
                ? event.deltaX : event.deltaY * direction;
            const scale = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? this.el.clientWidth : 1;
            const before = this.el.scrollLeft;
            this.el.scrollLeft += delta * scale;
            if (Math.abs(this.el.scrollLeft - before) > 0.5) {
                event.preventDefault();
            }
        }
    }

    function initializeNavigationScroll() {
        document.querySelectorAll(".ab-storefront-header .ab-storefront-primary-nav").forEach(element => {
            new AbStorefrontNavigationScroll(element);
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initializeNavigationScroll, { once: true });
    } else {
        initializeNavigationScroll();
    }
}());
