/** @odoo-module ignore **/
(function () {
    "use strict";

    const TOGGLE_SELECTOR = ".ab-storefront-side-category-toggle[data-ab-category-target]";

    function toggleCategory(button) {
        const targetSelector = button.dataset.abCategoryTarget;
        if (!targetSelector) {
            return;
        }
        const target = document.querySelector(targetSelector);
        if (!target) {
            return;
        }
        const isOpen = !target.classList.contains("show");
        if (isOpen) {
            const currentItem = button.closest(".ab-storefront-side-category-item");
            currentItem?.parentElement?.querySelectorAll(`:scope > .ab-storefront-side-category-item > ${TOGGLE_SELECTOR}`).forEach((sibling) => {
                if (sibling === button) {
                    return;
                }
                const siblingTarget = document.querySelector(sibling.dataset.abCategoryTarget);
                siblingTarget?.classList.remove("show");
                sibling.classList.add("collapsed");
                sibling.setAttribute("aria-expanded", "false");
            });
        }
        target.classList.toggle("show", isOpen);
        button.classList.toggle("collapsed", !isOpen);
        button.setAttribute("aria-expanded", isOpen ? "true" : "false");
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
