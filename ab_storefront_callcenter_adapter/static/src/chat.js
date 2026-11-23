import { _t, translationIsReady } from "@web/core/l10n/translation";

export function createSubmission(storage, key, body) {
    const existing = JSON.parse(storage.getItem(key) || "null");
    if (existing) return existing;
    const submission = { body, id: crypto.randomUUID() };
    storage.setItem(key, JSON.stringify(submission));
    return submission;
}

export function acknowledgeSubmission(storage, key, id) {
    const existing = JSON.parse(storage.getItem(key) || "null");
    if (existing?.id === id) storage.removeItem(key);
}

export function startChat(root) {
    const form = root.querySelector("form");
    const input = form.elements.body;
    const history = root.querySelector("[data-chat-history]");
    const status = root.querySelector("[data-chat-status]");
    const scope = `${location.origin}:${root.dataset.orderUuid || form.action}`;
    const pendingKey = `ab.website.pending:${scope}`;
    const draftKey = `ab.website.draft:${scope}`;
    let closed = false;
    let running = false;
    let queuedSubmissionId;
    let activeController;
    let cursor = "0";
    let accountIdentity;
    let generation = 0;
    let attempts = 0;
    let retryAt = 0;
    const rows = new Map();
    let attachments = [];
    input.value = input.value || sessionStorage.getItem(draftKey) || JSON.parse(sessionStorage.getItem(pendingKey) || "null")?.body || "";
    if (input.value) sessionStorage.setItem(draftKey, input.value);
    input.addEventListener("input", () => sessionStorage.setItem(draftKey, input.value));
    async function poll(send = false, explicit = false) {
        if (!root.isConnected || document.hidden) return;
        if (send) {
            try {
                let pending = JSON.parse(sessionStorage.getItem(pendingKey) || "null");
                if (!pending && !closed && (input.value.trim() || attachments.length)) {
                    pending = { ...createSubmission(sessionStorage, pendingKey, input.value.trim()), attachments };
                    sessionStorage.setItem(pendingKey, JSON.stringify(pending));
                }
                if (running && pending) queuedSubmissionId = pending.id;
            } catch {
                status.textContent = _t("Chat unavailable. Please retry.");
                return;
            }
        }
        if (running) return;
        if (explicit) { attempts = 0; retryAt = 0; }
        running = true;
        const epoch = generation;
        const controller = new AbortController();
        activeController = controller;
        const timeout = setTimeout(() => controller.abort(), 15000);
        let submission;
        try {
            await translationIsReady;
            submission = JSON.parse(sessionStorage.getItem(pendingKey) || "null");
            if (submission) {
                attempts = explicit ? 0 : submission.attempts || 0;
                retryAt = explicit ? 0 : submission.retryAt || 0;
                if (explicit) sessionStorage.setItem(pendingKey, JSON.stringify({ ...submission, attempts, retryAt }));
            }
            if (submission && (closed || attempts >= 8 || Date.now() < retryAt)) submission = null;
            const data = new FormData();
            data.set("csrf_token", form.elements.csrf_token.value);
            data.set("after", cursor);
            if (submission) {
                data.set("body", submission.body);
                data.set("event_uuid", submission.id);
                data.set("attachments", JSON.stringify(submission.attachments || []));
            }
            const response = await fetch(form.action, { method: "POST", credentials: "same-origin", body: data, signal: controller.signal });
            if (!response.ok) {
                if ([400, 401, 403, 410, 422].includes(response.status)) attempts = 8;
                throw new Error();
            }
            const result = await response.json();
            if (!Array.isArray(result.messages) || typeof result.cursor !== "string" || typeof result.ready !== "boolean") throw new Error();
            if (epoch !== generation || !root.isConnected) return;
            if (accountIdentity !== undefined && accountIdentity !== result.account_identity) {
                generation++;
                rows.clear(); history.replaceChildren();
                input.value = "";
                sessionStorage.removeItem(pendingKey); sessionStorage.removeItem(draftKey);
                location.reload();
                return;
            }
            accountIdentity = result.account_identity;
            const scrollTop = history.scrollTop;
            history.append(...result.messages.filter(message => !rows.has(message.key)).map(message => {
                rows.set(message.key, message);
                const row = document.createElement("p");
                row.textContent = `${message.direction === "agent" ? _t("Agent") : _t("You")}: ${message.body}`;
                for (const file of message.attachments || []) {
                    const link = document.createElement("a");
                    link.href = file.url;
                    link.textContent = file.name;
                    link.className = "d-block";
                    row.append(link);
                    const tag = file.kind === "image" ? "img" : ["voice", "audio"].includes(file.kind) ? "audio" : file.kind === "video" ? "video" : null;
                    if (tag) {
                        const preview = document.createElement(tag);
                        preview.src = file.url;
                        preview.controls = true;
                        preview.preload = "metadata";
                        preview.style.maxWidth = "100%";
                        row.append(preview);
                    }
                }
                return row;
            }));
            history.scrollTop = scrollTop;
            cursor = result.cursor;
            closed = Boolean(result.closed);
            input.disabled = !result.ready;
            const upload = root.querySelector("[data-chat-upload]");
            if (upload) upload.disabled = closed;
            form.querySelector('button[type="submit"]').disabled = !result.ready;
            status.textContent = closed ? _t("This chat has ended. Your order has been sent for delivery.") : attempts >= 8 ? _t("Message needs review. Submit again to retry.") :
                result.ready ? "" : _t("Chat unavailable. Please retry.");
            if (submission && result.acknowledged === submission.id) {
                acknowledgeSubmission(sessionStorage, pendingKey, submission.id);
                if (input.value.trim() === submission.body) { input.value = ""; sessionStorage.removeItem(draftKey); }
                attempts = 0; retryAt = 0;
                attachments = [];
                root.querySelector("[data-chat-uploads]")?.replaceChildren();
            }
            if (result.has_more) setTimeout(() => poll(), 0);
        } catch {
            if (submission) {
                attempts++;
                retryAt = Date.now() + Math.min(300000, 5000 * 2 ** Math.min(7, Math.max(0, attempts - 1)));
                if (JSON.parse(sessionStorage.getItem(pendingKey) || "null")?.id === submission.id) {
                    sessionStorage.setItem(pendingKey, JSON.stringify({ ...submission, attempts, retryAt }));
                }
            }
            status.textContent = closed ? _t("This chat has ended. Your order has been sent for delivery.") : attempts >= 8 ? _t("Message needs review. Submit again to retry.") : _t("Chat unavailable. Please retry.");
        } finally {
            clearTimeout(timeout);
            running = false;
            activeController = null;
            const queuedId = queuedSubmissionId;
            queuedSubmissionId = undefined;
            if (queuedId) {
                try {
                    if (JSON.parse(sessionStorage.getItem(pendingKey) || "null")?.id === queuedId) poll(false, true);
                } catch {
                    status.textContent = _t("Chat unavailable. Please retry.");
                }
            }
        }
    }
    root.querySelector("[data-chat-upload]")?.addEventListener("change", async event => {
        for (const file of event.target.files) {
            if (attachments.length >= 4 || file.size > 20 * 1024 * 1024) {
                status.textContent = _t("Invalid website media.");
                break;
            }
            const data = new FormData();
            data.set("csrf_token", form.elements.csrf_token.value);
            data.set("ufile", file);
            try {
                const response = await fetch(form.action + "/upload", { method: "POST", credentials: "same-origin", body: data });
                if (!response.ok) throw new Error();
                const uploaded = await response.json();
                attachments.push({ id: uploaded.id, token: uploaded.token });
                const name = document.createElement("span");
                name.textContent = uploaded.name;
                root.querySelector("[data-chat-uploads]").append(name);
            } catch { status.textContent = _t("Chat unavailable. Please retry."); }
        }
        event.target.value = "";
    });
    root.querySelector("[data-chat-refresh]")?.addEventListener("click", () => poll(false));
    form.addEventListener("submit", event => { event.preventDefault(); poll(true, true); });
    poll();
    const timer = setInterval(() => {
        if (!root.isConnected) cleanup();
        else if (!document.hidden) poll();
    }, 5000);
    const recover = () => { if (!document.hidden) poll(); };
    window.addEventListener("online", recover);
    window.addEventListener("pageshow", recover);
    document.addEventListener("visibilitychange", recover);
    const hide = () => { generation++; activeController?.abort(); };
    function cleanup() {
        clearInterval(timer);
        activeController?.abort();
        window.removeEventListener("online", recover);
        window.removeEventListener("pageshow", recover);
        document.removeEventListener("visibilitychange", recover);
        window.removeEventListener("pagehide", hide);
    }
    window.addEventListener("pagehide", hide);
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => document.querySelectorAll(".ab_website_chat").forEach(startChat));
} else {
    document.querySelectorAll(".ab_website_chat").forEach(startChat);
}
