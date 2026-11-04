/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onMounted, onWillStart, onWillUnmount, useRef, useState } from "@odoo/owl";

class AbWhatsAppDashboardAction extends Component {
    static template = "ab_whatsapp_api.WhatsAppDashboardAction";

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.fileInputRef = useRef("fileInput");
        this.messagesBoxRef = useRef("messagesBox");
        this.composerRef = useRef("composerTextarea");

        this.state = useState({
            loading: true,
            contacts: [],
            activeWaId: null,
            messages: [],
            templates: [],
            showContactModal: false,
            showTemplateModal: false,
            contactModalMode: "create",
            newContactName: "",
            newContactWaId: "",
            selectedTemplateId: null,
            submitTemplateName: "",
            submitTemplateBody: "",
            submitTemplateCategory: "UTILITY",
            submitTemplateLanguage: "en_US",
            templateParamValues: [],
            composeMessage: "",
            sendingText: false,
            sendingFile: false,
            sendingComposer: false,
            sendingReaction: false,
            sendingTemplate: false,
            syncingTemplates: false,
            submittingTemplate: false,
            showEmojiPanel: false,
            replyToMetaMessageId: null,
            editingMessageId: null,
            editMessageText: "",
            pendingFiles: [],
            openMessageMenuId: null,
            openMessageMenuTop: 0,
            openMessageMenuLeft: 0,
            isRecording: false,
            health: {
                token_configured: false,
                verify_token: "",
            },
            lastUpdated: "",
        });

        this._pollTimer = null;
        this._mediaRecorder = null;
        this._recordedChunks = [];
        this._recordStream = null;
        this._onDocumentClick = null;
        this._onDocumentKeydown = null;
        this._onMessagesScroll = null;
        this._stickToBottom = true;

        onWillStart(async () => {
            await this.loadInitial();
        });

        onMounted(() => {
            this._onDocumentClick = () => {
                this.state.openMessageMenuId = null;
            };
            document.addEventListener("click", this._onDocumentClick);
            this._onDocumentKeydown = (event) => {
                if (event?.key !== "Escape") {
                    return;
                }
                const closed = this.closePopups();
                if (!closed) {
                    return;
                }
                event.preventDefault();
                event.stopPropagation();
            };
            document.addEventListener("keydown", this._onDocumentKeydown);
            this._onMessagesScroll = () => {
                const box = this.messagesBoxRef.el;
                if (!box) {
                    return;
                }
                this._stickToBottom = this.isNearBottom(box);
                this.state.openMessageMenuId = null;
            };
            if (this.messagesBoxRef.el) {
                this.messagesBoxRef.el.addEventListener("scroll", this._onMessagesScroll);
            }
            this._pollTimer = setInterval(() => {
                this.safe(async () => {
                    await this.pollRefresh();
                });
            }, 4000);
            this.scrollMessagesToBottom(true);
            this.focusComposer();
        });

