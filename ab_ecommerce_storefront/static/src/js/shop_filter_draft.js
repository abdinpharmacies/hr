/** @odoo-module ignore **/
(function () {
    "use strict";

    const FILTER_PARAMS = [
        "attribute_values", "tags", "min_price", "max_price",
        "brand", "deal", "include_oos", "need",
    ];
    const DEAL_ORDER = ["discount", "coupon", "today"];
    const MOBILE_QUERY = "(max-width: 991.98px)";

    function initShopFilterDraft() {
        const dialog = document.querySelector("#o_wsale_offcanvas.ab-storefront-filter-dialog");
        if (!dialog) {
            return;
        }

        let draftUrl = null;
        let inputSnapshot = [];
        let rangeSnapshot = null;

        function isMobile() {
            return window.matchMedia(MOBILE_QUERY).matches;
        }

        function currentDraft() {
            draftUrl ||= new URL(window.location.href);
            return draftUrl;
        }

        function syncChoices() {
            const url = draftUrl || new URL(window.location.href);
            const selectedDeals = new Set((url.searchParams.get("deal") || "").split(","));
            const hasDeals = DEAL_ORDER.some((deal) => selectedDeals.has(deal));
            const selectedBrand = url.searchParams.get("brand") || "";
            const selectedNeed = url.searchParams.get("need") || "";
            const includeOutOfStock = url.searchParams.get("include_oos") === "1";
            const hasFilters = FILTER_PARAMS.some((name) => url.searchParams.has(name));

            for (const link of dialog.querySelectorAll("[data-ab-deal]")) {
                const checked = selectedDeals.has(link.dataset.abDeal);
                link.classList.toggle("active", checked);
                link.setAttribute("aria-checked", String(checked));
            }
            for (const link of dialog.querySelectorAll("[data-ab-deal-clear]")) {
                link.classList.toggle("d-none", !hasDeals);
            }
            for (const choices of dialog.querySelectorAll(".ab-storefront-filter-choice-list")) {
                choices.classList.toggle("d-none", hasDeals);
            }
            for (const link of dialog.querySelectorAll("[data-ab-brand]")) {
                const active = link.dataset.abBrand === selectedBrand;
                link.classList.toggle("active", active);
                if (active) {
                    link.setAttribute("aria-current", "true");
                } else {
                    link.removeAttribute("aria-current");
                }
            }
            for (const link of dialog.querySelectorAll("[data-ab-need]")) {
                const active = link.dataset.abNeed === selectedNeed;
                link.classList.toggle("active", active);
                if (active) {
                    link.setAttribute("aria-current", "true");
                } else {
                    link.removeAttribute("aria-current");
                }
            }
            for (const link of dialog.querySelectorAll("[data-ab-include-oos]")) {
                link.classList.toggle("active", includeOutOfStock);
                link.setAttribute("aria-pressed", String(includeOutOfStock));
            }
            for (const link of dialog.querySelectorAll(".ab-storefront-side-category-link[href]")) {
                const active = new URL(link.href).pathname === url.pathname;
                link.classList.toggle("active", active);
                if (active) {
                    link.setAttribute("aria-current", "page");
                } else {
                    link.removeAttribute("aria-current");
                }
            }
            for (const link of dialog.querySelectorAll(".ab-storefront-filter-dialog-actions a[href]")) {
                link.classList.toggle("disabled", !hasFilters);
                link.setAttribute("aria-disabled", String(!hasFilters));
            }
        }

        function rememberInputs() {
            inputSnapshot = [...dialog.querySelectorAll("form.js_attributes input, form.js_attributes select, input[name='wsale_sortby_radios_offcanvas']")]
                .map((input) => ({ input, checked: input.checked, value: input.value }));
            const range = dialog.querySelector("#o_wsale_price_range_option input[type='range'][multiple]");
            rangeSnapshot = range && Number.isFinite(Number(range.valueLow))
                && Number.isFinite(Number(range.valueHigh))
                ? { range, low: range.valueLow, high: range.valueHigh } : null;
        }

        function restoreInputs() {
            for (const { input, checked, value } of inputSnapshot) {
                input.checked = checked;
                input.value = value;
            }
            if (rangeSnapshot) {
                rangeSnapshot.range.value = `${rangeSnapshot.low},${rangeSnapshot.high}`;
            }
        }

        function updateAttributes(form) {
            const values = new Map();
            const tags = new Set();
            for (const input of form.querySelectorAll("input:checked, select")) {
                if (!input.value) {
                    continue;
                }
                if (input.name === "attribute_value") {
                    const [attributeId, valueId] = input.value.split("-");
                    if (!values.has(attributeId)) {
                        values.set(attributeId, new Set());
                    }
                    values.get(attributeId).add(valueId);
                } else if (input.name === "tags") {
                    tags.add(input.value);
                }
            }
            const params = currentDraft().searchParams;
            params.delete("attribute_values");
            for (const [attributeId, valueIds] of values) {
                params.append("attribute_values", `${attributeId}-${[...valueIds].join(",")}`);
            }
            if (tags.size) {
                params.set("tags", [...tags].join(","));
            } else {
                params.delete("tags");
            }
        }

        dialog.addEventListener("show.bs.offcanvas", () => {
            if (!isMobile()) {
                return;
            }
            draftUrl = new URL(window.location.href);
            rememberInputs();
            syncChoices();
        });

        dialog.addEventListener("hidden.bs.offcanvas", () => {
            restoreInputs();
            draftUrl = null;
            syncChoices();
        });

        document.addEventListener("click", (event) => {
            if (!isMobile() || !(event.target instanceof Element) || !dialog.contains(event.target)) {
                return;
            }
            const save = event.target.closest(".ab-storefront-filter-apply");
            if (save) {
                const selected = currentDraft();
                if (selected.href !== window.location.href) {
                    event.preventDefault();
                    event.stopPropagation();
                    window.location.assign(selected.href);
                }
                return;
            }

            const link = event.target.closest("a[href]");
            if (!link || !dialog.contains(link) || event.metaKey || event.ctrlKey || event.shiftKey) {
                return;
            }
            const targetUrl = new URL(link.href);
            if (targetUrl.origin !== window.location.origin) {
                return;
            }
            const draft = currentDraft();
            const params = draft.searchParams;
            if (link.hasAttribute("data-ab-deal-clear")) {
                params.delete("deal");
            } else if (link.hasAttribute("data-ab-deal")) {
                const selected = new Set((params.get("deal") || "").split(",").filter(Boolean));
                const deal = link.dataset.abDeal;
                if (selected.has(deal)) {
                    selected.delete(deal);
                } else {
                    selected.add(deal);
                }
                const deals = DEAL_ORDER.filter((item) => selected.has(item));
                if (deals.length) {
                    params.set("deal", deals.join(","));
                } else {
                    params.delete("deal");
                }
            } else if (link.hasAttribute("data-ab-need")) {
                if (link.dataset.abNeed) {
                    params.set("need", link.dataset.abNeed);
                } else {
                    params.delete("need");
                }
                draft.pathname = draft.pathname.replace(/\/page\/\d+\/?$/, "");
            } else if (link.hasAttribute("data-ab-brand")) {
                if (link.dataset.abBrand) {
                    params.set("brand", link.dataset.abBrand);
                } else {
                    params.delete("brand");
                }
            } else if (link.hasAttribute("data-ab-include-oos")) {
                if (params.get("include_oos") === "1") {
                    params.delete("include_oos");
                } else {
                    params.set("include_oos", "1");
                }
            } else if (link.matches(".ab-storefront-filter-clear, .ab-storefront-filter-dialog-actions a")) {
                FILTER_PARAMS.forEach((name) => params.delete(name));
                for (const input of dialog.querySelectorAll("form.js_attributes input, form.js_attributes select")) {
                    if (input.type === "checkbox" || input.type === "radio") {
                        input.checked = false;
                    } else if (input.tagName === "SELECT") {
                        input.selectedIndex = 0;
                    }
                }
                const range = dialog.querySelector("#o_wsale_price_range_option input[type='range'][multiple]");
                if (range && rangeSnapshot) {
                    range.value = `${range.min},${range.max}`;
                }
            } else if (link.closest("#o_wsale_offcanvas_orderby")) {
                const order = targetUrl.searchParams.get("order");
                if (order) {
                    params.set("order", order);
                } else {
                    params.delete("order");
                }
                const radio = link.querySelector("input[type='radio']");
                if (radio) {
                    radio.checked = true;
                }
            } else if (link.closest("#o_wsale_offcanvas_content")) {
                draft.pathname = targetUrl.pathname;
            } else {
                return;
            }
            event.preventDefault();
            event.stopPropagation();
            syncChoices();
        }, true);

        document.addEventListener("change", (event) => {
            if (!isMobile() || !(event.target instanceof Element) || !dialog.contains(event.target)) {
                return;
            }
            const form = event.target.closest("form.js_attributes");
            if (!form) {
                return;
            }
            event.preventDefault();
            event.stopPropagation();
            updateAttributes(form);
        }, true);

        document.addEventListener("newRangeValue", (event) => {
            if (!isMobile() || !(event.target instanceof Element) || !dialog.contains(event.target)) {
                return;
            }
            const range = event.target.closest("#o_wsale_price_range_option input[type='range'][multiple]");
            if (!range) {
                return;
            }
            event.preventDefault();
            event.stopPropagation();
            const params = currentDraft().searchParams;
            if (Number(range.valueLow) > Number(range.min)) {
                params.set("min_price", range.valueLow);
            } else {
                params.delete("min_price");
            }
            if (Number(range.valueHigh) < Number(range.max)) {
                params.set("max_price", range.valueHigh);
            } else {
                params.delete("max_price");
            }
        }, true);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initShopFilterDraft, { once: true });
    } else {
        initShopFilterDraft();
    }
}());
