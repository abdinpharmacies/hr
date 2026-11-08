/** @odoo-module **/
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

registry.category("actions").add("ab_legacy_process_batch", async (env, action) => {
    const batchId = action.params.batch_id;
    let close = env.services.notification.add(_t("Creating customer codes. Keep this page open."), { sticky: true });
    try {
        let result;
        do {
            result = await env.services.orm.call("ab_ecommerce_legacy_batch", "action_process_next", [[batchId]]);
            close();
            close = env.services.notification.add(_t("Processed %(processed)s of %(total)s customers.", result), { sticky: true });
        } while (!result.done);
    } finally {
        close();
    }
    return env.services.action.doAction({
        type: "ir.actions.act_window",
        res_model: "ab_ecommerce_legacy_batch",
        res_id: batchId,
        views: [[false, "form"]],
    });
});
