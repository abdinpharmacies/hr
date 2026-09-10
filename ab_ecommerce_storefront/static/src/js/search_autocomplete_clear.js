/** @odoo-module **/

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