        onWillUnmount(() => {
            if (this._pollTimer) {
                clearInterval(this._pollTimer);
                this._pollTimer = null;
            }
            if (this._onDocumentClick) {
                document.removeEventListener("click", this._onDocumentClick);
                this._onDocumentClick = null;
            }
            if (this._onDocumentKeydown) {
                document.removeEventListener("keydown", this._onDocumentKeydown);
                this._onDocumentKeydown = null;
            }
            if (this._onMessagesScroll && this.messagesBoxRef.el) {
                this.messagesBoxRef.el.removeEventListener("scroll", this._onMessagesScroll);
                this._onMessagesScroll = null;
            }
            this.stopRecordingTracks();
        });
    }

    get activeContact() {
        return this.state.contacts.find((item) => item.wa_id === this.state.activeWaId) || null;
    }

    get activeContactLabel() {
        const contact = this.activeContact;
        if (!contact) {
            return "No contact selected";
        }
        return (contact.name || "").trim() || contact.wa_id;
    }

    get hasActiveContact() {
        return Boolean(this.state.activeWaId);
    }

    get isEditContactMode() {
        return this.state.contactModalMode === "edit";
    }

    get selectedTemplate() {
        const selectedId = Number(this.state.selectedTemplateId || 0);
        if (!selectedId) {
            return null;
        }
        return (this.state.templates || []).find((item) => item.id === selectedId) || null;
    }

    contactModalTitle() {
        return this.isEditContactMode ? "Edit Contact" : "Add Contact";
    }

    contactSaveButtonLabel() {
        return this.isEditContactMode ? "Save Changes" : "Save Contact";
    }

    get renderMessages() {
        return (this.state.messages || []).filter((item) => !this.isReactionMessage(item));
    }

    get hasRenderableMessages() {
        return this.renderMessages.length > 0;
    }

    get replyTargetMessage() {
        if (!this.state.replyToMetaMessageId) {
            return null;
        }
        return this.findMessageByMetaId(this.state.replyToMetaMessageId);
    }

    emojiChoices() {
        return [
            "\uD83D\uDE00",
            "\uD83D\uDE02",
            "\uD83D\uDE0D",
            "\uD83D\uDC4D",
            "\uD83D\uDE4F",
            "\uD83D\uDD25",
            "\u2705",
            "\uD83C\uDF89",
            "\u2764\uFE0F",
            "\uD83D\uDE22",
            "\uD83D\uDE2E",
            "\uD83D\uDC4F",
        ];
    }

    pendingFilesLabel() {
        const count = (this.state.pendingFiles || []).length;
        if (!count) {
            return "";
        }
        if (count === 1) {
            return this.state.pendingFiles[0]?.name || "1 attachment";
        }
        return `${count} attachments`;
    }

    contactButtonClass(contact) {
        const isActive = contact?.wa_id === this.state.activeWaId;
        return isActive ? "abwa-contact active" : "abwa-contact";
    }

    bubbleWrapClass(message) {
        return this.isOutgoing(message) ? "abwa-bubble-wrap outgoing" : "abwa-bubble-wrap incoming";
    }

    bubbleClass(message) {
        return this.isOutgoing(message) ? "abwa-bubble outgoing" : "abwa-bubble incoming";
    }

    isOutgoing(message) {
        return (message?.direction || "").toLowerCase() === "outgoing";
    }

    isReactionMessage(message) {
        return (message?.message_type || "").toLowerCase() === "reaction";
    }

    isMessageDeleted(message) {
        return Boolean(message?.is_deleted) || (message?.message_type || "") === "deleted";
    }

    canReply(message) {
        return Boolean(message?.meta_message_id) && !this.isReactionMessage(message);
    }

    canReact(message) {
        return Boolean(message?.meta_message_id) && !this.isReactionMessage(message);
    }

    canEdit(message) {
        return this.isOutgoing(message) && (message?.message_type || "") === "text" && !this.isMessageDeleted(message);
    }

    canDelete(message) {
        return !this.isMessageDeleted(message);
    }

    hasMessageActions(message) {
        return this.canReply(message) || this.canReact(message) || this.canEdit(message) || this.canDelete(message);
    }

    isMessageMenuOpen(message) {
        return this.state.openMessageMenuId === message?.id;
    }

    messageMenuStyle(message) {
        if (!this.isMessageMenuOpen(message)) {
            return "";
        }
        return `top:${this.state.openMessageMenuTop}px;left:${this.state.openMessageMenuLeft}px;`;
    }

    messageById(messageId) {
        return (this.state.messages || []).find((item) => item.id === messageId) || null;
    }

    estimateMessageMenuHeight(messageId) {
        const message = this.messageById(messageId);
        if (!message) {
            return 160;
        }
        let actionCount = 0;
        if (this.canReply(message)) {
            actionCount += 1;
        }
        if (this.canReact(message)) {
            actionCount += 1;
        }
        if (this.canEdit(message)) {
            actionCount += 1;
        }
        if (this.canDelete(message)) {
            actionCount += 1;
        }
        return Math.max(42, actionCount * 34 + 8);
    }

    isEditing(message) {
        return this.state.editingMessageId === message?.id;
    }

    isImageMessage(message) {
        return Boolean(message?.media_id) && (message?.message_type || "") === "image";
    }

    isAudioMessage(message) {
        return Boolean(message?.media_id) && (message?.message_type || "") === "audio";
    }

    isVideoMessage(message) {
        return Boolean(message?.media_id) && (message?.message_type || "") === "video";
    }

    hasDownloadableMedia(message) {
        return Boolean(message?.media_id) && !this.isImageMessage(message) && !this.isAudioMessage(message) && !this.isVideoMessage(message);
    }

    mediaUrl(message, forceDownload = false) {
        if (!message?.id || !message?.media_id) {
            return "";
        }
        return forceDownload
            ? `/ab_whatsapp_api/media/${message.id}?download=1`
            : `/ab_whatsapp_api/media/${message.id}`;
    }

    messageTextParts(message) {
        const rawText = (message?.text_content || "").toString();
        if (!rawText) {
            return [];
        }

        const regex = /(?:https?:\/\/|www\.)[^\s<]+/gi;
        const parts = [];
        let cursor = 0;
        let match;
        let index = 0;

        while ((match = regex.exec(rawText)) !== null) {
            const matched = match[0] || "";
            const start = match.index;
            const end = start + matched.length;
            if (start > cursor) {
                parts.push({
                    key: `${message?.id || 0}-txt-${index}`,
                    is_link: false,
                    text: rawText.slice(cursor, start),
                    href: "",
                });
                index += 1;
            }

            const cleaned = this.trimTrailingLinkPunctuation(matched);
            const candidate = cleaned.core;
            const href = candidate.startsWith("http://") || candidate.startsWith("https://")
                ? candidate
                : `https://${candidate}`;

            if (candidate) {
                parts.push({
                    key: `${message?.id || 0}-lnk-${index}`,
                    is_link: true,
                    text: candidate,
                    href: href,
                });
                index += 1;
            }
            if (cleaned.trailing) {
                parts.push({
                    key: `${message?.id || 0}-txt-${index}`,
                    is_link: false,
                    text: cleaned.trailing,
                    href: "",
                });
                index += 1;
            }
            cursor = end;
        }

        if (cursor < rawText.length) {
            parts.push({
                key: `${message?.id || 0}-txt-${index}`,
                is_link: false,
                text: rawText.slice(cursor),
                href: "",
            });
        }
        return parts;
    }

    trimTrailingLinkPunctuation(value) {
        let core = (value || "").trim();
        let trailing = "";
        while (core && /[),.;!?]$/.test(core)) {
            trailing = `${core.slice(-1)}${trailing}`;
            core = core.slice(0, -1);
        }
        return { core, trailing };
    }

    reactionLine(message) {
        const reactions = this.reactionsForMessage(message);
        return reactions.join(" ");
    }

    reactionsForMessage(message) {
        const targetMetaId = (message?.meta_message_id || "").trim();
        if (!targetMetaId) {
            return [];
        }
        const byActor = {};
        for (const item of this.state.messages || []) {
            if (!this.isReactionMessage(item)) {
                continue;
            }
            if ((item?.reaction_target_meta_message_id || "").trim() !== targetMetaId) {
                continue;
            }
            const actor = this.isOutgoing(item) ? "outgoing" : `incoming:${item.wa_id || "contact"}`;
            const emoji = (item?.text_content || "").trim();
            if (emoji) {
                byActor[actor] = emoji;
            } else {
                delete byActor[actor];
            }
        }
        return Object.values(byActor);
    }

    hasReactions(message) {
        return this.reactionsForMessage(message).length > 0;
    }

    repliedMessage(message) {
        const parentMetaId = (message?.reply_to_meta_message_id || "").trim();
        if (!parentMetaId) {
            return null;
        }
        return this.findMessageByMetaId(parentMetaId);
    }

    findMessageByMetaId(metaId) {
        const target = (metaId || "").trim();
        if (!target) {
            return null;
        }
        return (this.state.messages || []).find((item) => (item?.meta_message_id || "").trim() === target) || null;
    }

    replySnippet(message) {
        if (!message) {
            return "Original message";
        }
        if (message.text_content) {
            return message.text_content;
        }
        if (message.media_filename) {
            return `[${message.message_type}] ${message.media_filename}`;
        }
        if (message.message_type) {
            return `[${message.message_type}]`;
        }
        return "Original message";
    }

    showOutgoingStatus(message) {
        return this.isOutgoing(message);
    }

    statusBadgeClass(message) {
        return `abwa-status ${this.statusClass(message)}`;
    }

    recordButtonTitle() {
        return this.state.isRecording ? "Stop Recording" : "Record Audio";
    }

    recordButtonClass() {
        return this.state.isRecording ? "abwa-action-btn secondary recording" : "abwa-action-btn secondary";
    }

    recordIconClass() {
        return this.state.isRecording ? "fa fa-stop" : "fa fa-microphone";
    }

    modalClass() {
        return this.state.showContactModal ? "abwa-modal" : "abwa-modal hidden";
    }

    templateModalClass() {
        return this.state.showTemplateModal ? "abwa-modal" : "abwa-modal hidden";
    }

    templateOptionLabel(template) {
        const name = (template?.name || "").trim() || "Unnamed";
        const language = (template?.language || "").trim() || "en_US";
        const status = (template?.status || "UNKNOWN").toUpperCase();
        return `${name} [${language}] - ${status}`;
    }

    canSubmitTemplate() {
        return Boolean((this.state.submitTemplateName || "").trim() && (this.state.submitTemplateBody || "").trim());
    }

    selectedTemplatePlaceholderIndexes() {
        const template = this.selectedTemplate;
        const indexes = template?.placeholder_indexes;
        if (!Array.isArray(indexes)) {
            return [];
        }
        return indexes
            .map((value) => Number(value))
            .filter((value) => Number.isInteger(value) && value > 0)
            .sort((a, b) => a - b);
    }

    templateParamFields() {
        return this.selectedTemplatePlaceholderIndexes().map((placeholderIndex, position) => ({
            key: `${placeholderIndex}-${position}`,
            placeholderIndex,
            position,
        }));
    }

    templateParamValue(position) {
        return this.state.templateParamValues?.[position] || "";
    }

    templateParamLabel(placeholderIndex) {
        return `Value for {{${placeholderIndex}}}`;
    }

    syncTemplateParameterState() {
        const indexes = this.selectedTemplatePlaceholderIndexes();
        const currentValues = Array.isArray(this.state.templateParamValues)
            ? [...this.state.templateParamValues]
            : [];
        this.state.templateParamValues = indexes.map((_, position) => currentValues[position] || "");
    }

    onTemplateParamInput(ev) {
        const position = Number(ev?.currentTarget?.dataset?.position ?? -1);
        if (!Number.isInteger(position) || position < 0) {
            return;
        }
        const value = ev?.currentTarget?.value || "";
        const currentValues = Array.isArray(this.state.templateParamValues)
            ? [...this.state.templateParamValues]
            : [];
        currentValues[position] = value;
        this.state.templateParamValues = currentValues;
    }

    onTemplateSelectionChange(ev) {
        const selectedId = Number(ev?.currentTarget?.value || 0);
        this.state.selectedTemplateId = selectedId || null;
        this.syncTemplateParameterState();
    }

    canSendSelectedTemplate() {
        const template = this.selectedTemplate;
        if (!template || !template.is_sendable) {
            return false;
        }
        const requiredIndexes = this.selectedTemplatePlaceholderIndexes();
        if (!requiredIndexes.length) {
            return true;
        }
        const values = this.state.templateParamValues || [];
        if (values.length < requiredIndexes.length) {
            return false;
        }
        return requiredIndexes.every((_, position) => Boolean((values[position] || "").trim()));
    }

    focusComposer() {
        if (
            !this.state.activeWaId ||
            this.state.showContactModal ||
            this.state.showTemplateModal ||
            this.state.editingMessageId
        ) {
            return;
        }
        requestAnimationFrame(() => {
            const input = this.composerRef.el;
            if (!input) {
                return;
            }
            if (document.activeElement === input) {
                return;
            }
            input.focus({ preventScroll: true });
            const cursor = (input.value || "").length;
            input.setSelectionRange(cursor, cursor);
        });
    }

    closePopups() {
        let closed = false;
        if (this.state.openMessageMenuId) {
            this.state.openMessageMenuId = null;
            closed = true;
        }
        if (this.state.showEmojiPanel) {
            this.state.showEmojiPanel = false;
            closed = true;
        }
        if (this.state.showContactModal) {
            this.state.showContactModal = false;
            closed = true;
        }
        if (this.state.showTemplateModal) {
            this.state.showTemplateModal = false;
            closed = true;
        }
        if (closed) {
            this.focusComposer();
        }
        return closed;
    }

    focusMessageMenu(messageId) {
        requestAnimationFrame(() => {
            const target = document.querySelector(
                `.o_ab_whatsapp_dashboard .abwa-message-menu[data-menu-message-id="${messageId}"] .abwa-message-menu-item`
            );
            if (!target || typeof target.focus !== "function") {
                return;
            }
            target.focus({ preventScroll: true });
        });
    }

    async safe(fn) {
        try {
            await fn();
        } catch (error) {
            const rpcMessage = error?.data?.message || error?.data?.arguments?.[0] || "";
            let message = rpcMessage || error?.message || "Unexpected error.";
            if (message === "Odoo Server Error") {
                const debug = (error?.data?.debug || "").split("\n").map((line) => line.trim()).filter(Boolean);
                const candidate = debug.reverse().find((line) => !line.startsWith("Traceback"));
                if (candidate) {
                    message = candidate;
                }
            }
            this.notification.add(message, { type: "danger" });
        }
    }

    async loadInitial() {
        this.state.loading = true;
        try {
            await this.refreshHealth();
            await this.loadContacts();
            if (this.state.activeWaId) {
                await this.loadConversation(true);
            }
        } finally {
            this.state.loading = false;
        }
    }

    async pollRefresh() {
        await this.loadContacts();
        if (this.state.activeWaId) {
            await this.loadConversation();
        }
    }

    async refreshHealth() {
        this.state.health = await this.orm.call("ab.whatsapp.service", "api_health", []);
    }

    async loadContacts() {
        const contacts = await this.orm.call("ab.whatsapp.service", "api_list_contacts", [], { limit: 500 });
        this.state.contacts = contacts || [];

        if (!this.state.activeWaId && this.state.contacts.length) {
            this.state.activeWaId = this.state.contacts[0].wa_id;
        } else if (
            this.state.activeWaId &&
            !this.state.contacts.some((item) => item.wa_id === this.state.activeWaId)
        ) {
            this.state.activeWaId = this.state.contacts[0]?.wa_id || null;
        }
        this.setUpdatedNow();
    }

    async loadConversation(forceScrollToBottom = false) {
        if (!this.state.activeWaId) {
            this.state.messages = [];
            return;
        }
        try {
            await this.orm.call("ab.whatsapp.service", "api_mark_incoming_read", [], {
                wa_id: this.state.activeWaId,
                limit: 100,
            });
        } catch {
            // Keep conversation loading even if read-receipt sync fails.
        }
        const box = this.messagesBoxRef.el;
        const wasNearBottom = box ? this.isNearBottom(box) : true;
        const messages = await this.orm.call(
            "ab.whatsapp.service",
            "api_list_conversation",
            [],
            { wa_id: this.state.activeWaId, limit: 350 }
        );
        this.state.messages = messages || [];
        this.queueScrollToBottom(forceScrollToBottom || wasNearBottom || this._stickToBottom);
        this.setUpdatedNow();
        this.focusComposer();
    }

    async selectContact(waId) {
        if (!waId) {
            return;
        }
        this.state.activeWaId = waId;
        this._stickToBottom = true;
        this.clearComposerState();
        await this.loadConversation(true);
    }

    clearComposerState() {
        this.state.replyToMetaMessageId = null;
        this.state.editingMessageId = null;
        this.state.openMessageMenuId = null;
        this.state.editMessageText = "";
        this.state.pendingFiles = [];
        this.state.showEmojiPanel = false;
        this.state.composeMessage = "";
        if (this.fileInputRef.el) {
            this.fileInputRef.el.value = "";
        }
    }

    openContactModal() {
        this.state.contactModalMode = "create";
        this.state.newContactName = "";
        this.state.newContactWaId = "";
        this.state.showContactModal = true;
    }

    openEditContactModal() {
        const contact = this.activeContact;
        if (!contact) {
            this.notification.add("Select a contact first.", { type: "warning" });
            return;
        }
        this.state.contactModalMode = "edit";
        this.state.newContactName = contact.name || "";
        this.state.newContactWaId = contact.wa_id || "";
        this.state.showContactModal = true;
    }

    closeContactModal() {
        this.state.showContactModal = false;
    }

    onModalBackdropClick() {
        this.closeContactModal();
    }

    closeTemplateModal() {
        this.state.showTemplateModal = false;
        this.state.templateParamValues = [];
        this.focusComposer();
    }

    onTemplateModalBackdropClick() {
        this.closeTemplateModal();
    }

    async onTemplateButtonClick() {
        await this.safe(async () => {
            if (!this.state.activeWaId) {
                this.notification.add("Select a contact first.", { type: "warning" });
                return;
            }
            this.state.showTemplateModal = true;
            this.state.showEmojiPanel = false;
            this.state.submitTemplateCategory = this.state.submitTemplateCategory || "UTILITY";
            this.state.submitTemplateLanguage = this.state.submitTemplateLanguage || "en_US";
            await this.loadTemplates({ sync: true, silent: true });
            this.syncTemplateParameterState();
        });
    }

    async onSubmitTemplateClick() {
        await this.safe(async () => {
            await this.submitTemplate();
        });
    }

    async onRefreshTemplatesClick() {
        await this.safe(async () => {
            await this.loadTemplates({ sync: true });
        });
    }

    async onSendTemplateClick() {
        await this.safe(async () => {
            await this.sendSelectedTemplate();
        });
    }

    noop() {}

    async onRefreshClick() {
        await this.safe(async () => {
            await this.pollRefresh();
            this.focusComposer();
        });
    }

    async onContactClick(ev) {
        const waId = ev?.currentTarget?.dataset?.waId || "";
        await this.safe(async () => {
            this.state.openMessageMenuId = null;
            await this.selectContact(waId);
        });
    }

    async onSendClick() {
        await this.safe(async () => {
            await this.sendComposer();
        });
    }

    onAttachClick() {
        if (this.fileInputRef.el) {
            this.fileInputRef.el.click();
        }
    }

    async onSaveContactClick() {
        await this.safe(async () => {
            await this.saveContact();
        });
    }

    async onEditContactClick() {
        this.openEditContactModal();
    }

    async onDeleteContactClick() {
        if (!this.state.activeWaId) {
            this.notification.add("Select a contact first.", { type: "warning" });
            return;
        }
        const label = this.activeContactLabel;
        if (!window.confirm(`Delete contact "${label}" and all related messages?`)) {
            return;
        }
        await this.safe(async () => {
            await this.orm.call("ab.whatsapp.service", "api_delete_contact", [], {
                wa_id: this.state.activeWaId,
            });
            this.state.activeWaId = null;
            this.state.messages = [];
            await this.loadContacts();
            if (this.state.activeWaId) {
                await this.loadConversation();
            }
            this.notification.add("Contact deleted.", { type: "success" });
        });
    }

    onFileInputChange(ev) {
        const files = Array.from(ev?.currentTarget?.files || []).filter((item) => Boolean(item?.size));
        if (!files.length) {
            return;
        }
        this.state.pendingFiles = [...(this.state.pendingFiles || []), ...files];
        if (this.fileInputRef.el) {
            this.fileInputRef.el.value = "";
        }
    }

    onComposerPaste(ev) {
        const items = ev?.clipboardData?.items || [];
        for (const item of items) {
            if (!item?.type?.startsWith("image/")) {
                continue;
            }
            const file = item.getAsFile();
            if (!file) {
                continue;
            }
            ev.preventDefault();
            const extension = (file.type || "image/png").split("/")[1] || "png";
            const pasteFile = new File([file], `pasted-${Date.now()}.${extension}`, {
                type: file.type || "image/png",
            });
            this.state.pendingFiles = [...(this.state.pendingFiles || []), pasteFile];
            this.notification.add("Image pasted. Click Send Message to upload.", { type: "info" });
            return;
        }
    }

    onRemovePendingFileClick() {
        this.state.pendingFiles = [];
        if (this.fileInputRef.el) {
            this.fileInputRef.el.value = "";
        }
    }

    onToggleEmojiPanelClick() {
        this.state.showEmojiPanel = !this.state.showEmojiPanel;
    }

    onEmojiClick(ev) {
        const emoji = ev?.currentTarget?.dataset?.emoji || "";
        if (!emoji) {
            return;
        }
        this.state.composeMessage = `${this.state.composeMessage || ""}${emoji}`;
        this.state.showEmojiPanel = false;
    }

    onToggleMessageMenu(ev) {
        const messageId = Number(ev?.currentTarget?.dataset?.messageId || 0);
        if (!messageId) {
            this.state.openMessageMenuId = null;
            this.focusComposer();
            return;
        }
        if (this.state.openMessageMenuId === messageId) {
            this.state.openMessageMenuId = null;
            this.focusComposer();
            return;
        }

        const triggerRect = ev.currentTarget.getBoundingClientRect();
        const menuWidth = 140;
        const menuHeight = this.estimateMessageMenuHeight(messageId);
        const margin = 8;
        let left = triggerRect.right - menuWidth;
        left = Math.max(margin, Math.min(left, window.innerWidth - menuWidth - margin));

        let top = triggerRect.bottom + 6;
        if (top + menuHeight > window.innerHeight - margin) {
            top = triggerRect.top - menuHeight - 6;
        }
        top = Math.max(margin, top);

        this.state.openMessageMenuTop = Math.round(top);
        this.state.openMessageMenuLeft = Math.round(left);
        this.state.openMessageMenuId = messageId;
        this.focusMessageMenu(messageId);
    }

    onReplyClick(ev) {
        this.state.openMessageMenuId = null;
        const metaMessageId = ev?.currentTarget?.dataset?.metaMessageId || "";
        if (!metaMessageId) {
            this.notification.add("This message cannot be used as a reply target.", { type: "warning" });
            return;
        }
        this.state.replyToMetaMessageId = metaMessageId;
        this.focusComposer();
    }

    onClearReplyClick() {
        this.state.replyToMetaMessageId = null;
        this.focusComposer();
    }

    async onReactClick(ev) {
        this.state.openMessageMenuId = null;
        const metaMessageId = ev?.currentTarget?.dataset?.metaMessageId || "";
        if (!metaMessageId) {
            this.notification.add("Cannot react to this message.", { type: "warning" });
            return;
        }
        const emoji = window.prompt("Reaction emoji", "\uD83D\uDC4D");
        if (!emoji) {
            return;
        }
        await this.safe(async () => {
            await this.sendReaction(metaMessageId, emoji);
        });
    }

    onEditClick(ev) {
        this.state.openMessageMenuId = null;
        const messageId = Number(ev?.currentTarget?.dataset?.messageId || 0);
        if (!messageId) {
            return;
        }
        const message = this.state.messages.find((item) => item.id === messageId);
        if (!message) {
            return;
        }
        this.state.editingMessageId = messageId;
        this.state.editMessageText = message.text_content || "";
    }

    onCancelEditClick() {
        this.state.editingMessageId = null;
        this.state.editMessageText = "";
        this.focusComposer();
    }

    async onComposerKeydown(ev) {
        if (ev?.key !== "Enter" || ev?.shiftKey || ev?.isComposing) {
            return;
        }
        ev.preventDefault();
        await this.safe(async () => {
            await this.sendComposer();
        });
        this.focusComposer();
    }

    async onSaveEditClick(ev) {
        const messageId = Number(ev?.currentTarget?.dataset?.messageId || 0);
        if (!messageId) {
            return;
        }
        await this.safe(async () => {
            await this.orm.call("ab.whatsapp.service", "api_edit_message_local", [], {
                message_id: messageId,
                new_text: this.state.editMessageText,
            });
            this.state.editingMessageId = null;
            this.state.editMessageText = "";
            await this.loadContacts();
            await this.loadConversation();
            this.notification.add("Message edited.", { type: "success" });
        });
    }

    async onDeleteClick(ev) {
        this.state.openMessageMenuId = null;
        const messageId = Number(ev?.currentTarget?.dataset?.messageId || 0);
        if (!messageId) {
            return;
        }
        if (!window.confirm("Delete this message?")) {
            return;
        }
        await this.safe(async () => {
            await this.orm.call("ab.whatsapp.service", "api_delete_message_local", [], {
                message_id: messageId,
            });
            await this.loadContacts();
            await this.loadConversation();
            this.notification.add("Message deleted.", { type: "success" });
        });
    }

    async onRecordAudioClick() {
        await this.safe(async () => {
            if (this.state.isRecording) {
                this.stopRecording();
                return;
            }
            await this.startRecording();
        });
    }

    async startRecording() {
        if (!navigator?.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
            this.notification.add("Audio recording is not supported in this browser.", { type: "danger" });
            return;
        }

        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        const mimeType = this.pickRecorderMimeType();
        this._recordStream = stream;
        this._recordedChunks = [];

        this._mediaRecorder = mimeType
            ? new MediaRecorder(stream, { mimeType })
            : new MediaRecorder(stream);

        this._mediaRecorder.ondataavailable = (event) => {
            if (event?.data?.size) {
                this._recordedChunks.push(event.data);
            }
        };

        this._mediaRecorder.onstop = () => {
            this.handleRecordingStopped();
        };

        this._mediaRecorder.start();
        this.state.isRecording = true;
        this.notification.add("Recording started.", { type: "info" });
    }

    stopRecording() {
        if (!this._mediaRecorder || this._mediaRecorder.state === "inactive") {
            this.state.isRecording = false;
            this.stopRecordingTracks();
            return;
        }
        this._mediaRecorder.stop();
        this.state.isRecording = false;
    }

    stopRecordingTracks() {
        if (this._recordStream) {
            for (const track of this._recordStream.getTracks()) {
                track.stop();
            }
        }
        this._recordStream = null;
    }

    pickRecorderMimeType() {
        const candidates = [
            "audio/ogg;codecs=opus",
            "audio/webm;codecs=opus",
            "audio/webm",
        ];
        for (const item of candidates) {
            if (MediaRecorder.isTypeSupported(item)) {
                return item;
            }
        }
        return "";
    }

    handleRecordingStopped() {
        this.stopRecordingTracks();

        if (!this._recordedChunks.length) {
            this.notification.add("No audio recorded.", { type: "warning" });
            return;
        }

        const mimeType = this._mediaRecorder?.mimeType || "audio/ogg";
        const blob = new Blob(this._recordedChunks, { type: mimeType });
        const extension = mimeType.includes("webm") ? "webm" : "ogg";
        const audioFile = new File([blob], `recording-${Date.now()}.${extension}`, {
            type: mimeType,
        });
        this.state.pendingFiles = [...(this.state.pendingFiles || []), audioFile];
        this.notification.add("Audio ready. Click Send Message.", { type: "success" });
    }

    async saveContact() {
        const waId = (this.state.newContactWaId || "").trim();
        if (!waId) {
            this.notification.add("WhatsApp number is required.", { type: "warning" });
            return;
        }
        const name = (this.state.newContactName || "").trim();
        const targetWaId = this.isEditContactMode && this.state.activeWaId ? this.state.activeWaId : waId;
        const contact = await this.orm.call(
            "ab.whatsapp.service",
            "api_upsert_contact",
            [],
            {
                wa_id: targetWaId,
                name: name || null,
            }
        );
        this.closeContactModal();
        this.notification.add(this.isEditContactMode ? "Contact updated." : "Contact saved.", { type: "success" });
        await this.loadContacts();
        if (contact?.wa_id) {
            await this.selectContact(contact.wa_id);
        }
    }

    async submitTemplate() {
        const name = (this.state.submitTemplateName || "").trim();
        const body = (this.state.submitTemplateBody || "").trim();
        const category = (this.state.submitTemplateCategory || "UTILITY").trim().toUpperCase() || "UTILITY";
        const language = (this.state.submitTemplateLanguage || "en_US").trim() || "en_US";

        if (!name || !body) {
            this.notification.add("Template name and body are required.", { type: "warning" });
            return;
        }

        this.state.submittingTemplate = true;
        try {
            const result = await this.orm.call("ab.whatsapp.service", "api_submit_template", [], {
                name: name,
                body: body,
                category: category,
                language: language,
            });

            const submittedStatus = (result?.status || "PENDING").toUpperCase();
            if (result?.template) {
                const incoming = result.template;
                this.state.templates = [
                    incoming,
                    ...(this.state.templates || []).filter((item) => item.id !== incoming.id),
                ];
                this.state.selectedTemplateId = incoming.id;
                this.syncTemplateParameterState();
            }

            this.state.submitTemplateName = "";
            this.state.submitTemplateBody = "";
            this.notification.add(
                `Template submitted to Meta. Current status: ${submittedStatus}. Use Sync Templates to refresh status.`,
                { type: "success" }
            );
        } finally {
            this.state.submittingTemplate = false;
        }
    }

    async loadTemplates({ sync = false, silent = false } = {}) {
        this.state.syncingTemplates = Boolean(sync);
        try {
            let templates = [];
            if (sync) {
                const result = await this.orm.call("ab.whatsapp.service", "api_sync_templates", [], {
                    page_limit: 100,
                });
                templates = result?.templates || [];
                if (!silent) {
                    this.notification.add(
                        `Templates synced. Fetched ${result?.fetched || 0}, created ${result?.created || 0}, updated ${result?.updated || 0}.`,
                        { type: "success" }
                    );
                }
            } else {
                templates = await this.orm.call("ab.whatsapp.service", "api_list_templates", []);
            }

            this.state.templates = templates;
            const selectedId = Number(this.state.selectedTemplateId || 0);
            if (selectedId && templates.some((item) => item.id === selectedId)) {
                return;
            }
            const defaultTemplate = templates.find((item) => item.is_sendable) || templates[0] || null;
            this.state.selectedTemplateId = defaultTemplate ? defaultTemplate.id : null;
            this.syncTemplateParameterState();
        } finally {
            this.state.syncingTemplates = false;
        }
    }

    async sendSelectedTemplate() {
        if (!this.state.activeWaId) {
            this.notification.add("Select a contact first.", { type: "warning" });
            return;
        }

        const template = this.selectedTemplate;
        if (!template) {
            this.notification.add("Select a template first.", { type: "warning" });
            return;
        }
        if (!template.is_sendable) {
            this.notification.add("Only approved templates can be sent.", { type: "warning" });
            return;
        }

        const requiredIndexes = this.selectedTemplatePlaceholderIndexes();
        const templateParams = requiredIndexes.map((_, position) =>
            (this.state.templateParamValues?.[position] || "").trim()
        );
        if (requiredIndexes.length && templateParams.some((item) => !item)) {
            this.notification.add("Fill all template parameter values first.", { type: "warning" });
            return;
        }

        this.state.sendingTemplate = true;
        try {
            await this.orm.call("ab.whatsapp.service", "api_send_template", [], {
                to: this.state.activeWaId,
                template_id: template.id,
                contact_name: this.activeContact?.name || null,
                template_params: templateParams,
            });
            this.state.showTemplateModal = false;
            this.notification.add("Template sent.", { type: "success" });
            await this.loadContacts();
            await this.loadConversation();
            this.queueScrollToBottom(true);
            this.focusComposer();
        } finally {
            this.state.sendingTemplate = false;
        }
    }

    async sendTextPayload(body, replyToMetaMessageId = null) {
        await this.orm.call(
            "ab.whatsapp.service",
            "api_send_text",
            [],
            {
                to: this.state.activeWaId,
                message: body,
                contact_name: this.activeContact?.name || null,
                reply_to_meta_message_id: replyToMetaMessageId || null,
            }
        );
    }

    async sendFilePayload(file, caption = null, replyToMetaMessageId = null) {
        const dataBase64 = await this.fileToBase64(file);
        const contentType = ((file.type || "application/octet-stream").split(";")[0] || "application/octet-stream").trim();
        await this.orm.call(
            "ab.whatsapp.service",
            "api_send_media_base64",
            [],
            {
                to: this.state.activeWaId,
                filename: file.name,
                content_type: contentType,
                data_base64: dataBase64,
                caption: caption || null,
                contact_name: this.activeContact?.name || null,
                reply_to_meta_message_id: replyToMetaMessageId || null,
            }
        );
    }

    async sendComposer() {
        if (!this.state.activeWaId) {
            this.notification.add("Select a contact first.", { type: "warning" });
            return;
        }

        const textBody = (this.state.composeMessage || "").trim();
        const pendingFiles = [...(this.state.pendingFiles || [])];
        if (!textBody && !pendingFiles.length) {
            this.notification.add("Write a message or attach a file first.", { type: "warning" });
            return;
        }

        const replyToMetaMessageId = this.state.replyToMetaMessageId || null;
        this.state.sendingComposer = true;
        this.state.sendingFile = true;
        this.state.sendingText = true;
        try {
            for (const file of pendingFiles) {
                await this.sendFilePayload(file, null, replyToMetaMessageId);
            }
            if (textBody) {
                await this.sendTextPayload(textBody, replyToMetaMessageId);
            }

            this.state.composeMessage = "";
            this.state.replyToMetaMessageId = null;
            this.state.pendingFiles = [];
            this.state.showEmojiPanel = false;
            if (this.fileInputRef.el) {
                this.fileInputRef.el.value = "";
            }

            this.notification.add("Message sent.", { type: "success" });
            await this.loadContacts();
            await this.loadConversation();
            this.queueScrollToBottom(true);
            this.focusComposer();
        } finally {
            this.state.sendingComposer = false;
            this.state.sendingFile = false;
            this.state.sendingText = false;
        }
    }

    async sendReaction(metaMessageId, emoji) {
        if (!this.state.activeWaId) {
            this.notification.add("Select a contact first.", { type: "warning" });
            return;
        }
        const normalizedEmoji = (emoji || "").trim();
        if (!normalizedEmoji) {
            return;
        }

        this.state.sendingReaction = true;
        try {
            await this.orm.call("ab.whatsapp.service", "api_send_reaction", [], {
                to: this.state.activeWaId,
                message_meta_id: metaMessageId,
                emoji: normalizedEmoji,
                contact_name: this.activeContact?.name || null,
            });
            await this.loadConversation();
            await this.loadContacts();
        } finally {
            this.state.sendingReaction = false;
        }
    }

    fileToBase64(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => {
                const result = reader.result || "";
                const marker = "base64,";
                const index = result.indexOf(marker);
                if (index < 0) {
                    reject(new Error("Invalid file payload."));
                    return;
                }
                resolve(result.slice(index + marker.length));
            };
            reader.onerror = () => reject(new Error("Unable to read file."));
            reader.readAsDataURL(file);
        });
    }

    contactPreview(contact) {
        if (contact.last_text_content) {
            return contact.last_text_content;
        }
        if (contact.last_message_type) {
            return `[${contact.last_message_type}]`;
        }
        return "No messages yet.";
    }

    formatTime(value) {
        if (!value) {
            return "";
        }
        const parsed = new Date(value.replace(" ", "T"));
        if (Number.isNaN(parsed.getTime())) {
            return value;
        }
        return parsed.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    }

    setUpdatedNow() {
        this.state.lastUpdated = new Date().toLocaleTimeString();
    }

    isNearBottom(element, threshold = 72) {
        if (!element) {
            return true;
        }
        return (element.scrollHeight - element.scrollTop - element.clientHeight) <= threshold;
    }

    scrollMessagesToBottom(force = false) {
        const box = this.messagesBoxRef.el;
        if (!box) {
            return;
        }
        if (!force && !this._stickToBottom) {
            return;
        }
        box.scrollTop = box.scrollHeight;
    }

    queueScrollToBottom(force = false) {
        requestAnimationFrame(() => {
            requestAnimationFrame(() => {
                this.scrollMessagesToBottom(force);
            });
        });
    }

    statusClass(message) {
        const status = (message?.status || "sent").toLowerCase();
        if (["sent", "delivered", "read", "failed"].includes(status)) {
            return status;
        }
        return "sent";
    }

    statusSymbol(message) {
        const status = this.statusClass(message);
        if (status === "read" || status === "delivered") {
            return "\u2713\u2713";
        }
        if (status === "failed") {
            return "!";
        }
        return "\u2713";
    }
}

registry.category("actions").add("ab_whatsapp_api.dashboard", AbWhatsAppDashboardAction);
