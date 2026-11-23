import { SavedReplies } from "@ab_crm_sales_workspace/templates";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { SalesWorkspace } from "@ab_crm_sales_workspace/workspace";

patch(SalesWorkspace.prototype, {
    reply(message) {
        super.reply(message);
        if (this.state.detail?.provider === "website" && this.state.replyTo?.id === message.id) {
            this.state.replyTo.website_target = message.website_target;
            this.state.replyTo.website_origin = message.website_origin;
            this.state.replyTo.website_origin_kind = message.website_origin_kind;
        }
    },
    templates() {
        if (this.state.detail?.provider !== "website") return super.templates();
        const conversation = this.state.detail;
        const version = this.navigationVersion;
        this.dialog.add(SavedReplies, {
            call: this.call.bind(this), conversation,
            insert: text => {
                if (this.destroyed || version !== this.navigationVersion || this.state.detail?.id !== conversation.id) return;
                if (text.length > 4096) {
                    this.state.error = _t("Replies must contain between 1 and 4096 characters.");
                    return;
                }
                this.state.reply = text;
                this.rememberDraft();
            },
        });
    },
    get replyMethod() {
        return this.state.detail?.provider === "website" ? "website_action_reply" : super.replyMethod;
    },
    get sendDisabledReason() {
        const reason = super.sendDisabledReason;
        if (this.state.detail?.provider === "website" && reason === _t("Media captions must not exceed 1024 characters.")) {
            return this.state.reply.length <= 4096 ? "" : _t("Replies must contain between 1 and 4096 characters.");
        }
        return reason;
    },
    chooseAttachment(category) {
        if (this.state.detail?.provider !== "website") return super.chooseAttachment(category);
        this.fileConversationId = this.state.detail.id;
        this.fileTargetKey = this.draftKey(this.state.detail.id);
        this.filesRef.el.accept = category === "media" ? "image/jpeg,image/png,image/webp,image/gif,video/mp4,video/webm" : category === "music" ? "audio/*" : "*/*";
        this.state.attachmentMenu = false;
        this.filesRef.el.click();
    },
    async attachFiles(files, kind = false, duration = 0) {
        if (this.state.detail?.provider !== "website") return super.attachFiles(files, kind, duration);
        const id = this.state.detail.id;
        const targetKey = this.draftKey(id);
        if (this.fileTargetKey && this.fileTargetKey !== targetKey) return;
        this.state.preparing++;
        try {
            for (const file of files) {
                if (this.state.attachments.length >= 4 || file.size > 20 * 1024 * 1024 || !file.size) throw new Error(_t("Invalid website media."));
                const data = await new Promise((resolve, reject) => {
                    const reader = new FileReader();
                    reader.onload = () => resolve(reader.result.split(",")[1]);
                    reader.onerror = reject;
                    reader.readAsDataURL(file);
                });
                if (this.destroyed || this.state.navigating || this.state.detail?.id !== id || this.draftKey(id) !== targetKey || !this.state.detail.owned) return;
                const mime = file.type.split(";")[0] || "application/octet-stream";
                const mediaKind = kind || (["image/jpeg", "image/png", "image/gif", "image/webp"].includes(mime) ? "image" : mime.startsWith("audio/") ? "audio" : ["video/mp4", "video/webm"].includes(mime) ? "video" : "document");
                const url = URL.createObjectURL(file);
                this.mediaUrls.add(url);
                this.state.attachments.push({ name: file.name, mimetype: mime, size: file.size, duration, kind: mediaKind, data, url });
            }
        } catch (error) { this.state.error = error.message; }
        finally { this.state.preparing--; }
    },
    async send() {
        if (this.state.detail?.provider !== "website") return super.send();
        if (this.sendDisabledReason) return;
        await this.run(async () => {
            const id = this.state.detail.id;
            const attachments = this.state.attachments.map(({url, ...item}) => item);
            const content = JSON.stringify({ body: this.state.reply, attachments, reply: this.state.replyTo?.id || false });
            this.rememberDraft();
            const draft = this.drafts.get(this.draftKey(id));
            let pending = draft.websiteSubmission;
            if (pending && pending.content !== content) throw new Error(_t("Retry the pending message before sending another."));
            if (!pending) {
                const latest = [...this.state.detail.messages].reverse().find(message => message.direction === "in" && message.item_type !== "information" && message.actions.reply?.enabled);
                pending = { uuid: crypto.randomUUID(), content, reply: this.state.replyTo?.id || latest?.id || false,
                    target: this.state.replyTo?.website_target || latest?.website_target || this.state.detail.website_target };
                draft.websiteSubmission = pending;
            }
            pending.uploads ||= [];
            for (let index = pending.uploads.length; index < attachments.length; index++) {
                const {data, ...metadata} = attachments[index];
                const raw = Uint8Array.from(atob(data), character => character.charCodeAt(0));
                const form = new FormData();
                form.set("csrf_token", odoo.csrf_token);
                form.set("conversation_id", id);
                form.set("token", this.state.token);
                form.set("target", JSON.stringify(pending.target));
                form.set("submission_uuid", pending.uuid);
                form.set("position", index);
                if (pending.reply) form.set("reply_id", pending.reply);
                form.set("metadata", JSON.stringify(metadata));
                form.set("ufile", new Blob([raw], {type: metadata.mimetype}), metadata.name);
                const controller = new AbortController();
                const timeout = setTimeout(() => controller.abort(), 60000);
                try {
                    const response = await fetch("/crm/website/media/upload", {method: "POST", credentials: "same-origin", body: form, signal: controller.signal});
                    if (!response.ok) throw new Error(_t("Website media is unavailable."));
                    pending.uploads.push(await response.json());
                } finally { clearTimeout(timeout); }
            }
            await this.call("ab_crm_conversation", "website_action_reply", [[id], this.state.reply], {
                attachments: pending.uploads, reply_id: pending.reply, submission_uuid: pending.uuid, target: pending.target,
            });
            delete draft.websiteSubmission;
            this.clearAttachments();
            this.state.replyTo = null;
            this.state.reply = "";
            this.rememberDraft();
            await this.refresh();
        });
    },
    rememberDraft() {
        const id = this.state.detail?.id;
        const pending = this.drafts.get(this.draftKey(id))?.websiteSubmission;
        super.rememberDraft();
        if (pending && this.drafts.has(this.draftKey(id))) this.drafts.get(this.draftKey(id)).websiteSubmission = pending;
    },
    get replyDestinationKwargs() {
        return this.state.detail?.provider === "website" ? {} : super.replyDestinationKwargs;
    },
});
