/** @odoo-module **/

import {registry} from "@web/core/registry";
import {user} from "@web/core/user";
import {_t} from "@web/core/l10n/translation";

export function groupNotificationItems(items) {
    const groups = new Map();
    for (const item of items) {
        const key = item.customer_group_key || item.alert_key;
        if (!groups.has(key)) groups.set(key, {key, name: item.name, conversations: [], count: 0});
        const group = groups.get(key);
        group.conversations.push(item);
        group.count += item.count;
    }
    return [...groups.values()];
}

registry.category("services").add("ab_chatter_session", {
    dependencies: ["orm", "notification", "action", "localization", "ab_chatter_feedback"],
    start(env, {orm, notification, action, ab_chatter_feedback: feedback}) {
        const key = `ab_chatter_session_v2_${user.userId}`;
        let session = null;
        let polling = false;
        let generation = 0;
        let repoll = false;
        const alerts = new Map();
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
            unreadChanged(broadcast = true) {
                generation++;
                env.bus.trigger("AB_CHATTER_UNREAD");
                if (broadcast && session) channel?.postMessage({employee: session.employee_id, company: user.activeCompany.id});
                service.poll();
            },
            async acknowledge(item, token) {
                if (session?.token !== token) return;
                await feedback.call(orm, "ab_crm_chatter_api", "acknowledge_alert", [], {token, conversation_id: item.conversation_id, message_ids: [...item.message_ids]});
                if (session?.token === token) service.unreadChanged();
            },
            async dismiss(items, token) {
                try {
                    for (const item of items) await service.acknowledge(item, token);
                } catch (error) {
                    feedback.report(error);
                }
            },
            async open(item, token) {
                if (session?.token !== token) return;
                try {
                    if (service.focusHandler) {
                        await service.focusHandler(item, token);
                    } else {
                        await action.doAction("ab_crm_sales_workspace.action_workspace", {additionalContext: {chatter_conversation_id: item.conversation_id, chatter_alert: item}});
                    }
                } catch (error) {
                    feedback.report(error);
                }
            },
            async poll() {
                if (!session) return;
                if (polling) { repoll = true; return; }
                const token = session.token;
                const version = generation;
                polling = true;
                try {
                    let cursor = 0;
                    let more = true;
                    const pending = new Map();
                    while (more && session?.token === token && version === generation) {
                        const result = await feedback.call(orm, "ab_crm_chatter_api", "notifications", [], {token, after_id: cursor});
                        for (const item of result.items) pending.set(item.alert_key, item);
                        cursor = result.cursor;
                        more = result.has_more;
                    }
                    if (session?.token !== token || version !== generation) return;
                    const groups = groupNotificationItems([...pending.values()]);
                    const keys = new Set(groups.map(group => group.key));
                    for (const alertKey of alerts.keys()) if (!keys.has(alertKey)) hide(alertKey);
                    for (const group of groups) {
                        const alertKey = group.key;
                        const signature = JSON.stringify(group);
                        if (alerts.get(alertKey)?.signature === signature) continue;
                        hide(alertKey);
                        const alert = {silent: false, signature};
                        const conversations = group.conversations.map(item => ({
                            ...item, message_ids: [...item.message_ids],
                            source: {telegram: _t("Telegram"), whatsapp: _t("WhatsApp"), website: _t("Website")}[item.provider] || _t("Channel"),
                        }));
                        const text = [_t("%s pending messages", group.count), ...conversations.map(item =>
                            [item.source, item.display_destination, item.conversation_label, String(item.unread_count), item.preview].filter(Boolean).join(" · "))].join("\n");
                        alert.close = notification.add(text, {
                            title: group.name, type: "info", sticky: true, className: "ab_chatter_notification",
                            buttons: conversations.map(item => ({
                                name: [_t("Open conversation"), item.source, item.display_destination, item.conversation_label].filter(Boolean).join(" · "),
                                onClick: () => service.open(item, token),
                            })),
                            onClose: () => {
                                if (alert.silent) return;
                                if (alerts.get(alertKey) === alert) alerts.delete(alertKey);
                                return service.dismiss(conversations, token);
                            },
                        });
                        alerts.set(alertKey, alert);
                    }
                } catch (error) {
                    if (error.data?.name === "odoo.exceptions.AccessError" && session?.token === token) service.clear();
                    else feedback.report(error);
                } finally {
                    polling = false;
                    if (repoll) { repoll = false; service.poll(); }
                }
            },
        };
        if (channel) channel.onmessage = ({data}) => {
            if (session?.employee_id === data.employee && user.activeCompany.id === data.company) { service.unreadChanged(false); }
        };
        setInterval(() => service.poll(), 5000);
        service.poll();
        return service;
    },
});
