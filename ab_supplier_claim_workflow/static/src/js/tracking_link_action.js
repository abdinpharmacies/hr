/** @odoo-module **/

import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

registry.category("actions").add("supplier_claim_copy_tracking_link", async (env, action) => {
    const url = action.params?.url || "";
    if (!url) {
        env.services.notification.add(_t("Tracking link is not available."), { type: "warning" });
        return;
    }
    try {
        await navigator.clipboard.writeText(url);
        env.services.notification.add(_t("Tracking link copied."), { type: "success" });
    } catch {
        env.services.notification.add(url, {
            title: _t("Tracking Link"),
            type: "info",
            sticky: true,
        });
    }
});
