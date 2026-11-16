/** @odoo-module **/

import {
    Many2ManyTagsField,
    many2ManyTagsField,
} from "@web/views/fields/many2many_tags/many2many_tags_field";
import { registry } from "@web/core/registry";

export class Many2ManyTagsAddOnlyField extends Many2ManyTagsField {
    getTagProps(record) {
        return {
            ...super.getTagProps(record),
            onDelete: undefined,
        };
    }

    deleteTag() {
        return Promise.resolve();
    }
}

export const many2ManyTagsAddOnlyField = {
    ...many2ManyTagsField,
    component: Many2ManyTagsAddOnlyField,
};

registry.category("fields").add("many2many_tags_add_only", many2ManyTagsAddOnlyField);
