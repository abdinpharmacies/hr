/** @odoo-module **/

import { registry } from "@web/core/registry";
import { SearchBarResults } from "@website/snippets/s_searchbar/search_bar_results";
import { SearchBar } from "@website/snippets/s_searchbar/search_bar";
import { patch } from "@web/core/utils/patch";

patch(SearchBar.prototype, {
    start() {
        super.start();
        this.abStorefrontOnImmediateInput = () => this.abStorefrontClearEmptySearch();
        this.inputEl.addEventListener("input", this.abStorefrontOnImmediateInput);
        this.inputEl.addEventListener("search", this.abStorefrontOnImmediateInput);
    },

    destroy() {
        this.inputEl?.removeEventListener("input", this.abStorefrontOnImmediateInput);
        this.inputEl?.removeEventListener("search", this.abStorefrontOnImmediateInput);
        super.destroy();
    },

    async onInput() {
        if (!this.limit) {
            return;
        }
        if (!this.inputEl.value.trim().length) {
            await this.abStorefrontClearEmptySearch();
            return;
        }
        return super.onInput();
    },

    onSearch(ev) {
        if (!this.inputEl.value.trim().length) {
            this.render();
            ev.preventDefault();
            return;
        }
        return super.onSearch(ev);
    },

    async abStorefrontClearEmptySearch() {
        if (this.inputEl.value.trim().length) {
            return;
        }
        this.render();
        await this.keepLast.add(this.waitFor(Promise.resolve(null)));
    },
});

class AbStorefrontSearchBarResults extends SearchBarResults {
    setup() {
        super.setup();
        if (!this.searchBarEl.closest(".ab-storefront-products-grid")) {
            return;
        }
        this.isDropup = false;
        this.dynamicContent._window["t-on-scroll"] = () => {};
        const originalStyle = this.dynamicContent._root["t-att-style"];
        this.dynamicContent._root["t-att-style"] = () => {
            const bounds = this.searchBarEl.getBoundingClientRect();
            const viewport = window.visualViewport;
            const viewportBottom = viewport
                ? viewport.offsetTop + viewport.height
                : document.documentElement.clientHeight;
            const availableHeight = Math.max(0, viewportBottom - bounds.bottom - 20);
            return {
                ...originalStyle.call(this),
                "max-height": `${Math.min(384, availableHeight)}px !important`,
                "min-width": "0 !important",
            };
        };
        if (window.visualViewport) {
            const updatePosition = () => this.updateContent();
            window.visualViewport.addEventListener("resize", updatePosition);
            window.visualViewport.addEventListener("scroll", updatePosition);
            this.registerCleanup(() => {
                window.visualViewport.removeEventListener("resize", updatePosition);
                window.visualViewport.removeEventListener("scroll", updatePosition);
            });
        }
    }
}

registry.category("public.interactions").add(
    "website.search_bar_results",
    AbStorefrontSearchBarResults,
    { force: true }
);
