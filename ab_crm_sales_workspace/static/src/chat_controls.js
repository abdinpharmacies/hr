/** @odoo-module **/

import {user} from "@web/core/user";
import {patch} from "@web/core/utils/patch";
import {SalesWorkspace} from "./workspace";

patch(SalesWorkspace.prototype, {
    setup() {
        super.setup();
        this.websiteTargets = new Map();
        this.websiteScroll = new Map();
    },
    async acknowledgeRead(messageId) {
        if (this.state.detail?.provider === "website" && !this.state.detail.messages.some(
            message => message.id === messageId && message.website_target)) return false;
        return super.acknowledgeRead(messageId);
    },
    draftKey(id) {
        const target = this.state.detail?.id === id ? this.state.detail.website_target : this.websiteTargets?.get(id);
        return target ? `${id}:${target.kind}:${target.uuid}` : super.draftKey(id);
    },
    async call(model, method, args = [], kwargs = {}) {
        if (model === "ab_crm_conversation" && ["workspace_detail", "workspace_updates"].includes(method)) {
            const id = args[0]?.[0];
            const initial = this.props?.action?.context?.chatter_alert;
            const target = kwargs.target || this.websiteTargets?.get(id) ||
                (initial?.conversation_id === id ? initial.website_target : null) ||
                (this.initialSelection?.conversationId === id ? this.initialSelection.websiteTarget : null) ||
                this.state.inbox?.find(item => item.id === id)?.website_target;
            kwargs = {...kwargs, combine: false};
            if (target) kwargs.target = target;
        }
        if (model === "ab_crm_conversation" && ["workspace_acknowledge", "workspace_reply"].includes(method) && this.state.detail?.website_target) {
            const messageId = args[1];
            const message = this.state.detail.messages.find(item => item.id === messageId);
            kwargs = {...kwargs, target: message?.website_target || this.state.detail.website_target,
                combine: false};
        }
        const company = user.activeCompany.id;
        const version = this.navigationVersion;
        const token = this.state.token;
        const result = await super.call(model, method, args, kwargs);
        if (!this.destroyed && company === user.activeCompany.id && version === this.navigationVersion && token === this.state.token && result?.website_target && model === "ab_crm_conversation" && ["workspace_detail", "workspace_channel", "workspace_focus"].includes(method)) {
            this.websiteTargets.set(result.id, result.website_target);
        }
        return result;
    },
    async selectCustomer(item) {
        if (!item.website_target) return super.selectCustomer(item);
        if (this.state.busy || this.state.navigating) return;
        return this.select(item.id, false, null, item.website_target);
    },
    async select(id, channel = false, focusedDetail = null, target = null) {
        this.rememberDraft();
        if (target) this.websiteTargets.set(id, target);
        if (focusedDetail?.website_target) this.websiteTargets.set(id, focusedDetail.website_target);
        return super.select(id, channel, focusedDetail);
    },
    selectedStream(item) {
        if (item.website_target && (item.website_target.uuid !== this.state.detail?.website_target?.uuid
            || item.website_target.kind !== this.state.detail?.website_target?.kind)) return null;
        return super.selectedStream(item);
    },
    async loadCustomerInbox(pages = this.inboxPages || 1) {
        const items = [];
        let cursor = null;
        let result = {has_more: false};
        for (let page = 0; page < pages; page++) {
            result = await this.call("ab_crm_conversation", "workspace_customer_inbox", [], {
                query: this.state.inboxQuery, cursor});
            items.push(...result.items);
            cursor = result.next_cursor;
            if (!result.has_more) break;
        }
        return {items, has_more: result.has_more};
    },
});
