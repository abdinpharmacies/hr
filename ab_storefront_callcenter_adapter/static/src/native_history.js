import { Component, onMounted, onWillUnmount, useState } from "@odoo/owl";
import { Message } from "@mail/core/common/message";
import { ChatWindow } from "@mail/core/common/chat_window";
import { patch } from "@web/core/utils/patch";
import { nativeKey, request } from "./native";

export class WebsiteHistory extends Component {
    static template = "ab_storefront_callcenter_adapter.WebsiteHistory";
    static props = { thread: Object };
    static components = { Message };
    setup() {
        this.state = useState({ previous: [], pending: false, review: false, unavailable: false, ended: false });
        this.cursor = 0;
        this.active = true;
        this.running = false;
        this.recover = () => this.catchUp();
        onMounted(() => {
            this.catchUp();
            this.timer = setInterval(this.recover, 5000);
            window.addEventListener("online", this.recover);
            window.addEventListener("pageshow", this.recover);
            document.addEventListener("visibilitychange", this.recover);
        });
        onWillUnmount(() => {
            this.active = false;
            clearInterval(this.timer);
            window.removeEventListener("online", this.recover);
            window.removeEventListener("pageshow", this.recover);
            document.removeEventListener("visibilitychange", this.recover);
        });
    }
    async retry() {
        const pending = JSON.parse(sessionStorage.getItem(nativeKey(this.props.thread)) || "null");
        if (pending) {
            pending.attempts = 0; pending.retryAt = 0;
            sessionStorage.setItem(nativeKey(this.props.thread), JSON.stringify(pending));
        }
        await this.catchUp();
    }
    async catchUp() {
        if (!this.active || this.running || document.hidden) return;
        this.running = true;
        const thread = this.props.thread;
        try {
            await thread.abEnsureWebsiteIdentity();
            const pending = JSON.parse(sessionStorage.getItem(nativeKey(thread)) || "null");
            this.state.pending = Boolean(pending);
            this.state.review = pending?.attempts >= 8;
            this.state.ended = pending?.failure === 'ended';
            if (pending && !this.state.review) {
                const message = await thread.post(pending.body, {}, { abAutomatic: true });
                if (message && String(thread.composer.composerHtml) === pending.body &&
                    JSON.stringify(thread.composer.attachments.map(file => file.id).sort((a, b) => a - b)) === JSON.stringify((pending.attachments || []).map(file => file.id).sort((a, b) => a - b))) thread.composer.clear();
            }
            let more;
            do {
                const result = await request("/storefront-callcenter/native/history", { channel_id: thread.id, after: this.cursor });
                if (!this.active || this.props.thread !== thread) return;
                this.state.ended = Boolean(result.closed);
                thread.store.insert(result.store_data);
                for (const id of result.message_ids) {
                    const message = thread.store["mail.message"].get(id);
                    if (!thread.messages.some(row => row.id === id)) thread.messages.add(message);
                }
                const existing = new Set(this.state.previous.map(message => message.id));
                this.state.previous.push(...result.previous.filter(message => !existing.has(message.id)).map(message => thread.store["mail.message"].get(message.id)));
                this.cursor = result.cursor;
                more = result.has_more;
            } while (more && this.active);
            this.state.unavailable = false;
            this.state.pending = Boolean(sessionStorage.getItem(nativeKey(thread)));
        } catch { this.state.unavailable = true; }
        finally { this.running = false; }
    }
}

patch(ChatWindow, { components: { ...ChatWindow.components, WebsiteHistory } });
