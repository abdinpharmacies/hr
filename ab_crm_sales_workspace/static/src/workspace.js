import {useChatterFeedback, useChatterNotice, feedbackError} from "./feedback";
/** @odoo-module **/

import {Component, onMounted, onWillStart, onWillUnmount, onWillPatch, onPatched, useRef, useState, useExternalListener} from "@odoo/owl";
import {registry} from "@web/core/registry";
import {LocationDialog} from "./composer";
import {SavedReplies} from "./templates";
import {ChatterContacts, ChatterOrderPhone} from "./contacts";
import {LocationCard} from "./location";
import {ChatterLoginDialog} from "./login";
import {useBus} from "@web/core/utils/hooks";
import {useService} from "@web/core/utils/hooks";
import {_t} from "@web/core/l10n/translation";
import {user} from "@web/core/user";
import {MessageQuote, MessagePreview, MessageActions, MessageMedia, messageDate, compactUpdateTime, visibleMessageId, mediaBlob} from "./message";
import {localization} from "@web/core/l10n/localization";

export class SalesWorkspace extends Component {
    static template = "ab_crm_sales_workspace.Workspace";
    static props = ["*"];
    static components = {MessageQuote, MessageActions, MessageMedia, LocationCard};

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.chatterLabel = _t("Sales Chatter");
        this.noMessagesLabel = _t("No messages yet.");
        this.dialog = useService("dialog");
        this.chatterSession = useService("ab_chatter_session");
        this.loginClose = null;
        useBus(this.env.bus, "AB_CHATTER_SESSION", ({detail}) => {
            if (!detail) {
                this.navigationVersion++;
                if (this.previewClose) this.previewClose();
                this.stopRecording(true);
                this.rememberDraft();
                if (this.employeeId) this.employeeDrafts.set(`${user.activeCompany.id}:${this.employeeId}`, {messages: this.drafts, mediaUrls: this.mediaUrls, streams: this.selectedStreams, selection: {conversationId: this.state.detail?.id, contactId: this.state.contact?.id}});
                this.state.token = "";
                this.state.loggedIn = false;
                this.state.inbox = [];
                this.state.contacts = [];
                this.state.contact = null;
                this.state.detail = null;
                this.clearSearch();
                this.state.searchOpen = false;
                this.state.firstUnread = false;
                this.state.historyContext = false;
                this.state.emoji = false;
                this.state.attachmentMenu = false;
                this.emojiCaret = null;
                this.drafts = new Map();
                this.showLogin();
            }
        });
        useBus(this.env.bus, "AB_CHATTER_UNREAD", () => {
            if (this.state.loggedIn) this.refresh().catch(error => { this.state.error = feedbackError(this, error); });
        });
        this.messagesRef = useRef("messages");
        this.filesRef = useRef("files");
        this.attachToggleRef = useRef("attachToggle");
        this.replyRef = useRef("reply");
        this.searchInputRef = useRef("searchInput");
        this.searchToggleRef = useRef("searchToggle");
        useExternalListener(document, "pointerdown", event => {
            if (!event.target.closest(".ab_channel_group")) this.state.channelChooser = "";
            if (!event.target.closest(".ab_attachment_control")) this.state.attachmentMenu = false;
            if (!event.target.closest(".ab_emoji_panel, .ab_emoji_toggle")) this.state.emoji = false;
            if (this.state.searchOpen && !event.target.closest(".ab_message_search, .ab_search_field, .ab_search_toggle")) this.closeSearch(false);
        });
        useExternalListener(document, "keydown", event => {
            if (event.key === "Escape" && this.state.channelChooser) this.closeChannelChooser();
            if (event.key === "Escape" && this.state.attachmentMenu) { this.state.attachmentMenu = false; this.attachToggleRef.el?.focus(); }
            if (event.key === "Escape" && this.state.searchOpen) this.closeSearch();
            if (event.key === "Escape" && this.state.emoji) { this.state.emoji = false; this.replyRef.el?.focus(); }
        });
        this.sendLabel = _t("Send message");
        this.mediaUrls = new Set();
        this.drafts = new Map();
        this.employeeDrafts = this.chatterSession.workspaceDrafts;
        this.scrollState = null;
        this.prepending = false;
        onWillPatch(() => {
            const element = this.messagesRef.el;
            if (element) this.scrollState = {top: element.scrollTop, height: element.scrollHeight, bottom: element.scrollHeight - element.scrollTop - element.clientHeight < 40};
        });
        const restoreScroll = () => {
            const element = this.messagesRef.el;
            if (element && this.resetScroll) {
                element.scrollTop = element.scrollHeight;
                this.resetScroll = false;
                this.preservedSearchScroll = null;
            } else if (element && this.preservedSearchScroll != null) {
                element.scrollTop = this.preservedSearchScroll;
                this.preservedSearchScroll = null;
            } else if (element && this.scrollState) {
                element.scrollTop = this.scrollState.bottom && !this.prepending && !this.state.historyContext ? element.scrollHeight : this.scrollState.top + (this.prepending ? element.scrollHeight - this.scrollState.height : 0);
                this.prepending = false;
            }
            this.focusPendingQuote();
            this.restoreComposerCaret();
            if (this.focusSearch && this.searchInputRef.el) { this.searchInputRef.el.focus({preventScroll: true}); this.focusSearch = false; }
            this.updateScroll();
        };
        onMounted(restoreScroll);
        onPatched(restoreScroll);
        this.direction = localization.direction;
        this.state = useState({inbox: [], contacts: [], contact: null, detail: null, reply: "", phone: "",
             inboxQuery: "", inboxHasMore: false, candidates: [], customer: "", confirmed: false, query: "", products: [], reason: "",
            firstUnread: false, away: false, historyContext: false, searchOpen: false, searchQuery: "", searchResults: [], searchOlder: false, searchBusy: false, searchSubmitted: false, searchError: "", preparing: 0, attachments: [], replyTo: null, recording: false, attachmentMenu: false, emoji: false, error: "", busy: false, token: "", employee: "", loggedIn: false});
        this.feedback = useChatterFeedback(this);
        useChatterNotice(() => this.state.detail && !this.state.detail.can_send ? {message: this.state.detail.send_reason} : null,
            () => [this.state.detail?.id, this.state.detail?.can_send, this.state.detail?.send_reason]);
        useChatterNotice(() => this.state.detail?.can_send && !this.state.busy && !this.state.preparing && this.composerHint ? {message: this.composerHint} : null,
            () => [this.state.detail?.id, this.state.busy, this.state.preparing, this.composerHint]);

