/** @odoo-module ignore **/
(function () {
    "use strict";

    const TOGGLE_SELECTOR = ".ab-storefront-side-category-toggle[data-ab-category-target]";
    const animations = new WeakMap();
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    const easing = "cubic-bezier(.22, 1, .36, 1)";

    function setCategoryOpen(button, target, isOpen) {
        const height = target.getBoundingClientRect().height;
        const opacity = getComputedStyle(target).opacity;
        const transform = getComputedStyle(target).transform;
        const wasVisible = target.classList.contains("show");
        animations.get(target)?.forEach((animation) => animation.cancel());
        animations.delete(target);
        button.classList.toggle("collapsed", !isOpen);
        button.setAttribute("aria-expanded", String(isOpen));
        target.inert = !isOpen;

        if (reducedMotion.matches || !target.animate) {
            target.classList.toggle("show", isOpen);
            return;
        }

        target.classList.add("show");
        const panelAnimation = target.animate([
            {
                height: `${height}px`,
                transform: wasVisible ? transform : "translateY(-8px) scale(.99)",
                overflow: "hidden",
                transformOrigin: "top center",
            },
            {
                height: isOpen ? `${target.getBoundingClientRect().height}px` : "0px",
                transform: isOpen ? "none" : "translateY(-8px) scale(.99)",
                overflow: "hidden",
                transformOrigin: "top center",
            },
        ], { duration: 240, easing });
        const running = [panelAnimation, target.animate([
            { opacity: wasVisible ? opacity : 0 },
            { opacity: isOpen ? 1 : 0 },
        ], { duration: isOpen ? 200 : 180, easing: "ease-out", fill: "forwards" })];
        animations.set(target, running);
        panelAnimation.onfinish = () => {
            if (animations.get(target) === running) {
                target.classList.toggle("show", isOpen);
                running[1].cancel();
            }
        };

        if (isOpen) {
            Array.from(target.children).forEach((item, index) => {
                const options = { delay: Math.min(index, 13) * 45, easing, fill: "backwards" };
                running.push(
                    item.animate([{ opacity: 0 }, { opacity: 1 }], { ...options, duration: 240 }),
                    item.animate([
                        { transform: "translateY(-9px) scale(.985)" },
                        { transform: "none" },
                    ], { ...options, duration: 280 }),
                );
            });
        }
    }

    function toggleCategory(button) {
        const targetSelector = button.dataset.abCategoryTarget;
        if (!targetSelector) {
            return;
        }
        const target = document.querySelector(targetSelector);
        if (!target) {
            return;
        }
        const isOpen = button.getAttribute("aria-expanded") !== "true";
        if (isOpen) {
            const currentItem = button.closest(".ab-storefront-side-category-item");
            currentItem?.parentElement?.querySelectorAll(`:scope > .ab-storefront-side-category-item > ${TOGGLE_SELECTOR}`).forEach((sibling) => {
                if (sibling === button) {
                    return;
                }
                const siblingTarget = document.querySelector(sibling.dataset.abCategoryTarget);
                if (siblingTarget && sibling.getAttribute("aria-expanded") === "true") {
                    setCategoryOpen(sibling, siblingTarget, false);
                }
            });
        }
        setCategoryOpen(button, target, isOpen);
    }

    document.addEventListener("click", (ev) => {
        const button = ev.target.closest(TOGGLE_SELECTOR);
        if (!button) {
            return;
        }
        ev.preventDefault();
        toggleCategory(button);
    });
}());
