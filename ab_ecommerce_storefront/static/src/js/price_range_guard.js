/** @odoo-module ignore **/
(function () {
    "use strict";

    const PRICE_RANGE_SELECTOR = "#o_wsale_price_range_option input[type='range'][multiple]";
    const RANGE_WRAPPER_SELECTOR = "#o_wsale_price_range_option .multirange-wrapper";
    const BUSY_ATTRIBUTE = "data-ab-price-range-guard-busy";

    function toNumber(value, fallback) {
        const parsed = Number.parseFloat(value);
        return Number.isFinite(parsed) ? parsed : fallback;
    }

    function clamp(value, min, max) {
        return Math.min(Math.max(value, min), max);
    }

    function getRangeParts(input) {
        const wrapper = input.closest(".multirange-wrapper");
        if (!wrapper) {
            return {};
        }
        return {
            wrapper,
            minInput: wrapper.querySelector("input.original.multirange"),
            maxInput: wrapper.querySelector("input.ghost.multirange"),
        };
    }

    function syncCounters(wrapper, minInput, maxInput) {
        const minCounter = wrapper.querySelector("span.multirange-min");
        const maxCounter = wrapper.querySelector("span.multirange-max");
        const minEditor = wrapper.querySelector("input.multirange-min");
        const maxEditor = wrapper.querySelector("input.multirange-max");

        if (minCounter && minEditor) {
            minEditor.value = minInput.originalValue || minInput.valueLow || minInput.value;
        }
        if (maxCounter && maxEditor) {
            maxEditor.value = maxInput.value || minInput.valueHigh;
        }
    }

    function forceCounterLayout(wrapper) {
        const minCounter = wrapper.querySelector("span.multirange-min");
        const maxCounter = wrapper.querySelector("span.multirange-max");
        const minEditor = wrapper.querySelector("input.multirange-min");
        const maxEditor = wrapper.querySelector("input.multirange-max");

        wrapper.style.direction = "ltr";

        [minCounter, minEditor].forEach((element) => {
            if (!element) {
                return;
            }
            element.style.left = "0";
            element.style.right = "auto";
            element.style.textAlign = "left";
        });

        [maxCounter, maxEditor].forEach((element) => {
            if (!element) {
                return;
            }
            element.style.left = "auto";
            element.style.right = "0";
            element.style.textAlign = "right";
        });
    }

    function syncTrack(wrapper, minInput, maxInput, minValue, maxValue) {
        const min = toNumber(minInput.min, 0);
        const max = toNumber(minInput.max, 100);
        const span = max - min || 1;
        const low = 100 * (minValue - min) / span;
        const high = 100 * (maxValue - min) / span;

        wrapper.style.setProperty("--low", `${low}%`);
        wrapper.style.setProperty("--high", `${high}%`);
        syncCounters(wrapper, minInput, maxInput);
    }

    function applyRangeDirection(root = document) {
        root.querySelectorAll(RANGE_WRAPPER_SELECTOR).forEach((wrapper) => {
            wrapper.classList.add("ab-storefront-price-range-wrapper");
            forceCounterLayout(wrapper);
            wrapper.querySelectorAll("input[type='range'].multirange").forEach((input) => {
                input.style.direction = "ltr";
            });
        });
    }

    function guardRange(input) {
        const { wrapper, minInput, maxInput } = getRangeParts(input);
        if (!wrapper || !minInput || !maxInput || wrapper.hasAttribute(BUSY_ATTRIBUTE)) {
            return;
        }

        const min = toNumber(minInput.min, 0);
        const max = toNumber(minInput.max, 100);
        let minValue = clamp(toNumber(minInput.originalValue, min), min, max);
        let maxValue = clamp(toNumber(maxInput.value, max), min, max);

        if (minValue > maxValue) {
            if (input === maxInput) {
                maxValue = minValue;
            } else {
                minValue = maxValue;
            }
        }

        if (String(minInput.originalValue) !== String(minValue)) {
            minInput.originalValue = String(minValue);
        }
        if (String(maxInput.value) !== String(maxValue)) {
            maxInput.value = String(maxValue);
        }

        syncTrack(wrapper, minInput, maxInput, minValue, maxValue);
        forceCounterLayout(wrapper);
    }

    function onRangeInput(ev) {
        const input = ev.target.closest?.(PRICE_RANGE_SELECTOR);
        if (!input) {
            return;
        }
        guardRange(input);
    }

    function onNewRangeValue(ev) {
        const input = ev.target.closest?.(PRICE_RANGE_SELECTOR);
        if (!input) {
            return;
        }
        guardRange(input);
    }

    function initPriceRangeGuard() {
        const priceRangeOption = document.querySelector("#o_wsale_price_range_option");
        if (!priceRangeOption) {
            return;
        }

        applyRangeDirection(priceRangeOption);
        document.addEventListener("input", onRangeInput, true);
        document.addEventListener("newRangeValue", onNewRangeValue, true);

        const observer = new MutationObserver(() => applyRangeDirection(priceRangeOption));
        observer.observe(priceRangeOption, {
            childList: true,
            subtree: true,
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initPriceRangeGuard, { once: true });
    } else {
        initPriceRangeGuard();
    }
}());
