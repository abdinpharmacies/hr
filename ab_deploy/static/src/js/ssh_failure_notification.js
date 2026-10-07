/** @odoo-module **/

import { registry } from "@web/core/registry";
import { renderToMarkup } from "@web/core/utils/render";

registry.category("actions").add("ab_deploy_ssh_failure_notification", (env, action) => {
    const { title, summary, failures } = action.params;
    env.services.notification.add(
        renderToMarkup("ab_deploy.SshFailureReport", { summary, failures }),
        { title, type: "warning", sticky: true, className: "ab_deploy_ssh_failure_notification" }
    );
});
