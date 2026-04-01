/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { user } from "@web/core/user";
import { CogMenu } from "@web/search/cog_menu/cog_menu";

function isRestrictedFeedbackModel(component) {
    return component?.props?.resModel === "hr.employee.feedback";
}

function isAdminUser() {
    return user.isAdmin || user.isSystem;
}

patch(CogMenu.prototype, {
    async _registryItems() {
        if (isRestrictedFeedbackModel(this) && !isAdminUser()) {
            return [];
        }
        return await super._registryItems();
    },
});
