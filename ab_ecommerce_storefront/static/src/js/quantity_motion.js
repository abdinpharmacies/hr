/** @odoo-module **/

const QUANTITY_MOTION_CLASSES = [
    "ab-storefront-quantity-slide-next",
    "ab-storefront-quantity-slide-prev",
    "ab-storefront-quantity-shake",
];

function getQuantityNumber(quantity) {
    const value = Number.parseFloat(quantity?.value);
    return Number.isFinite(value) ? value : 0;
}

function getQuantityLimit(quantity, name, fallback) {
    const rawValue = quantity?.dataset?.[name] ?? quantity?.getAttribute?.(name);
    const value = Number.parseFloat(rawValue);
    return Number.isFinite(value) ? value : fallback;
}

function isQuantityBlocked(quantity, button, previousValue, nextValue, direction) {
    if (button?.classList?.contains("disabled") || button?.getAttribute?.("aria-disabled") === "true") {
        return true;
    }
    if (direction === "decrease") {
        const minValue = getQuantityLimit(quantity, "min", 1);
        return previousValue <= minValue && nextValue <= minValue;
    }
    const maxValue = getQuantityLimit(quantity, "max", Infinity);
    if (previousValue >= maxValue && nextValue >= maxValue) {
        return true;
    }
    return nextValue === previousValue;
}

function applyQuantityMotion(quantity, className) {
    quantity.classList.remove(...QUANTITY_MOTION_CLASSES);
    void quantity.offsetWidth;
    quantity.classList.add(className);
}

export function animateQuantityChange({
    button,
    quantity,
    direction,
    previousValue,
    delay = 80,
} = {}) {
    if (!quantity) {
        return;
    }
    const initialValue = Number.isFinite(previousValue) ? previousValue : getQuantityNumber(quantity);
    const motionDirection = direction
        || (button?.classList?.contains("css_quantity_plus") ? "increase" : "decrease");
    window.setTimeout(() => {
        const nextValue = getQuantityNumber(quantity);
        const className = isQuantityBlocked(quantity, button, initialValue, nextValue, motionDirection)
            ? "ab-storefront-quantity-shake"
            : motionDirection === "increase"
                ? "ab-storefront-quantity-slide-next"
                : "ab-storefront-quantity-slide-prev";
        applyQuantityMotion(quantity, className);
    }, delay);
}

export function getQuantityInputNumber(quantity) {
    return getQuantityNumber(quantity);
}
