/** @odoo-module ignore **/
(function () {
    "use strict";

    const HEADER_SELECTOR = ".ab-storefront-header";
    const STUCK_CLASS = "is-stuck";
    const UNSTICKING_CLASS = "is-unsticking";
    const MORPHING_CLASS = "is-morphing";
    const HIDDEN_CLASS = "is-scroll-hidden";
    const STICKY_DISABLED_CLASS = "is-sticky-disabled";
    const STUCK_OFFSET = 18;
    const SCROLL_DELTA_THRESHOLD = 2;
    const SCROLL_UP_REVEAL_DISTANCE = 28;
    const MORPH_DURATION = 420;

    let header = null;
    let stickyShop = null;
    let ticking = false;
    let morphTimer = null;
    let unstickTimer = null;
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

    function setStuck(nextStuck) {
        if (!header) {
            return;
        }
        const currentStuck = header.classList.contains(STUCK_CLASS);
        if (nextStuck === currentStuck && !header.classList.contains(UNSTICKING_CLASS)) {
            return;
        }
        window.clearTimeout(morphTimer);
        window.clearTimeout(unstickTimer);
        if (nextStuck) {
            header.classList.remove(UNSTICKING_CLASS);
            header.classList.add(STUCK_CLASS, MORPHING_CLASS);
            morphTimer = window.setTimeout(() => header.classList.remove(MORPHING_CLASS), MORPH_DURATION);
            return;
        }
        if (currentStuck) {
            header.classList.add(UNSTICKING_CLASS);
            unstickTimer = window.setTimeout(() => {
                header.classList.remove(STUCK_CLASS, UNSTICKING_CLASS, MORPHING_CLASS, HIDDEN_CLASS);
            }, MORPH_DURATION);
        }
    }

    function updateFromScroll() {
        ticking = false;
        syncPlaceholderHeight();

        const currentScrollY = Math.max(window.scrollY, 0);
        const scrollDelta = currentScrollY - lastScrollY;

        if (currentScrollY <= STUCK_OFFSET) {
            upwardTravel = 0;
            setScrollHidden(false);
            setStuck(false);
            lastScrollY = currentScrollY;
            return;
        }

        setStuck(true);

        if (scrollDelta > SCROLL_DELTA_THRESHOLD) {
            upwardTravel = 0;
            setScrollHidden(true);
        } else if (scrollDelta < -SCROLL_DELTA_THRESHOLD) {
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
            header.classList.remove(STUCK_CLASS, UNSTICKING_CLASS, MORPHING_CLASS, HIDDEN_CLASS);
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
        if (!header || !stickyShop) {
            return;
        }
        header.style.setProperty("--ab-sticky-placeholder-height", `${stickyShop.offsetHeight}px`);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", start, { once: true });
    } else {
        start();
    }
}());