        this.destroyed = false;
        this.refreshing = false;
        this.navigationVersion = 0;
        this.acknowledged = new Map();
        this.readTimer = setInterval(() => this.acknowledgeVisible(), 1000);
        this.focusHandler = (item, token) => this.focusAlert(item, token);
        onMounted(() => {
            this.chatterSession.focusHandler = this.focusHandler;
            const item = this.props?.action?.context?.chatter_alert;
            if (item && this.state.loggedIn) this.focusAlert(item, this.state.token).catch(error => { this.state.error = feedbackError(this, error); });
        });
        onWillStart(async () => {
            await this.run(() => this.restoreSession());
            if (this.state.loggedIn && this.props?.action?.context?.chatter_create_order) {
                setTimeout(() => this.createOrder(), 0);
            }
            this.timer = setInterval(() => {
                if (!this.state.loggedIn && this.chatterSession.current && !this.loginClose && !this.state.busy) {
                    this.run(() => this.restoreSession());
                } else if (this.state.loggedIn && !this.state.busy && !this.refreshing) {
                    this.refresh().catch(error => { this.state.error = feedbackError(this, error); });
                }
            }, 5000);
        });
        onWillUnmount(() => { if (this.chatterSession.focusHandler === this.focusHandler) this.chatterSession.focusHandler = null; this.destroyed = true; clearInterval(this.readTimer); if (this.previewClose) this.previewClose(); this.stopRecording(true); this.rememberDraft(); if (this.state.loggedIn && this.employeeId) this.employeeDrafts.set(`${user.activeCompany.id}:${this.employeeId}`, {messages: this.drafts, mediaUrls: this.mediaUrls, streams: this.selectedStreams, selection: {conversationId: this.state.detail?.id, contactId: this.state.contact?.id}}); clearInterval(this.timer); if (this.loginClose) this.loginClose(); });
    }

    get emojis() { return ["😀", "😂", "😍", "👍", "🙏", "🔥", "✅", "🎉", "❤️", "😢", "😮", "👏"]; }
    context() { return {ab_chatter_session_token: this.state.token, ab_chatter_inbox_only: true}; }
    call(model, method, args = [], kwargs = {}) {
        return this.feedback.call(this.orm, model, method, args, {...kwargs, context: this.context()});
    }
    async run(action) {
        if (this.state.busy) return;
        this.state.busy = true;
        this.state.error = "";
        try { await action(); }
        catch (error) { this.state.error = feedbackError(this, error); }
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
        } catch (error) { this.state.error = feedbackError(this, error); }
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
        try { await this.refresh(); }
        catch (error) { this.state.error = feedbackError(this, error); }
        if (this.props?.action?.context?.chatter_create_order) setTimeout(() => this.createOrder(), 0);
    }
    async restoreSession() {
        const cached = this.chatterSession.current;
        const bootstrap = await this.call("ab_crm_chatter_api", "bootstrap", [], {token: cached?.token || false});
        if (this.destroyed) return;
        if (bootstrap.session) {
            this.restoreEmployeeDrafts(bootstrap.session.employee_id);
            this.state.token = cached.token;
            this.state.employee = bootstrap.session.employee;
            this.state.loggedIn = true;
            await this.refresh();
        } else {
            this.chatterSession.clear();
            await this.showLogin(bootstrap.employees);
        }
    }
    restoreEmployeeDrafts(employeeId) {
        this.employeeId = employeeId;
        const preserved = this.employeeDrafts.get(`${user.activeCompany.id}:${employeeId}`);
        this.drafts = preserved?.messages || new Map();
        this.selectedStreams = preserved?.streams || new Map();
        this.mediaUrls = preserved?.mediaUrls || new Set();
        this.initialSelection = preserved?.selection;
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
            const inbox = await this.loadCustomerInbox();
            if (this.destroyed || navigationVersion !== this.navigationVersion) return;
            this.state.inbox = inbox.items;
            this.state.inboxHasMore = inbox.has_more;
            await this.refreshContacts();
            const restoreContact = this.props?.action?.context?.chatter_contact_id || this.initialSelection?.contactId;
            let restoreConversation = this.props?.action?.context?.chatter_conversation_id || this.initialSelection?.conversationId;
            if (!this.restoredContact && !this.state.detail && restoreContact && !restoreConversation) {
                this.restoredContact = true;
                const restored = await this.call("ab_crm_chatter_api", "contact_open", [], {token: this.state.token, contact_id: restoreContact});
                if (restored.conversation_id) restoreConversation = restored.conversation_id;
                else this.state.contact = restored.contact;
            }
            if (!this.state.detail && !this.state.contact && this.state.inbox.length &&
                (!this.props?.action?.context?.chatter_create_order || restoreConversation)) {
                const selected = restoreConversation || this.preferredStream(this.state.inbox[0]);
                const initial = await this.call("ab_crm_conversation", "workspace_detail", [[selected]], {});
                if (this.destroyed || navigationVersion !== this.navigationVersion) return;
                this.resetScroll = true;
                this.state.detail = initial;
                this.state.firstUnread = initial.first_unread_message_id;
                this.state.historyContext = false;
                this.clearSearch();
                this.state.searchOpen = false;
                const draft = this.drafts.get(selected);
                this.state.reply = draft?.reply || "";
                this.state.attachments = draft?.attachments || [];
                this.state.replyTo = draft?.replyTo || null;
            }
            const id = this.state.detail?.id;
            if (id) {
                const current = this.state.detail;
                const detail = await this.call("ab_crm_conversation", "workspace_detail", [[id]], {after_id: current.message_cursor || Math.max(0, ...current.messages.map(message => message.id)) || false});
                if (!this.destroyed && navigationVersion === this.navigationVersion && this.state.detail?.id === id) {
                    const messages = new Map(current.messages.map(message => [message.id, message]));
                    for (const message of detail.messages) messages.set(message.id, message);
                    const latest = await this.call("ab_crm_conversation", "workspace_detail", [[id]], {});
                    for (const message of latest.messages) {
                        if (messages.has(message.id)) messages.set(message.id, message);
                    }
                    if (current.last_update_at !== latest.last_update_at) {
                        const recent = new Set(latest.messages.map(message => message.id));
                        const older = current.messages.filter(message => !recent.has(message.id)).map(message => message.id);
                        for (let offset = 0; offset < older.length; offset += 50) {
                            if (this.destroyed || navigationVersion !== this.navigationVersion || this.state.detail?.id !== id) return;
                            const updated = await this.call("ab_crm_conversation", "workspace_detail", [[id]], {message_ids: older.slice(offset, offset + 50)});
                            for (const message of updated.messages) messages.set(message.id, message);
                        }
                    }
                    if (!this.destroyed && navigationVersion === this.navigationVersion && this.state.detail?.id === id) {
                        this.state.detail = {...detail, has_older: current.has_older, messages: [...messages.values()].sort((a, b) => (a.timestamp || "").localeCompare(b.timestamp || "") || a.id - b.id)};
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
    async select(id, channel = false, focusedDetail = null) {
        if (this.state.busy) return;
        const version = ++this.navigationVersion;
        await this.run(async () => {
            this.stopRecording(true);
            this.rememberDraft();
            this.state.contact = null;
            const source = this.state.detail?.id;
            const detail = focusedDetail || await this.call("ab_crm_conversation", channel ? "workspace_channel" : "workspace_detail", channel ? [[source], id] : [[id]]);
            if (this.destroyed || version !== this.navigationVersion) return;
            if (this.previewClose) this.previewClose();
            this.resetScroll = true;
            this.state.detail = detail;
            this.state.channelChooser = "";
            this.selectedStreams ||= new Map();
            const group = this.state.inbox?.find(item => item.streams?.some(stream => stream.id === id));
            if (group) {
                const key = `${user.activeCompany.id}:${this.employeeId}:${group.group_key}`;
                this.selectedStreams.set(key, id);
                try { localStorage.setItem(`ab_chatter_stream:${key}`, String(id)); } catch {}
            }
            this.state.firstUnread = detail.first_unread_message_id;
            this.state.historyContext = false;
            this.clearSearch();
            this.state.searchOpen = false;
            this.state.attachmentMenu = false;
            this.state.emoji = false;
            this.state.phone = this.state.detail.phone;
            this.state.reason = this.drafts.get(id)?.reason || "";
            this.state.candidates = this.state.detail.candidates || [];
            this.state.attachments = this.drafts.get(id)?.attachments || [];
            this.state.replyTo = this.drafts.get(id)?.replyTo || null;
            this.state.customer = "";
            this.state.confirmed = false;
            this.state.products = [];
            this.state.reply = this.drafts.get(id)?.reply || "";
        });
    }
    openInvoices() { return this.action.doAction("ab_sales.ab_sales_bill_wizard_action"); }
    openInbox() { return this.refresh(); }
    async createOrder(messageId = false, contact = null, phoneId = false) {
        contact ||= this.state.detail?.contact || this.state.contact;
        if (!contact) {
            this.dialog.add(ChatterContacts, {mode: "add", call: this.call.bind(this), token: this.state.token,
                initial: this.state.detail ? {name: this.state.detail.name, phone: this.state.detail.phone,
                    display_phone: this.state.detail.display_phone, branch_id: this.state.detail.branch_id} : undefined,
                onSaved: selected => this.createOrder(messageId, selected), pick: true});
            return;
        }
        if (!phoneId && contact.phones?.length > 1) {
            this.dialog.add(ChatterOrderPhone, {phones: contact.phones,
                select: id => this.createOrder(messageId, contact, id)});
            return;
        }
        return this.run(async () => {
            this.stopRecording(true);
            this.rememberDraft();
            const id = await this.call("ab_crm_chatter_api", "pos_handoff_start", [], {
                token: this.state.token, contact_id: contact.id,
                conversation_id: this.state.detail && (!this.state.detail.contact || this.state.detail.contact.id === contact.id) ? this.state.detail.id : false,
                message_id: messageId, phone_id: phoneId,
            });
            await this.action.doAction("ab_crm_sales_workspace.action_pos", {additionalContext: {crm_handoff_id: id}});
        });
    }
    preferredStream(item) {
        const key = `${user.activeCompany.id}:${this.employeeId}:${item.group_key}`;
        let selected = this.selectedStreams?.get(key);
        if (!selected) {
            try { selected = Number(localStorage.getItem(`ab_chatter_stream:${key}`)); } catch {}
        }
        return item.streams?.some(stream => stream.id === selected) ? selected : item.id;
    }
    get channelGroups() {
        const groups = new Map();
        for (const stream of this.state.detail?.streams || []) {
            if (!groups.has(stream.provider)) groups.set(stream.provider, {provider: stream.provider, streams: [], unread: 0});
            const group = groups.get(stream.provider);
            group.streams.push(stream); group.unread += stream.unread || 0;
        }
        return [...groups.values()];
    }
    openChannel(group) {
        if (group.streams.length === 1) return this.select(group.streams[0].id, true);
        this.state.channelChooser = this.state.channelChooser === group.provider ? "" : group.provider;
        requestAnimationFrame(() => document.querySelector(".ab_channel_chooser button.active, .ab_channel_chooser button")?.focus());
    }
    closeChannelChooser() {
        const provider = this.state.channelChooser;
        this.state.channelChooser = "";
        document.querySelector(`.ab_channel_button[data-channel="${provider}"]`)?.focus();
    }
    channelKeydown(event) {
        const buttons = [...event.currentTarget.querySelectorAll("button")];
        let index = buttons.indexOf(event.target);
        if (event.key === "ArrowDown") index = (index + 1) % buttons.length;
        else if (event.key === "ArrowUp") index = (index - 1 + buttons.length) % buttons.length;
        else if (event.key === "Home") index = 0;
        else if (event.key === "End") index = buttons.length - 1;
        else return;
        event.preventDefault(); buttons[index]?.focus();
    }
    selectCustomer(item) { return this.select(this.preferredStream(item)); }
    async loadCustomerInbox(pages = this.inboxPages || 1) {
        const items = [];
        let result;
        for (let page = 0; page < pages; page++) {
            result = await this.call("ab_crm_conversation", "workspace_customer_inbox", [], {query: this.state.inboxQuery, offset: page * 50});
            items.push(...result.items);
            if (!result.has_more) break;
        }
        return {items, has_more: result.has_more};
    }
    searchInbox() {
        return this.run(async () => {
            this.inboxPages = 1;
            const result = await this.loadCustomerInbox();
            this.state.inbox = result.items;
            this.state.inboxHasMore = result.has_more;
            await this.refreshContacts();
        });
    }
    olderConversations() {
        return this.run(async () => {
            this.inboxPages = (this.inboxPages || 1) + 1;
            const result = await this.loadCustomerInbox();
            this.state.inbox = result.items;
            this.state.inboxHasMore = result.has_more;
        });
    }
    olderMessages() {
        if (this.state.busy) return;
        const version = ++this.navigationVersion;
        return this.run(async () => {
            const detail = await this.call("ab_crm_conversation", "workspace_detail", [[this.state.detail.id]], {before_id: this.state.detail.messages[0]?.id});
            if (this.destroyed || version !== this.navigationVersion || this.state.detail?.id !== detail.id) return;
            this.prepending = true;
            this.state.historyContext = true;
            this.state.detail = {...this.state.detail, has_older: detail.has_older, messages: [...detail.messages, ...this.state.detail.messages]};
        });
    }
    channelLabel(provider) { return {telegram: _t("Telegram"), whatsapp: _t("WhatsApp"), website: _t("Website"), application: _t("Application")}[provider] || provider; }
    icon(provider) { return {telegram: "fa-telegram", whatsapp: "fa-whatsapp", website: "fa-globe", application: "fa-mobile"}[provider] || "fa-phone"; }
    stateLabel(value) {
        return {draft: _t("Draft"), accepted: _t("Accepted"), closed: _t("Closed"), cancelled: _t("Cancelled"),
            queued: _t("Queued"), leased: _t("Queued"), received: _t("Queued"), delivered: _t("Delivered"), read: _t("Read"), review: _t("Delivery review"), sent: _t("Sent"), approved: _t("Approved"), unknown: _t("Sending / review"), failed: _t("Failed")}[value] || value;
    }
    mediaStateLabel(value) { return {pending: _t("Pending download"), ready: _t("Ready"), failed: _t("Download failed")}[value] || value; }
    messageStateLabel(value) {
        return {waiting: _t("Waiting to send"), sending: _t("Sending…"), sent: _t("Sent"), delivered: _t("Delivered"), read: _t("Read"), failed: _t("Not sent"), retrying: _t("Retrying…"), retry_failed: _t("Retry failed"), uncertain: _t("Couldn’t confirm sending"), received: _t("Received")}[value] || "";
    }
    retryLabel(message) { return message.retry_operation_id ? _t("Retry sending") : message.explanation || this.messageStateLabel(message.status); }
    compactTime(value) { return compactUpdateTime(value); }
    get composerHint() { return this.state.reply.trim() || this.state.attachments.length || this.state.preparing || this.state.recording ? this.sendDisabledReason : ""; }
    retry(message) {
        if (!message.retry_operation_id) return;
        return this.run(async () => {
            await this.call("ab_crm_messaging_operation", "action_retry", [[message.retry_operation_id]]);
            await this.refreshMessage(message.target_message_id || message.id);
            await this.refresh();
        });
    }
    async refreshMessage(id) {
        const version = this.navigationVersion;
        const conversation = this.state.detail.id;
        const detail = await this.call("ab_crm_conversation", "workspace_detail", [[conversation]], {message_ids: [id]});
        if (this.destroyed || version !== this.navigationVersion || this.state.detail?.id !== conversation) return;
        const updated = new Map(detail.messages.map(message => [message.id, message]));
        this.state.detail.messages = this.state.detail.messages.map(message => updated.get(message.id) || message);
    }
    async refreshContacts() {
        const result = await this.call("ab_crm_chatter_api", "contact_search", [], {token: this.state.token, query: this.state.inboxQuery});
        if (!this.destroyed) this.state.contacts = result.contacts;
    }
    contacts(mode, initial = null, offerLink = false) {
        const conversationId = this.state.detail?.id;
        const channel = this.state.detail?.provider;
        initial ||= ["edit", "delete"].includes(mode) ? this.state.detail?.contact || this.state.contact : null;
        this.dialog.add(ChatterContacts, {mode, initial, channel, conversationId, branchId: this.state.detail?.branch_id, onLink: contact => this.contacts("link", contact), call: this.call.bind(this), token: this.state.token, onSaved: async contact => {
            await this.refreshContacts();
            if (conversationId && this.state.detail?.id === conversationId) {
                await this.refresh();
                if (mode === "add" && contact && offerLink) this.contacts("link", contact);
            } else if (contact) await this.openContact(contact);
            else { this.state.contact = null; await this.refresh(); }
        }});
    }
    async unlinkCustomer() {
        const detail = this.state.detail;
        if (!detail?.contact || detail.streams.length < 2) return;
        const id = detail.id;
        const customerId = detail.contact.id;
        const preview = await this.call("ab_crm_conversation", "action_preview_customer_unlink", [[id], customerId]);
        if (this.state.detail?.id !== id || this.state.detail?.contact?.id !== customerId) return;
        this.rememberDraft();
        await this.call("ab_crm_conversation", "action_unlink_customer", [[id], customerId, preview.fingerprint]);
        this.state.channelChooser = null;
        await this.refresh();
        this.chatterSession?.unreadChanged();
    }
    async createConversationContact() {
        const id = this.state.detail.id;
        const result = await this.call("ab_crm_conversation", "action_customer_link_candidates", [[id]]);
        if (this.state.detail?.id !== id) return;
        if (result.contacts.length) { this.contacts("link"); return; }
        this.contacts("add", {name: this.state.detail.name, phone: result.phone, display_phone: result.display_phone, branch_id: this.state.detail.branch_id}, true);
    }
    saveContactCard(card) {
        const address = card.addresses?.[0];
        this.contacts("add", {name: card.name?.formatted_name || "", phone: card.phones?.[0]?.phone || "",
            address: address ? [address.street, address.city, address.state, address.country].filter(Boolean).join(", ") : "",
            branch_id: this.state.detail.branch_id});
    }
    async openContact(contact) {
        const result = await this.call("ab_crm_chatter_api", "contact_open", [], {token: this.state.token, contact_id: contact.id});
        if (result.conversation_id) return this.select(result.conversation_id);
        this.stopRecording(true); this.rememberDraft();
        this.state.detail = null; this.state.contact = result.contact;
    }
    async focusAlert(item, token) {
        const version = ++this.navigationVersion;
        if (token !== this.state.token || !this.state.loggedIn) throw new Error(_t("Sign in to Sales Chatter with your employee and PIN."));
        this.focusingAlert = version;
        try {
            const detail = await this.call("ab_crm_conversation", "workspace_focus", [[item.conversation_id], item.latest_message_id]);
            if (this.destroyed || token !== this.state.token || version !== this.navigationVersion) return;
            if (this.state.busy) throw new Error(_t("Couldn’t open the conversation. Try again."));
            await this.select(detail.id, false, detail);
            const selectedVersion = this.navigationVersion;
            if (this.state.detail?.id !== detail.id) throw new Error(_t("Couldn’t open the conversation. Try again."));
            this.state.historyContext = true;
            this.resetScroll = false;
            await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
            const target = this.messagesRef.el?.querySelector(`[data-message-id="${item.latest_message_id}"]`);
            if (!target || this.destroyed) throw new Error(_t("Couldn’t open the conversation. Try again."));
            await Promise.all([...this.messagesRef.el.querySelectorAll("img")].map(img => img.decode().catch(() => {})));
            if (this.destroyed || selectedVersion !== this.navigationVersion || token !== this.state.token) return;
            target.scrollIntoView({block: "center"});
            this.messagesRef.el.querySelectorAll(".ab_message_focus").forEach(element => element.classList.remove("ab_message_focus"));
            target.classList.add("ab_message_focus");
            target.focus({preventScroll: true});
            await this.chatterSession.acknowledge(item, token);
        } finally {
            if (this.focusingAlert === version) this.focusingAlert = false;
        }
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
        this.emojiCaret = {position: start + emoji.length, text: this.state.reply, conversation: this.state.detail?.id};
        this.state.emoji = false;
    }
    restoreComposerCaret() {
        const caret = this.emojiCaret;
        if (!caret) return;
        this.emojiCaret = null;
        const input = this.replyRef.el;
        if (!input?.isConnected || caret.text !== this.state.reply || caret.conversation !== this.state.detail?.id) return;
        input.focus({preventScroll: true});
        input.setSelectionRange(caret.position, caret.position);
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
    openAttachments() {
        if (this.state.detail?.owned && !this.state.busy && !this.state.recording && !this.state.preparing) this.state.attachmentMenu = true;
    }
    toggleAttachments(event) {
        this.state.attachmentMenu = event.detail === 0 ? !this.state.attachmentMenu : true;
    }
    leaveAttachments(event) {
        if (!event.currentTarget.contains(document.activeElement)) this.state.attachmentMenu = false;
    }
    leaveAttachmentFocus(event) {
        if (!event.currentTarget.contains(event.relatedTarget)) this.state.attachmentMenu = false;
    }
    chooseAttachment(category) {
        const input = this.filesRef.el;
        this.fileConversationId = this.state.detail.id;
        input.accept = {
            media: "image/jpeg,image/png,image/webp,video/mp4",
            document: this.state.detail.provider === "whatsapp" ? ".pdf,.doc,.docx,.txt,.xls,.xlsx,.ppt,.pptx" : ".pdf,.doc,.docx",
            music: this.state.detail.provider === "whatsapp" ? "audio/mpeg,audio/mp4,audio/ogg" : "audio/mpeg,audio/mp4",
        }[category];
        this.state.attachmentMenu = false;
        input.click();
    }
    attachmentTemplates() { this.state.attachmentMenu = false; this.templates(); }
    location() {
        this.state.attachmentMenu = false;
        const conversation = this.state.detail.id;
        const version = this.navigationVersion;
        this.dialog.add(LocationDialog, {
            call: this.call.bind(this), conversationId: conversation,
            valid: () => !this.destroyed && this.state.detail?.id === conversation && this.navigationVersion === version && this.state.detail.owned,
            sent: () => { if (!this.destroyed && this.state.detail?.id === conversation && this.navigationVersion === version) this.refresh(); },
        }, {onClose: () => { if (!this.destroyed && this.state.detail?.id === conversation && this.navigationVersion === version) this.attachToggleRef?.el?.focus(); }});
    }

    async attachFiles(files, kind = false, duration = 0) {
        const conversationId = this.state.detail?.id;
        this.state.preparing++;
        try {
        for (const file of files) {
            const mime = file.type.split(";")[0];
            const image = mime.startsWith("image/");
            const video = mime === "video/mp4";
            const limit = image ? (this.state.detail.provider === "whatsapp" ? 5 : 10) : video || (this.state.detail.provider === "whatsapp" && mime.startsWith("audio/")) ? 16 : 20;
            if (this.state.attachments.length >= 4 || file.size > limit * 1024 * 1024) {
                this.state.error = feedbackError(this, _t("Attach up to four files. Images: 10 MB (WhatsApp: 5 MB); videos: 16 MB; other files: 20 MB (WhatsApp audio: 16 MB)."));
                return;
            }
            const data = await new Promise((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(reader.result.split(",")[1]); reader.onerror = reject; reader.readAsDataURL(file); });
            if (this.destroyed || this.state.detail?.id !== conversationId || !this.state.detail?.owned) return;
            if (this.state.attachments.length >= 4) {
                this.state.error = feedbackError(this, _t("Attach up to four files. Images: 10 MB (WhatsApp: 5 MB); videos: 16 MB; other files: 20 MB (WhatsApp audio: 16 MB)."));
                return;
            }
            const url = URL.createObjectURL(file);
            this.mediaUrls.add(url);
            this.state.attachments.push({name: file.name, mimetype: mime, size: file.size, duration, kind: kind || (image ? "image" : video ? "video" : mime.startsWith("audio/") ? "audio" : "document"), data, url});
        }
        } catch (error) { this.state.error = feedbackError(this, error); }
        finally { this.state.preparing--; }
    }
    async filesChanged(event) {
        if (!this.fileConversationId || this.fileConversationId === this.state.detail?.id) await this.attachFiles(event.target.files);
        event.target.value = "";
        this.fileConversationId = null;
    }
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
                } catch (error) { this.state.error = feedbackError(this, error); }
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
        const version = this.navigationVersion;
        await this.run(async () => {
            try {
                const result = await this.call("ab_crm_message_media", "download", [[media.id]]);
                if (this.destroyed || version !== this.navigationVersion) return;
                const url = URL.createObjectURL(mediaBlob(result));
                if (download) {
                    try {
                        const link = document.createElement("a");
                        link.href = url; link.download = result.name; link.click();
                    } finally { setTimeout(() => URL.revokeObjectURL(url), 1000); }
                } else {
                    try {
                        this.previewClose = this.dialog.add(MessagePreview, {url, media, provider: this.state.detail?.provider || "telegram"}, {onClose: () => { this.previewClose = null; }});
                    } catch (error) { URL.revokeObjectURL(url); throw error; }
                }
            } catch (error) { throw new Error(download ? _t("Couldn’t download the attachment. Try again.") : _t("Couldn’t preview the attachment. Try again.")); }
        });
    }
    async copy(message) {
        try { await navigator.clipboard.writeText(message.body || ""); }
        catch { this.state.error = feedbackError(this, _t("Couldn’t copy the message. Check clipboard permissions.")); }
    }
    react(message, reaction) {
        if (!message.actions.react.enabled || !message.actions.reactions.includes(reaction)) return;
        return this.run(async () => {
            await this.call("ab_crm_conversation", "action_reply", [[this.state.detail.id], "", [], message.id, reaction]);
            await this.refreshMessage(message.id);
            await this.refresh();
        });
    }
    reply(message) {
        if (!message.actions.reply.enabled) return;
        this.state.replyTo = {available: true, id: message.id, author: message.author,
            body: (message.body || message.media[0]?.name || _t("Attachment")).slice(0, 160),
            thumbnail: message.media.find(media => media.kind === "image" && media.state === "ready") || false};
        this.replyRef.el?.focus();
    }
    async openQuote(quote) {
        if (this.state.busy || !quote.available) return;
        const id = this.state.detail.id;
        const version = ++this.navigationVersion;
        await this.run(async () => {
            let result;
            try { result = await this.call("ab_crm_conversation", "workspace_reply", [[id], quote.id]); }
            catch { if (!this.destroyed && version === this.navigationVersion) quote.available = false; return; }
            if (this.destroyed || version !== this.navigationVersion || this.state.detail?.id !== id) return;
            if (!result.available) { quote.available = false; return; }
            this.pendingQuoteFocus = {id: quote.id, version};
            if (!this.state.detail.messages.some(message => message.id === quote.id)) {
                this.state.historyContext = true;
                this.state.detail.messages = result.messages;
                this.state.detail.has_older = result.has_older;
            }
            this.resetScroll = false;
        });
    }
    focusPendingQuote() {
        const focus = this.pendingQuoteFocus;
        if (!focus) return;
        if (this.destroyed || focus.version !== this.navigationVersion) { this.pendingQuoteFocus = null; return; }
        const target = this.messagesRef.el?.querySelector(`[data-message-id="${focus.id}"]`);
        if (!target) return;
        this.messagesRef.el.querySelectorAll(".ab_message_focus").forEach(element => element.classList.remove("ab_message_focus"));
        target.scrollIntoView({block: "center"});
        target.classList.add("ab_message_focus");
        target.focus({preventScroll: true});
        this.pendingQuoteFocus = null;
    }
    updateScroll() {
        const element = this.messagesRef.el;
        if (element) this.state.away = element.scrollHeight - element.scrollTop - element.clientHeight > 40;
    }
    async jumpLatest() {
        if (this.state.busy) return;
        const id = this.state.detail.id;
        const version = ++this.navigationVersion;
        await this.run(async () => {
            const detail = await this.call("ab_crm_conversation", "workspace_detail", [[id]]);
            if (this.destroyed || version !== this.navigationVersion || this.state.detail?.id !== id) return;
            this.resetScroll = true;
            this.state.historyContext = false;
            this.state.detail = detail;
        });
    }
    jumpUnread() { if (this.state.firstUnread) return this.openQuote({id: this.state.firstUnread, available: true}); }
    toggleSearch() {
        if (this.state.searchOpen) return this.closeSearch();
        this.state.searchOpen = true;
        this.focusSearch = true;
    }
    closeSearch(restoreFocus = true) {
        this.state.searchOpen = false;
        this.focusSearch = false;
        if (restoreFocus) this.searchToggleRef?.el?.focus({preventScroll: true});
    }
    async openSearchResult(result) {
        if (this.state.busy) return;
        const conversationId = this.state.detail.id;
        await this.openQuote({id: result.id, available: true});
        if (this.state.detail?.id === conversationId) this.closeSearch(false);
    }
    clearSearch() {
        this.preservedSearchScroll = this.messagesRef?.el?.scrollTop;
        this.searchVersion = (this.searchVersion || 0) + 1;
        Object.assign(this.state, {searchQuery: "", searchResults: [], searchOlder: false, searchBusy: false, searchSubmitted: false, searchError: ""});
    }
    searchInput(event) {
        this.clearSearch();
        this.state.searchQuery = event.target.value;
    }
    async searchMessages(older = false) {
        const query = this.state.searchQuery.trim();
        if (!query || this.state.searchBusy) return;
        const id = this.state.detail.id;
        const version = this.navigationVersion;
        const request = this.searchVersion = (this.searchVersion || 0) + 1;
        this.state.searchBusy = true;
        this.state.searchError = "";
        try {
            const detail = await this.call("ab_crm_conversation", "workspace_detail", [[id]], {query, before_id: older ? this.state.searchResults.at(-1)?.id : false});
            if (this.destroyed || version !== this.navigationVersion || request !== this.searchVersion || this.state.detail?.id !== id) return;
            const results = [...detail.messages].reverse();
            this.state.searchResults = older ? [...this.state.searchResults, ...results] : results;
            this.state.searchOlder = detail.has_older;
            this.state.searchSubmitted = true;
        } catch (error) {
            if (request === this.searchVersion && version === this.navigationVersion) this.state.searchError = feedbackError(this, error);
        } finally { if (request === this.searchVersion) this.state.searchBusy = false; }
    }
    async acknowledgeVisible() {
        if (document.visibilityState !== "visible" || !document.hasFocus() || this.state.historyContext || this.focusingAlert || this.destroyed || !this.state.loggedIn || this.state.searchOpen || this.state.busy || this.refreshing || this.reading || this.chatterSession.focusHandler !== this.focusHandler) return;
        const id = this.state.detail?.id;
        const messageId = visibleMessageId(this.messagesRef.el);
        const key = `${this.state.token}:${id}`;
        if (!id || !messageId || messageId <= (this.acknowledged.get(key) || 0)) return;
        this.reading = true;
        try {
            await this.call("ab_crm_conversation", "workspace_acknowledge", [[id], messageId]);
            this.acknowledged.set(key, messageId);
            this.chatterSession.unreadChanged();
        } catch (error) { this.feedback?.report(error); }
        finally { this.reading = false; }
    }
    time(value) { return messageDate(value)?.toLocaleString({hour: "2-digit", minute: "2-digit"}) || ""; }
    fullTime(value) { return messageDate(value)?.toLocaleString({dateStyle: "full", timeStyle: "short"}) || ""; }
    day(value) { return messageDate(value)?.toLocaleString({dateStyle: "long"}) || ""; }
    newDay(index) { return !index || this.day(this.state.detail.messages[index - 1].timestamp) !== this.day(this.state.detail.messages[index].timestamp); }
    useLocation(message) { return this.createOrder(message.id); }

}
registry.category("actions").add("ab_crm_sales_workspace.workspace", SalesWorkspace);

registry.category("actions").add("ab_crm_sales_workspace.orders", SalesWorkspace);
