/** @odoo-module **/

const initializeOrderCenter = () => {
    const page = document.querySelector("[data-ab-customer-orders]");
    if (!page) {
        return;
    }

    const list = page.querySelector(".ab-customer-orders-list");
    const switcher = page.querySelector(".ab-customer-orders-switcher");
    const tabsTrack = switcher.querySelector("[data-ab-order-tabs]");
    const cards = [...list.querySelectorAll("[data-ab-order-card]")];
    const buttons = [...page.querySelectorAll("[data-ab-order-filter]")];
    const emptyStates = [...page.querySelectorAll("[data-ab-order-empty]")];

    cards.sort((first, second) => {
        const firstDate = Date.parse(first.dataset.abOrderDate || "") || 0;
        const secondDate = Date.parse(second.dataset.abOrderDate || "") || 0;
        return secondDate - firstDate;
    }).forEach((card) => list.insertBefore(card, emptyStates[0] || null));

    const setFilter = (filter, animate = true) => {
        if (!animate) {
            switcher.classList.add("is-initializing");
        }

        buttons.forEach((button) => {
            const isActive = button.dataset.abOrderFilter === filter;
            button.classList.toggle("is-active", isActive);
            button.setAttribute("aria-pressed", String(isActive));
        });
        tabsTrack.dataset.abActiveFilter = filter;

        let visibleCount = 0;
        cards.forEach((card) => {
            const isVisible = filter === "all" || card.dataset.abOrderCard === filter;
            card.hidden = !isVisible;
            visibleCount += Number(isVisible);
        });

        const emptyType = visibleCount ? "" : filter;
        emptyStates.forEach((emptyState) => {
            emptyState.hidden = emptyState.dataset.abOrderEmpty !== emptyType;
        });

        if (!animate) {
            requestAnimationFrame(() => switcher.classList.remove("is-initializing"));
        }
    };

    buttons.forEach((button) => {
        button.addEventListener("click", () => setFilter(button.dataset.abOrderFilter));
    });
    const requestedFilter = new URLSearchParams(window.location.search).get("order_type");
    const initialFilter = buttons.some((button) => button.dataset.abOrderFilter === requestedFilter)
        ? requestedFilter
        : "all";
    setFilter(initialFilter, false);
};

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initializeOrderCenter, { once: true });
} else {
    initializeOrderCenter();
}
