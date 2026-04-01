/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { user } from "@web/core/user";
import { ListController } from "@web/views/list/list_controller";
import { FormController } from "@web/views/form/form_controller";

function isRestrictedFeedbackModel(controller) {
    return controller?.props?.resModel === "hr.employee.feedback";
}

function isAdminUser() {
    return user.isAdmin || user.isSystem;
}

patch(ListController.prototype, {
    getStaticActionMenuItems() {
        const items = super.getStaticActionMenuItems();
        if (isRestrictedFeedbackModel(this) && !isAdminUser()) {
            delete items.export;
            delete items.duplicate;
            delete items.archive;
            delete items.unarchive;
            delete items.delete;
        }
        return items;
    },
});

patch(FormController.prototype, {
    getStaticActionMenuItems() {
        const items = super.getStaticActionMenuItems();
        if (isRestrictedFeedbackModel(this) && !isAdminUser()) {
            delete items.duplicate;
            delete items.archive;
            delete items.unarchive;
            delete items.delete;
        }
        return items;
    },
});
