/** @odoo-module **/

import {Component, reactive} from "@odoo/owl";
import {registry} from "@web/core/registry";
import {user} from "@web/core/user";
import {_t} from "@web/core/l10n/translation";

class ChatterAlertContainer extends Component {
    static template = "ab_crm_sales_workspace.Alerts";
    static props = ["alerts"];
    get items() { return Object.values(this.props.alerts); }
}

registry.category("services").add("ab_chatter_session", {
    dependencies: ["orm", "notification", "action"],
    start(env, {orm, notification, action}) {
        const key = `ab_chatter_session_v2_${user.userId}`;
        let session = null;
        let polling = false;
        let generation = 0;
        const alerts = new Map();
        const visibleAlerts = reactive({});
        registry.category("main_components").add("ab_chatter_alerts", {Component: ChatterAlertContainer, props: {alerts: visibleAlerts}});
        const channel = typeof BroadcastChannel === "undefined" ? null : new BroadcastChannel(`ab_chatter_alerts_${user.userId}`);
        try { session = JSON.parse(sessionStorage.getItem(key) || "null"); } catch { sessionStorage.removeItem(key); }
        const hide = alertKey => {
            const alert = alerts.get(alertKey);
            if (alert) { alert.silent = true; alert.close(); alerts.delete(alertKey); }
        };
        const save = () => {
            if (session) sessionStorage.setItem(key, JSON.stringify(session));
            else sessionStorage.removeItem(key);
        };
        const service = {
            get current() { return session; },
            workspaceDrafts: new Map(),
            focusHandler: null,
            set(value) {
                generation++;
                for (const alertKey of alerts.keys()) hide(alertKey);
                session = value; save(); env.bus.trigger("AB_CHATTER_SESSION", session);
                service.poll();
            },
            clear() { service.set(null); },
            async acknowledge(item, token) {
                if (session?.token !== token) return;
                await orm.call("ab_crm_chatter_api", "acknowledge_alert", [], {token, conversation_id: item.conversation_id, message_ids: item.message_ids});
                generation++;
                hide(item.alert_key);
                channel?.postMessage({employee: session.employee_id, company: user.activeCompany.id});
                service.poll();
            },
            async open(item, token) {
                if (session?.token !== token) return;
                try {
                    if (service.focusHandler) {
                        await service.focusHandler(item, token);
                    } else {
                        await action.doAction("ab_crm_sales_workspace.action_workspace", {additionalContext: {chatter_conversation_id: item.conversation_id, chatter_alert: item}});
                    }
                } catch {
                    notification.add(_t("Couldn’t open the conversation. Try again."), {type: "warning"});
                }
            },
            async poll() {
                if (!session || polling) return;
                const token = session.token;
                const version = generation;
                polling = true;
                try {
                    let cursor = 0;
                    let more = true;
                    const pending = new Map();
                    while (more && session?.token === token && version === generation) {
                        const result = await orm.call("ab_crm_chatter_api", "notifications", [], {token, after_id: cursor});
                        for (const item of result.items) pending.set(item.alert_key, item);
                        cursor = result.cursor;
                        more = result.has_more;
                    }
                    if (session?.token !== token || version !== generation) return;
                    for (const alertKey of alerts.keys()) if (!pending.has(alertKey)) hide(alertKey);
                    for (const [alertKey, item] of pending) {
                        const signature = item.message_ids.join(",");
                        if (alerts.get(alertKey)?.signature === signature) continue;
                        hide(alertKey);
                        const source = {telegram: _t("Telegram"), whatsapp: _t("WhatsApp"), website: _t("Website")}[item.provider] || _t("Channel");
                        const alert = {silent: false, signature};
                        alert.close = () => { delete visibleAlerts[alertKey]; };
                        visibleAlerts[alertKey] = {
                            key: alertKey, title: `${item.name} · ${source}`,
                            text: _t("%s pending messages · %s", item.count, item.preview),
                            open: () => service.open(item, token),
                            dismiss: () => {
                                alert.close(); alerts.delete(alertKey);
                                service.acknowledge(item, token).catch(() => service.poll());
                            },
                        };
                        alerts.set(alertKey, alert);
                    }
                } catch (error) {
                    if (error.data?.name === "odoo.exceptions.AccessError" && session?.token === token) service.clear();
                } finally { polling = false; }
            },
        };
        if (channel) channel.onmessage = ({data}) => {
            if (session?.employee_id === data.employee && user.activeCompany.id === data.company) { generation++; service.poll(); }
        };
        setInterval(() => service.poll(), 5000);
        service.poll();
        return service;
    },
});
