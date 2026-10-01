/** @odoo-module **/
import {browser} from "@web/core/browser/browser";
import {registry} from "@web/core/registry";

export const restoreDeliveryActionService = {
    start() {
        // Odoo restores this action on reload without fetching its updated tag.
        // Services start before the webclient restores the current route.
        try {
            const storedAction = browser.sessionStorage.getItem("current_action");
            if (!storedAction) {
                return;
            }
            const action = JSON.parse(storedAction);
            if (action?.type !== "ir.actions.client" || action.tag !== "ab_sales.pos") {
                return;
            }
            action.tag = "ab_sales_delivery_tracking.pos";
            browser.sessionStorage.setItem("current_action", JSON.stringify(action));
        } catch {
            // Missing browser storage or an invalid saved action must not block startup.
        }
    },
};

registry.category("services").add(
    "ab_sales_delivery_tracking.restore_delivery_action",
    restoreDeliveryActionService
);
