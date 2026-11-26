import {traceTiming} from "./timing";
/** @odoo-module **/

import {registry} from "@web/core/registry";
import {user} from "@web/core/user";
import {_t} from "@web/core/l10n/translation";

export function groupNotificationItems(items) {
    const groups = new Map();
    for (const item of items) {
        const key = item.alert_key;
        if (!groups.has(key)) groups.set(key, {key, name: item.name, conversations: [], count: 0});
        const group = groups.get(key);
        group.conversations.push(item);
        group.count += item.count;
    }
    return [...groups.values()];
}

registry.category("services").add("ab_chatter_session", {
    dependencies: ["orm", "notification", "action", "localization", "ab_chatter_feedback", "bus_service"],
    start(env, {orm, notification, action, ab_chatter_feedback: feedback, bus_service: busService}) {
        const key = `ab_chatter_session_v2_${user.userId}`;
        let session = null;
        let polling = false;
        let pollingIds = null;
        let generation = 0;
        let repoll = false;
        let pendingIds = new Set();
        let pendingFull = false;
        let invalidatedIds = new Set();
        let invalidatedCategories = new Set();
        let invalidatedFull = false;
        const snapshot = new Map();
        let invalidationTimer;
        let company = user.activeCompany.id;
        const alerts = new Map();
        const dismissed = new Map();
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
                company = user.activeCompany.id;
                generation++;
                clearTimeout(invalidationTimer);
                invalidationTimer = null;
                invalidatedIds.clear();
                invalidatedCategories.clear();
                invalidatedFull = false;
                dismissed.clear();
                snapshot.clear();
                for (const alertKey of alerts.keys()) hide(alertKey);
                session = value; save(); env.bus.trigger("AB_CHATTER_SESSION", session);
                service.poll();
            },
            clear() { service.set(null); },
            unreadChanged(broadcast = true, conversationIds = null) {
                if (polling) {
                    if (pollingIds === null) pendingFull = true;
                    else for (const id of pollingIds) pendingIds.add(id);
                }
                generation++;
                env.bus.trigger("AB_CHATTER_UNREAD", {conversation_ids: conversationIds, categories: ["unread"]});
                if (broadcast && session) channel?.postMessage({employee: session.employee_id, company: user.activeCompany.id, conversation_ids: conversationIds});
                service.poll(conversationIds);
            },
            async acknowledge(item, token) {
                if (session?.token !== token) return;
                await feedback.call(orm, "ab_crm_chatter_api", "acknowledge_alert", [], {token, conversation_id: item.conversation_id, message_ids: [...item.message_ids], target: item.website_target || null});
                if (session?.token === token) service.unreadChanged(true, [item.conversation_id]);
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
            async poll(conversationIds = null) {
                if (company !== user.activeCompany.id) {
                    company = user.activeCompany.id;
                    service.clear();
                }
                if (!session) return;
                if (polling) {
                    repoll = true;
                    if (conversationIds === null) pendingFull = true;
                    else for (const id of conversationIds) pendingIds.add(id);
                    if (pendingIds.size > 50) pendingFull = true;
                    return;
                }
                const token = session.token;
                const requestCompany = user.activeCompany.id;
                const version = generation;
                polling = true;
                pollingIds = conversationIds;
                try {
                    let cursor = 0;
                    let more = true;
                    const pending = new Map();
                    while (more && session?.token === token && version === generation && requestCompany === user.activeCompany.id) {
                        const result = await feedback.call(orm, "ab_crm_chatter_api", "notifications_v2", [], {token, cursor, ...(conversationIds ? {conversation_ids: conversationIds} : {})});
                        for (const item of result.items) {
                            const previous = pending.get(item.alert_key);
                            if (!previous) { pending.set(item.alert_key, item); continue; }
                            const messageIds = [...new Set([...previous.message_ids, ...item.message_ids])];
                            const latest = item.latest_message_id > previous.latest_message_id ? item : previous;
                            pending.set(item.alert_key, {...latest, message_ids: messageIds, count: messageIds.length,
                                unread_count: Math.max(previous.unread_count, item.unread_count)});
                        }
                        cursor = result.cursor;
                        more = result.has_more;
                    }
                    if (session?.token !== token || version !== generation || requestCompany !== user.activeCompany.id) return;
                    if (conversationIds === null) snapshot.clear();
                    else for (const [key, item] of snapshot) if (conversationIds.includes(item.conversation_id)) snapshot.delete(key);
                    for (const [key, item] of pending) snapshot.set(key, item);
                    const groups = groupNotificationItems([...snapshot.values()]);
                    const keys = new Set(groups.map(group => group.key));
                    for (const alertKey of alerts.keys()) if (!keys.has(alertKey)) hide(alertKey);
                    for (const group of groups) {
                        const alertKey = group.key;
                        const signature = JSON.stringify(group);
                        if (alerts.get(alertKey)?.signature === signature || dismissed.get(alertKey) === signature) continue;
                        hide(alertKey);
                        const alert = {silent: false, signature};
                        const conversations = group.conversations.map(item => ({
                            ...item, message_ids: [...item.message_ids],
                        }));
                        const unreadCount = conversations.reduce((count, item) => count + item.unread_count, 0);
                        const text = _t("You have %s unread messages", unreadCount);
                        alert.close = notification.add(text, {
                            type: "info", sticky: true, className: "ab_chatter_notification",
                            buttons: conversations.map(item => ({
                                name: _t("Open"),
                                onClick: () => service.open(item, token),
                            })),
                            onClose: () => {
                                if (alert.silent) return;
                                if (alerts.get(alertKey) === alert) alerts.delete(alertKey);
                                dismissed.set(alertKey, signature);
                            },
                        });
                        alerts.set(alertKey, alert);
                    }
                } catch (error) {
                    if (error.data?.name === "odoo.exceptions.AccessError" && session?.token === token) service.clear();
                    else feedback.report(error);
                } finally {
                    polling = false;
                    pollingIds = null;
                    if (repoll) {
                        const ids = pendingFull ? null : [...pendingIds];
                        repoll = false; pendingFull = false; pendingIds = new Set();
                        service.poll(ids);
                    }
                }
            },
        };
        if (channel) channel.onmessage = ({data}) => {
            if (session?.employee_id === data.employee && user.activeCompany.id === data.company) { service.unreadChanged(false, data.conversation_ids || null); }
        };
        const invalidate = (payload = null) => {
            if (!payload || payload.overflow || !Array.isArray(payload.conversation_ids)) invalidatedFull = true;
            else for (const id of payload.conversation_ids) if (Number.isInteger(id) && id > 0) invalidatedIds.add(id);
            for (const category of payload?.categories || []) invalidatedCategories.add(category);
            if (invalidatedIds.size > 50) invalidatedFull = true;
            if (invalidationTimer) return;
            invalidationTimer = setTimeout(() => {
                invalidationTimer = null;
                const ids = invalidatedFull ? null : [...invalidatedIds];
                const categories = [...invalidatedCategories];
                invalidatedIds = new Set(); invalidatedCategories = new Set(); invalidatedFull = false;
                if (session) {
                    env.bus.trigger('AB_CHATTER_UNREAD', {conversation_ids: ids, categories});
                    service.poll(ids);
                }
            }, 75);
        };
        busService?.subscribe('ab_chatter.invalidate', payload => {
            if (payload.company_id === user.activeCompany.id &&
                (!payload.employee_id || payload.employee_id === session?.employee_id)) {
                traceTiming('browser_notification', payload.correlation_ids || []);
                invalidate(payload);
            }
        });
        busService?.addEventListener('BUS:RECONNECT', () => invalidate());
        busService?.addEventListener('BUS:CONNECT', () => invalidate());
        busService?.start?.();
        setInterval(() => service.poll(), 5000);
        service.poll();
        return service;
    },
});
