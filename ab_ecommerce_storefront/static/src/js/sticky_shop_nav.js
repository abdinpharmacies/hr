/** @odoo-module ignore **/
(function () {
    "use strict";

    const HEADER_SELECTOR = ".ab-storefront-header";
    const STUCK_CLASS = "is-stuck";
    const UNSTICKING_CLASS = "is-unsticking";
    const MORPHING_CLASS = "is-morphing";
    const STUCK_OFFSET = 18;
    const MORPH_DURATION = 420;

    let header = null;
    let stickyShop = null;
    let ticking = false;
    let morphTimer = null;
    let unstickTimer = null;

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
                header.classList.remove(STUCK_CLASS, UNSTICKING_CLASS, MORPHING_CLASS);
            }, MORPH_DURATION);
        }
    }

    function updateFromScroll() {
        ticking = false;
        syncPlaceholderHeight();
        setStuck(window.scrollY > STUCK_OFFSET);
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
        stickyShop = header.querySelector("[data-ab-sticky-shop]");
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
