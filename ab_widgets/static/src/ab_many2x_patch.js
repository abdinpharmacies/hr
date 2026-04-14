/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { Many2XAutocomplete } from "@web/views/fields/relational_utils";

const originalSearch = Many2XAutocomplete.prototype.search;

patch(Many2XAutocomplete.prototype, {
    async search(name) {
        if (
            this.lastEmptySearch &&
            name &&
            name.startsWith(this.lastEmptySearch.name) &&
            name.length > this.lastEmptySearch.name.length
        ) {
            this.lastEmptySearch = null;
        }
        return await originalSearch.call(this, name);
    },
});
