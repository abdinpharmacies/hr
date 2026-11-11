import {useEffect} from "@odoo/owl";
import {registry} from "@web/core/registry";
import {useService} from "@web/core/utils/hooks";
import {ConnectionLostError, ConnectionAbortedError} from "@web/core/network/rpc";
import {_t} from "@web/core/l10n/translation";

export function isConnectionFailure(error) {
    const message = typeof error === "string" ? error : error?.message || "";
    return error instanceof ConnectionLostError || /^Connection (?:to ".*" )?couldn't be established or was interrupted$/.test(message);
}

const readMethods = new Set(["bootstrap", "notifications", "contact_search", "contact_accounts", "whatsapp_templates", "search_products", "preview_branch"]);
const isRead = method => readMethods.has(method) || method.startsWith("workspace_") && method !== "workspace_acknowledge" || method.startsWith("action_preview_");

export const chatterFeedbackService = {
    dependencies: ["notification", "localization"],
    start(env, {notification}) {
        const notices = new Map();
        const failedReads = new Set();
        let disconnected = false;
        let closeConnection;
        const service = {
            notify(message, options = {}) {
                if (!message) return;
                const key = options.key || `${options.type || "info"}:${String(message)}`;
                if (notices.has(key)) return notices.get(key);
                const notificationOptions = {...options};
                delete notificationOptions.key;
                const close = notification.add(message, {type: "info", sticky: true, className: "ab_chatter_feedback", ...notificationOptions,
                    onClose: () => { notices.delete(key); options.onClose?.(); }});
                notices.set(key, close);
                return close;
            },
            report(error) {
                if (error instanceof ConnectionAbortedError || error === "XmlHttpRequestError abort") return;
                if (isConnectionFailure(error)) {
                    if (!disconnected) {
                        disconnected = true;
                        closeConnection = service.notify(_t("Connection to Odoo was lost. Reconnecting… Your drafts are kept. Check the result before retrying an action."),
                            {type: "warning", key: "connection"});
                    }
                    return;
                }
                service.notify(typeof error === "string" || error instanceof String ? error : error?.data?.message || error?.message || _t("Operation failed."), {type: "danger"});
            },
            async call(orm, model, method, args = [], kwargs = {}) {
                const route = `${model}/${method}`;
                const read = isRead(method);
                try {
                    const result = await (read && orm.silent || orm).call(model, method, args, kwargs);
                    failedReads.delete(route);
                    if (disconnected && read && !failedReads.size) {
                        disconnected = false;
                        closeConnection?.();
                        closeConnection = null;
                        service.notify(_t("Connection to Odoo restored."), {type: "success", key: "connection-restored"});
                    }
                    return result;
                } catch (error) {
                    if (isConnectionFailure(error)) {
                        if (["workspace_customer_inbox", "notifications"].includes(method)) failedReads.add(route);
                        service.report(error);
                    }
                    throw error;
                }
            },
        };
        return service;
    },
};

registry.category("services").add("ab_chatter_feedback", chatterFeedbackService);

export function useChatterFeedback(component) {
    const feedback = useService("ab_chatter_feedback");
    useEffect(() => {
        if (component.state.error) feedback.report(component.state.error);
    }, () => [component.state.error]);
    return feedback;
}

export function useChatterNotice(getNotice, dependencies) {
    const notification = useService("notification");
    useEffect(() => {
        const notice = getNotice();
        if (!notice?.message) return;
        const {message, onClose, ...options} = notice;
        let silent = false;
        const notificationOptions = {...options};
                delete notificationOptions.key;
                const close = notification.add(message, {type: "info", sticky: true, className: "ab_chatter_feedback", ...notificationOptions,
            onClose: () => { if (!silent) onClose?.(); }});
        return () => { silent = true; close(); };
    }, dependencies);
}

export function feedbackError(component, error) {
    component.feedback?.report(error);
    return typeof error === "string" || error instanceof String ? error : error?.data?.message || error?.message || _t("Operation failed.");
}
