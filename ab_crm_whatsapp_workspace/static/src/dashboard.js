import "@ab_whatsapp_api/dashboard/whatsapp_dashboard";
import {registry} from "@web/core/registry";
import {patch} from "@web/core/utils/patch";
import {_t} from "@web/core/l10n/translation";

const Dashboard = registry.category("actions").get("ab_whatsapp_api.dashboard");
patch(Dashboard.prototype, {
    setup() {
        super.setup();
        const notification = this.notification;
        this.notification = {...notification, add: (message, options) => {
            if (this.activeContact?.integrated) {
                if (message === "Message sent.") message = _t("Message queued.");
                if (message === "Template sent.") message = _t("Template queued.");
            }
            return notification.add(message, options);
        }};
    },
    canEdit(message) { return !message.integrated && super.canEdit(message); },
    canDelete(message) { return !message.integrated && super.canDelete(message); },
    statusClass(message) {
        if (message.integrated && ["queued", "accepted", "uncertain"].includes(message.status)) return message.status;
        return super.statusClass(message);
    },
    statusSymbol(message) {
        if (message.integrated) {
            const labels = {queued: _t("Queued"), accepted: _t("Accepted"), uncertain: _t("Uncertain"), failed: _t("Failed")};
            if (labels[message.status]) return labels[message.status];
        }
        return super.statusSymbol(message);
    },
});
