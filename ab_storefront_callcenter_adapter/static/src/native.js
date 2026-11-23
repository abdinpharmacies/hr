import { Thread } from "@mail/core/common/thread_model";
import { Composer } from "@mail/core/common/composer";
import { fields } from "@mail/core/common/record";
import { patch } from "@web/core/utils/patch";
import { rpc } from "@web/core/network/rpc";
import { _t } from "@web/core/l10n/translation";
import { user } from "@web/core/user";

export function websiteThread(thread) {
    return thread?.channel_type === "livechat" && thread.store.env.services["im_livechat.livechat"]?.options.ab_callcenter;
}

export async function request(route, params) {
    const call = rpc(route, params, { silent: true });
    let timeout;
    try {
        return await Promise.race([call, new Promise((resolve, reject) => {
            timeout = setTimeout(() => { call.abort?.(); reject(new Error(_t("Chat unavailable. Please retry."))); }, 15000);
        })]);
    } finally { clearTimeout(timeout); }
}

export function nativeKey(thread) {
    return `ab.website.native:${thread.ab_callcenter_session_uuid}`;
}

patch(Thread.prototype, {
    setup() {
        super.setup();
        this.ab_callcenter_session_uuid = fields.Attr();
        this.ab_callcenter_identity_kind = fields.Attr();
    },
    async openChatWindow(options = {}) {
        if (!websiteThread(this) || !document.body.classList.contains("ab-storefront")) return super.openChatWindow(...arguments);
        return super.openChatWindow({ ...options, bypassCompact: true });
    },
    async abEnsureWebsiteIdentity() {
        if (user.userId && this.ab_callcenter_identity_kind === "visitor" && this.store.env.services["im_livechat.livechat"]?.options.ab_callcenter_lifecycle) {
            await request("/storefront-callcenter/native/handoff", { channel_id: this.id });
            this.ab_callcenter_identity_kind = "customer";
        }
    },
    async post(body, postData = {}, extraData = {}) {
        if (!websiteThread(this)) return super.post(...arguments);
        if (this.isTransient) {
            const thread = await this.store.env.services["im_livechat.livechat"].persist(this);
            if (!thread) throw new Error(_t("Chat unavailable. Please retry."));
            await thread.isLoadedDeferred;
            try { return await thread.post(body, postData, extraData); }
            finally { thread.readyToSwapDeferred.resolve(); }
        }
        await this.abEnsureWebsiteIdentity();
        const key = nativeKey(this);
        let submission = JSON.parse(sessionStorage.getItem(key) || "null");
        const attachments = (postData.attachments || []).map(file => ({ id: file.id, token: file.ownership_token || null })).sort((a, b) => a.id - b.id);
        if (submission && !extraData.abAutomatic && (submission.body !== String(body) || JSON.stringify(submission.attachments || []) !== JSON.stringify(attachments))) throw new Error(_t("Retry the pending message before sending another."));
        if (!submission) {
            submission = { id: crypto.randomUUID(), body: String(body), channel: this.id, attachments };
            sessionStorage.setItem(key, JSON.stringify(submission));
        }
        if (extraData.abAutomatic && (submission.attempts >= 8 || Date.now() < (submission.retryAt || 0))) return;
        try {
            const data = await request("/storefront-callcenter/native/send", {
                channel_id: submission.channel, body: submission.body, event_uuid: submission.id, attachments: submission.attachments || [],
            });
            if (data.acknowledged !== submission.id) throw new Error(_t("Chat unavailable. Please retry."));
            if (JSON.parse(sessionStorage.getItem(key) || "null")?.id === submission.id) sessionStorage.removeItem(key);
            this.store.insert(data.store_data);
            const message = this.store["mail.message"].get(data.message_id);
            this.addOrReplaceMessage(message);
            this.onNewSelfMessage(message);
            return message;
        } catch (error) {
            const name = error.data?.name || '';
            submission.failure = name.includes('SessionEnded') ? 'ended' : /AccessError|ValidationError/.test(name) ? 'rejected' : 'transient';
            submission.attempts = /AccessError|ValidationError|SessionEnded/.test(name) ? 8 : (submission.attempts || 0) + 1;
            submission.retryAt = Date.now() + Math.min(300000, 5000 * 2 ** Math.min(7, submission.attempts - 1));
            sessionStorage.setItem(key, JSON.stringify(submission));
            throw error;
        }

    },
});

patch(Composer.prototype, {
    async _sendMessage(value, postData, extraData) {
        if (!websiteThread(this.thread)) return super._sendMessage(...arguments);
        this.abWebsiteDraft = this.props.composer.composerHtml;
        this.abWebsiteAttachments = JSON.stringify(this.props.composer.attachments.map(file => file.id).sort((a, b) => a - b));
        return this.thread.post(value, postData, extraData);
    },
    clear() {
        if (websiteThread(this.thread) && this.abWebsiteDraft !== undefined && (this.props.composer.composerHtml !== this.abWebsiteDraft || JSON.stringify(this.props.composer.attachments.map(file => file.id).sort((a, b) => a - b)) !== this.abWebsiteAttachments)) return;
        return super.clear();
    },
    async sendMessage() {
        if (!websiteThread(this.thread)) return super.sendMessage(...arguments);
        try { return await super.sendMessage(...arguments); }
        catch {
            this.env.services.notification.add(_t("Chat unavailable. Your draft is saved. Please retry."), { type: "warning" });
        } finally { this.state.active = true; }
    },
});
