import { _t } from "@web/core/l10n/translation";

function startChat(root) {
    const form = root.querySelector("form");
    const history = root.querySelector("[data-chat-history]");
    const status = root.querySelector("[data-chat-status]");
    let pending = false;
    let submission = null;
    async function poll(body = "") {
        if (pending || !root.isConnected) return;
        pending = true;
        try {
            const data = new FormData();
            data.set("csrf_token", form.elements.csrf_token.value);
            data.set("body", body);
            if (body) {
                if (!submission || submission.body !== body) submission = { body, id: crypto.randomUUID() };
                data.set("event_uuid", submission.id);
            }
            const response = await fetch(form.action, { method: "POST", credentials: "same-origin", body: data });
            if (!response.ok) throw new Error();
            const result = await response.json();
            history.replaceChildren(...result.messages.map(message => {
                const row = document.createElement("p");
                row.textContent = `${message.direction === "agent" ? _t("Agent") : _t("You")}: ${message.body}`;
                return row;
            }));
            status.textContent = "";
            if (body) { form.elements.body.value = ""; submission = null; }
        } catch {
            status.textContent = _t("Chat unavailable. Please retry.");
        } finally { pending = false; }
    }
    form.addEventListener("submit", event => {
        event.preventDefault();
        const body = form.elements.body.value.trim();
        if (body) poll(body);
    });
    poll();
    const timer = setInterval(() => {
        if (!root.isConnected) clearInterval(timer);
        else if (!document.hidden) poll();
    }, 5000);
    window.addEventListener("pagehide", () => clearInterval(timer), { once: true });
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => document.querySelectorAll(".ab_website_chat").forEach(startChat));
} else {
    document.querySelectorAll(".ab_website_chat").forEach(startChat);
}
