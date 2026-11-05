/** @odoo-module **/

import {Component, onMounted, onWillStart, onWillUnmount, onWillPatch, onPatched, useRef, useState} from "@odoo/owl";
import {registry} from "@web/core/registry";
import {SavedReplies} from "./templates";
import {ChatterContacts} from "./contacts";
import {OrderDialog} from "./order_dialog";
import {ChatterLoginDialog} from "./login";
import {useBus} from "@web/core/utils/hooks";
import {useService} from "@web/core/utils/hooks";
import {_t} from "@web/core/l10n/translation";
import {user} from "@web/core/user";
import {localization} from "@web/core/l10n/localization";

export class SalesWorkspace extends Component {
    static template = "ab_crm_sales_workspace.Workspace";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.isOrders = this.props.action?.tag === "ab_crm_sales_workspace.orders";
        this.ordersLabel = _t("Orders");
        this.chatterLabel = _t("Sales Chatter");
        this.noMessagesLabel = _t("No messages yet.");
        this.dialog = useService("dialog");
        this.chatterSession = useService("ab_chatter_session");
        this.loginClose = null;
        useBus(this.env.bus, "AB_CHATTER_SESSION", ({detail}) => {
            if (!detail) {
                this.stopRecording(true);
                this.rememberDraft();
                if (this.employeeId) this.employeeDrafts.set(`${user.activeCompany.id}:${this.employeeId}`, {messages: this.drafts, orders: this.orderDrafts, mediaUrls: this.mediaUrls});
                if (this.orderClose) this.orderClose();
                this.state.token = "";
                this.state.loggedIn = false;
                this.state.inbox = [];
                this.state.contacts = [];
                this.state.contact = null;
                this.state.detail = null;
                this.state.order = null;
                this.drafts = new Map();
                this.orderDrafts = new Map();
                this.showLogin();
            }
        });
        this.messagesRef = useRef("messages");
        this.filesRef = useRef("files");
        this.replyRef = useRef("reply");
        this.sendLabel = _t("Send message");
        this.mediaUrls = new Set();
        this.drafts = new Map();
        this.orderDrafts = new Map();
        this.employeeDrafts = this.chatterSession.workspaceDrafts;
        this.scrollState = null;
        this.prepending = false;
        onWillPatch(() => {
            const element = this.messagesRef.el;
            if (element) this.scrollState = {top: element.scrollTop, height: element.scrollHeight, bottom: element.scrollHeight - element.scrollTop - element.clientHeight < 40};
        });
        onPatched(() => {
            const element = this.messagesRef.el;
            if (element && this.resetScroll) {
                element.scrollTop = element.scrollHeight;
                this.resetScroll = false;
            } else if (element && this.scrollState) {
                element.scrollTop = this.scrollState.bottom && !this.prepending ? element.scrollHeight : this.scrollState.top + (this.prepending ? element.scrollHeight - this.scrollState.height : 0);
                this.prepending = false;
            }
        });
        this.direction = localization.direction;
        this.state = useState({inbox: [], contacts: [], contact: null, detail: null, order: null, reply: "", phone: "",
            showSearch: false, inboxQuery: "", inboxHasMore: false, candidates: [], customer: "", confirmed: false, query: "", products: [], reason: "",
            preparing: 0, attachments: [], replyTo: null, recording: false, emoji: false, messageQuery: "", searchResults: null, previews: {}, error: "", busy: false, token: "", employee: "", loggedIn: false});
        this.destroyed = false;
        this.refreshing = false;
        this.navigationVersion = 0;
        this.focusHandler = (item, token) => this.focusAlert(item, token);
        onMounted(() => {
            if (!this.isOrders) this.chatterSession.focusHandler = this.focusHandler;
            const item = this.props.action?.context?.chatter_alert;
            if (item && this.state.loggedIn) this.focusAlert(item, this.state.token).catch(error => { this.state.error = error.data?.message || error.message; });
        });
        onWillStart(async () => {
            await this.run(async () => {
                const cached = this.chatterSession.current;
                const bootstrap = await this.call("ab_crm_chatter_api", "bootstrap", [], {token: cached?.token || false});
                if (bootstrap.session) {
                    this.restoreEmployeeDrafts(bootstrap.session.employee_id);
                    this.state.token = cached.token;
                    this.state.employee = bootstrap.session.employee;
                    this.state.loggedIn = true;
                    await this.refresh();

                } else {
                    this.chatterSession.clear();
                    this.showLogin(bootstrap.employees);
                }
            });
            this.timer = setInterval(() => {
                if (this.state.loggedIn && !this.state.busy && !this.refreshing) {
                    this.refresh().catch(error => { this.state.error = error.data?.message || error.message; });
                }
            }, 5000);
        });
        onWillUnmount(() => { if (this.chatterSession.focusHandler === this.focusHandler) this.chatterSession.focusHandler = null; this.destroyed = true; this.stopRecording(true); this.rememberDraft(); if (this.state.loggedIn && this.employeeId) this.employeeDrafts.set(`${user.activeCompany.id}:${this.employeeId}`, {messages: this.drafts, orders: this.orderDrafts, mediaUrls: this.mediaUrls}); clearInterval(this.timer); if (this.loginClose) this.loginClose(); if (this.orderClose) this.orderClose(); });
    }

    context() { return {ab_chatter_session_token: this.state.token}; }
    call(model, method, args = [], kwargs = {}) {
        return this.orm.call(model, method, args, {...kwargs, context: this.context()});
    }
    async run(action) {
        if (this.state.busy) return;
        this.state.busy = true;
        this.state.error = "";
        try { await action(); }
        catch (error) { this.state.error = error.data?.message || error.message || _t("Operation failed."); }
        finally { this.state.busy = false; }
    }
    async showLogin(employees) {
        if (this.loginClose || this.destroyed) return;
        try {
            if (!employees) {
                const bootstrap = await this.call("ab_crm_chatter_api", "bootstrap");
                employees = bootstrap.employees;
            }
            if (this.loginClose || this.destroyed) return;
            this.loginClose = this.dialog.add(ChatterLoginDialog, {
                employees, onLogin: (profileId, pin) => this.login(profileId, pin),
            }, {onClose: () => { this.loginClose = null; }});
        } catch (error) { this.state.error = error.data?.message || error.message; }
    }
    async login(profileId, pin) {
        let device = sessionStorage.getItem(`ab_chatter_device_${user.userId}`);
        if (!device) { device = crypto.randomUUID(); sessionStorage.setItem(`ab_chatter_device_${user.userId}`, device); }
        const result = await this.call("ab_crm_chatter_api", "employee_login", [], {profile_id: profileId, pin, device_uid: device});
        if (result.error) throw new Error(result.error);
        this.restoreEmployeeDrafts(result.employee_id);
        this.state.token = result.token;
        this.state.employee = result.employee;
        this.chatterSession.set(result);
        this.state.loggedIn = true;
        this.state.error = "";
        await this.refresh();
    }
    restoreEmployeeDrafts(employeeId) {
        this.employeeId = employeeId;
        const preserved = this.employeeDrafts.get(`${user.activeCompany.id}:${employeeId}`);
        this.drafts = preserved?.messages || new Map();
        this.orderDrafts = preserved?.orders || new Map();
        this.mediaUrls = preserved?.mediaUrls || new Set();
    }
    async logout() {
        this.stopRecording(true);
        await this.run(async () => {
            await this.call("ab_crm_chatter_api", "logout", [], {token: this.state.token});
            this.chatterSession.clear();
        });
    }
    async refresh() {
        if (this.refreshing || this.destroyed) return;
        this.refreshing = true;
        const navigationVersion = this.navigationVersion;
        try {
            const inbox = await this.call("ab_crm_conversation", "workspace_inbox", [], {query: this.state.inboxQuery});
            if (this.destroyed || navigationVersion !== this.navigationVersion) return;
            if (!this.state.inbox.length) this.state.inboxHasMore = inbox.length === 50;
            const rows = new Map(this.state.inbox.map(row => [row.id, row]));
            for (const row of inbox) rows.set(row.id, row);
            this.state.inbox = [...rows.values()].sort((a, b) => b.id - a.id);
            await this.refreshContacts();
            if (!this.state.detail && !this.state.contact && this.state.inbox.length) {
                this.resetScroll = true;
                const selected = this.props.action?.context?.chatter_conversation_id || this.state.inbox[0].id;
                this.state.detail = await this.call("ab_crm_conversation", "workspace_detail", [[selected]], {mark_read: !this.isOrders});
                const draft = this.drafts.get(selected);
                this.state.reply = draft?.reply || "";
                this.state.attachments = draft?.attachments || [];
                this.state.replyTo = draft?.replyTo || null;
            }
            const id = this.state.detail?.id;
            if (id) {
                const current = this.state.detail;
                const detail = await this.call("ab_crm_conversation", "workspace_detail", [[id]], {after_id: current.messages.at(-1)?.id || false, mark_read: !this.isOrders && !this.orderClose && document.visibilityState === 'visible'});
                if (!this.destroyed && navigationVersion === this.navigationVersion && this.state.detail?.id === id) {
                    const messages = new Map(current.messages.map(message => [message.id, message]));
                    for (const message of detail.messages) messages.set(message.id, message);
                    const latest = await this.call("ab_crm_conversation", "workspace_detail", [[id]], {mark_read: !this.isOrders && !this.orderClose && document.visibilityState === "visible"});
                    for (const message of latest.messages) {
                        if (messages.has(message.id)) messages.set(message.id, message);
                    }
                    if (!this.destroyed && navigationVersion === this.navigationVersion && this.state.detail?.id === id) {
                        this.state.detail = {...detail, has_older: current.has_older, messages: [...messages.values()].sort((a, b) => a.id - b.id)};
                        if (!detail.owned) this.stopRecording(true);
                        if (detail.candidates?.length) this.state.candidates = detail.candidates;
                        if (!this.state.phone && detail.phone) this.state.phone = detail.phone;
                    }
                }
            }
        } finally { this.refreshing = false; }
    }
    rememberDraft() {
        if (this.state.detail) this.drafts.set(this.state.detail.id, {reply: this.state.reply, attachments: [...this.state.attachments], replyTo: this.state.replyTo});
    }
    async select(id) {
        this.navigationVersion++;
        await this.run(async () => {
            this.stopRecording(true);
            this.rememberDraft();
            this.resetScroll = true;
            this.state.contact = null;
            this.state.detail = await this.call("ab_crm_conversation", "workspace_detail", [[id]], {mark_read: !this.isOrders});
            this.state.phone = this.state.detail.phone;
            this.state.order = this.drafts.get(id)?.order || null;
            this.state.reason = this.drafts.get(id)?.reason || "";
            this.state.candidates = this.state.detail.candidates || [];
            this.state.attachments = this.drafts.get(id)?.attachments || [];
            this.state.replyTo = this.drafts.get(id)?.replyTo || null;
            this.state.searchResults = null;
            this.state.messageQuery = "";
            this.state.customer = "";
            this.state.confirmed = false;
            this.state.products = [];
            this.state.reply = this.drafts.get(id)?.reply || "";
        });
    }
    openView(orders) {
        if (orders === this.isOrders) return;
        this.stopRecording(true);
        this.rememberDraft();
        this.employeeDrafts.set(`${user.activeCompany.id}:${this.employeeId}`, {messages: this.drafts, orders: this.orderDrafts, mediaUrls: this.mediaUrls});
        this.action.doAction(orders ? "ab_crm_sales_workspace.action_orders" : "ab_crm_sales_workspace.action_workspace", {additionalContext: {chatter_conversation_id: this.state.detail?.id || false}});
    }
    searchInbox() {
        return this.run(async () => {
            this.state.inbox = await this.call("ab_crm_conversation", "workspace_inbox", [], {query: this.state.inboxQuery});
            this.state.inboxHasMore = this.state.inbox.length === 50;
            await this.refreshContacts();
        });
    }
    olderConversations() {
        return this.run(async () => {
            const rows = await this.call("ab_crm_conversation", "workspace_inbox", [], {query: this.state.inboxQuery, before_id: this.state.inbox.at(-1)?.id});
            this.state.inbox.push(...rows);
            this.state.inboxHasMore = rows.length === 50;
        });
    }
    olderMessages() {
        return this.run(async () => {
            const detail = await this.call("ab_crm_conversation", "workspace_detail", [[this.state.detail.id]], {before_id: this.state.detail.messages[0]?.id});
            this.prepending = true;
            this.state.detail = {...this.state.detail, has_older: detail.has_older, messages: [...detail.messages, ...this.state.detail.messages]};
        });
    }
    channelLabel(provider) { return {telegram: _t("Telegram"), whatsapp: _t("WhatsApp"), website: _t("Website")}[provider] || provider; }
    icon(provider) { return {telegram: "fa-telegram", whatsapp: "fa-whatsapp", website: "fa-globe"}[provider] || "fa-phone"; }
    stateLabel(value) {
        return {draft: _t("Draft"), accepted: _t("Accepted"), closed: _t("Closed"), cancelled: _t("Cancelled"),
            queued: _t("Queued"), leased: _t("Queued"), received: _t("Queued"), delivered: _t("Delivered"), read: _t("Read"), review: _t("Delivery review"), sent: _t("Sent"), approved: _t("Approved"), unknown: _t("Sending / review"), failed: _t("Failed")}[value] || value;
    }
    mediaStateLabel(value) { return {pending: _t("Pending download"), ready: _t("Ready"), failed: _t("Download failed")}[value] || value; }
    messageStateLabel(value) {
        return {waiting: _t("Waiting to send"), sending: _t("Sending…"), sent: _t("Sent"), delivered: _t("Delivered"), read: _t("Read"), failed: _t("Not sent"), retrying: _t("Retrying…"), retry_failed: _t("Retry failed"), uncertain: _t("Couldn’t confirm sending"), received: _t("Received")}[value] || "";
    }
    statusIcon(status) {
        return {waiting: "fa-clock-o", sending: "fa-spinner fa-spin", sent: "fa-check", delivered: "fa-check", read: "fa-check", failed: "fa-exclamation-circle", retry_failed: "fa-exclamation-circle", retrying: "fa-spinner fa-spin", uncertain: "fa-exclamation-triangle"}[status] || "";
    }
    retry(message) {
        return this.run(async () => {
            await this.call("ab_crm_messaging_operation", "action_retry", [[message.retry_operation_id]]);
            await this.refresh();
        });
    }
    async refreshContacts() {
        const result = await this.call("ab_crm_chatter_api", "contact_search", [], {token: this.state.token, query: this.state.inboxQuery});
        if (!this.destroyed) this.state.contacts = result.contacts;
    }
    contacts(mode) {
        this.dialog.add(ChatterContacts, {mode, call: this.call.bind(this), token: this.state.token, onSaved: async contact => {
            await this.refreshContacts();
            if (contact) await this.openContact(contact);
            else { this.state.contact = null; await this.refresh(); }
        }});
    }
    async openContact(contact) {
        const result = await this.call("ab_crm_chatter_api", "contact_open", [], {token: this.state.token, contact_id: contact.id});
        if (result.conversation_id) return this.select(result.conversation_id);
        this.stopRecording(true); this.rememberDraft();
        this.state.detail = null; this.state.contact = result.contact;
    }
    async focusAlert(item, token) {
        this.navigationVersion++;
        if (token !== this.state.token || !this.state.loggedIn) throw new Error(_t("Sign in to Sales Chatter with your employee and PIN."));
        const detail = await this.call("ab_crm_conversation", "workspace_focus", [[item.conversation_id], item.latest_message_id]);
        if (this.destroyed || token !== this.state.token) return;
        if (this.orderClose) this.orderClose();
        this.stopRecording(true); this.rememberDraft();
        this.state.contact = null;
        this.state.searchResults = null; this.state.messageQuery = ""; this.state.showSearch = false;
        this.state.detail = detail;
        const draft = this.drafts.get(detail.id);
        this.state.reply = draft?.reply || ""; this.state.attachments = draft?.attachments || []; this.state.replyTo = draft?.replyTo || null;
        this.resetScroll = false;
        await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
        const target = this.messagesRef.el?.querySelector(`[data-message-id="${item.latest_message_id}"]`);
        if (!target || this.destroyed) throw new Error(_t("Couldn’t open the conversation. Try again."));
        await Promise.all([...this.messagesRef.el.querySelectorAll("img")].map(img => img.decode().catch(() => {})));
        target.scrollIntoView({block: "center"});
        this.messagesRef.el.querySelectorAll(".ab_message_focus").forEach(element => element.classList.remove("ab_message_focus"));
        target.classList.add("ab_message_focus");
        target.focus({preventScroll: true});
        await this.chatterSession.acknowledge(item, token);
    }
    async conversationAction(method, args = []) {
        await this.run(async () => {
            await this.call("ab_crm_conversation", method, [[this.state.detail.id], ...args]);
            await this.refresh();
        });
    }
    requestContact() { return this.conversationAction("action_request_contact"); }
    async send() {
        if (this.sendDisabledReason) return;
        await this.run(async () => {
            await this.call("ab_crm_conversation", "action_reply", [[this.state.detail.id], this.state.reply], {attachments: this.state.attachments.map(({url, ...attachment}) => attachment), reply_id: this.state.replyTo?.id || false});
            this.clearAttachments();
            this.state.replyTo = null;
            this.state.reply = "";
            await this.refresh();
        });
    }
    get sendDisabledReason() {
        if (!this.state.detail?.can_send) return this.state.detail?.send_reason || _t("Select a conversation to begin.");
        if (this.state.busy || this.state.preparing) return _t("Preparing message…");
        if (this.state.recording) return _t("Stop or cancel recording before sending.");
        if (!this.state.reply.trim() && !this.state.attachments.length) return _t("Write a message or attach a file.");
        if (this.state.attachments.length && this.state.reply.length > 1024) return _t("Media captions must not exceed 1024 characters.");
        return "";
    }
    composerKeydown(event) {
        if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
            event.preventDefault();
            this.send();
        }
        if (event.key === "Escape") { this.state.emoji = false; this.state.replyTo = null; }
    }
    insertEmoji(emoji) {
        const input = this.replyRef.el;
        const start = input?.selectionStart ?? this.state.reply.length;
        const end = input?.selectionEnd ?? start;
        this.state.reply = this.state.reply.slice(0, start) + emoji + this.state.reply.slice(end);
        this.state.emoji = false;
        input?.focus();
    }
    clearAttachments() {
        for (const attachment of this.state.attachments) { URL.revokeObjectURL(attachment.url); this.mediaUrls.delete(attachment.url); }
        this.state.attachments = [];
    }
    removeAttachment(index) {
        const [attachment] = this.state.attachments.splice(index, 1);
        URL.revokeObjectURL(attachment.url);
        this.mediaUrls.delete(attachment.url);
    }
    async attachFiles(files, kind = false, duration = 0) {
        const conversationId = this.state.detail?.id;
        this.state.preparing++;
        try {
        for (const file of files) {
            const mime = file.type.split(";")[0];
            const image = mime.startsWith("image/");
            if (this.state.attachments.length >= 4 || file.size > (image ? 10 : 20) * 1024 * 1024) {
                this.state.error = _t("Attach up to four files, 20 MB per file and 10 MB per image.");
                return;
            }
            const data = await new Promise((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(reader.result.split(",")[1]); reader.onerror = reject; reader.readAsDataURL(file); });
            if (this.destroyed || this.state.detail?.id !== conversationId || !this.state.detail?.owned) return;
            if (this.state.attachments.length >= 4) {
                this.state.error = _t("Attach up to four files, 20 MB per file and 10 MB per image.");
                return;
            }
            const url = URL.createObjectURL(file);
            this.mediaUrls.add(url);
            this.state.attachments.push({name: file.name, mimetype: mime, size: file.size, duration, kind: kind || (image ? "image" : mime.startsWith("audio/") ? "audio" : "document"), data, url});
        }
        } finally { this.state.preparing--; }
    }
    async filesChanged(event) { await this.attachFiles(event.target.files); event.target.value = ""; }
    async paste(event) {
        const files = [...event.clipboardData.items].filter(item => item.kind === "file").map(item => item.getAsFile());
        if (files.length) { event.preventDefault(); await this.attachFiles(files); }
    }
    async record() {
        if (!this.state.detail?.owned || this.state.preparing) return;
        await this.run(async () => {
            const epoch = (this.recordEpoch || 0) + 1;
            this.recordEpoch = epoch;
            const stream = await navigator.mediaDevices.getUserMedia({audio: true});
            if (this.destroyed || this.recordEpoch !== epoch) { stream.getTracks().forEach(track => track.stop()); return; }
            this.stream = stream;
            try { this.recorder = new MediaRecorder(stream); }
            catch (error) { stream.getTracks().forEach(track => track.stop()); throw error; }
            const chunks = [];
            const recording = {cancelled: false};
            this.activeRecording = recording;
            const started = Date.now();
            this.recorder.ondataavailable = event => chunks.push(event.data);
            this.recorder.onstop = async () => {
                stream.getTracks().forEach(track => track.stop());
                try {
                    if (!recording.cancelled && !this.destroyed) {
                        const blob = new Blob(chunks, {type: chunks[0]?.type || "audio/webm"});
                        await this.attachFiles([new File([blob], "voice.webm", {type: blob.type})], "voice", Math.min(300, (Date.now() - started) / 1000));
                    }
                } catch (error) { this.state.error = error.message; }
                finally { if (recording.preparing) this.state.preparing--; }
            };
            this.recorder.start();
            this.state.recording = true;
            this.recordTimer = setTimeout(() => this.stopRecording(), 300000);
        });
    }
    stopRecording(cancel = false) {
        this.recordEpoch = (this.recordEpoch || 0) + 1;
        if (this.activeRecording) this.activeRecording.cancelled = cancel;
        clearTimeout(this.recordTimer);
        if (this.recorder?.state === "recording") {
            if (!cancel) { this.activeRecording.preparing = true; this.state.preparing++; }
            this.recorder.stop();
        }
        this.stream?.getTracks().forEach(track => track.stop());
        this.state.recording = false;
    }
    templates() { this.dialog.add(SavedReplies, {call: this.call.bind(this), conversation: this.state.detail, insert: text => { this.state.reply = text; }}); }
    async preview(media, download = false) {
        await this.run(async () => {
            const result = await this.call("ab_crm_message_media", "download", [[media.id]]);
            const raw = Uint8Array.from(atob(result.data), character => character.charCodeAt(0));
            const url = URL.createObjectURL(new Blob([raw], {type: result.mimetype}));
            this.mediaUrls.add(url);
            if (download || media.kind === "document") { const link = document.createElement("a"); link.href = url; link.download = result.name; link.click(); }
            else this.state.previews[media.id] = url;
        });
    }
    copy(message) { return navigator.clipboard.writeText(message.body); }
    react(message) { return this.conversationAction("action_reply", ["", [], message.id, "👍"]); }
    searchMessages() {
        return this.run(async () => {
            if (!this.state.messageQuery.trim()) { this.state.searchResults = null; return; }
            const detail = await this.call("ab_crm_conversation", "workspace_detail", [[this.state.detail.id]], {query: this.state.messageQuery});
            this.state.searchResults = detail.messages;
        });
    }
    auditLabel(action) {
        return {created: _t("Created"), line_added: _t("Line added"), line_changed: _t("Line changed"),
            accepted: _t("Accepted"), reopened: _t("Reopened"), closed: _t("Closed"), cancelled: _t("Cancelled")}[action] || action;
    }
    async loadOrder(id) {
        this.stopRecording(true);
        const order = await this.call("ab_crm_channel_order", "workspace_data", [[id]]);
        this.orderClose = this.dialog.add(OrderDialog, {order, orders: [...this.state.detail.orders.filter(row => row.id !== order.id), {id: order.id, name: order.name, state: order.state, revision: order.revision}].sort((a, b) => b.id - a.id), cachedDrafts: this.orderDrafts, call: this.call.bind(this), context: this.context(), onSaved: () => this.refresh()}, {onClose: () => { this.orderClose = null; }});
    }
    selectOrder(id) { return this.run(() => this.loadOrder(id)); }
    async newOrder() {
        await this.run(async () => {
            const id = await this.call("ab_crm_conversation", "action_new_order", [[this.state.detail.id]]);
            await this.loadOrder(id);
            await this.refresh();
        });
    }
}
registry.category("actions").add("ab_crm_sales_workspace.workspace", SalesWorkspace);

registry.category("actions").add("ab_crm_sales_workspace.orders", SalesWorkspace);
