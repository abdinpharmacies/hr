import { PortalChatter } from "@portal/chatter/frontend/portal_chatter";
import { Component, onMounted, onWillUnmount, useState } from "@odoo/owl";
import { rpc } from "@web/core/network/rpc";
import { patch } from "@web/core/utils/patch";

const PortalChatterBase = PortalChatter.components.Chatter;

export class OrderChatter extends PortalChatterBase {
    static template = "ab_storefront_callcenter_adapter.OrderChatter";
    setup() {
        super.setup();
        this.abRefresh = useState({ running: false, unavailable: false, closed: Boolean(this.websiteOrder?.dataset.closed), ready: false });
        this.abActive = true;
        this.abRecover = () => this.refreshWebsiteMessages();
        onMounted(() => {
            if (!this.websiteOrder) return;
            this.abRecover();
            this.abTimer = setInterval(this.abRecover, 5000);
            window.addEventListener("online", this.abRecover);
            document.addEventListener("visibilitychange", this.abRecover);
        });
        onWillUnmount(() => {
            this.abActive = false;
            clearInterval(this.abTimer);
            window.removeEventListener("online", this.abRecover);
            document.removeEventListener("visibilitychange", this.abRecover);
        });
    }
    get websiteOrder() {
        return this.props.threadModel === "sale.order" && document.querySelector(`[data-ab-order-chatter="${this.props.threadId}"]`);
    }
    async refreshWebsiteMessages() {
        const thread = this.state.thread;
        if (!this.abActive || !this.websiteOrder || document.hidden || this.abRefresh.running || !thread || thread.status === "loading") return;
        this.abRefresh.running = true;
        const scrollTop = this.rootRef.el?.scrollTop;
        const windowY = window.scrollY;
        try {
            const status = await rpc("/storefront-callcenter/order/status", { order_id: this.props.threadId });
            this.abRefresh.closed = status.closed;
            this.abRefresh.ready = status.ready;
            let after = Math.max(0, ...thread.messages.map(message => Number.isInteger(message.id) ? message.id : 0));
            let rows;
            do {
                rows = await thread.fetchMessages({ after });
                if (!this.abActive || this.state.thread !== thread) return;
                for (const message of rows) {
                    if (!thread.messages.some(row => row.id === message.id)) thread.messages.add(message);
                }
                after = Math.max(after, ...rows.map(message => message.id));
            } while (rows.length >= this.store.FETCH_LIMIT && this.abActive);
            this.abRefresh.unavailable = false;
            requestAnimationFrame(() => {
                if (!this.abActive) return;
                if (this.rootRef.el) this.rootRef.el.scrollTop = scrollTop;
                if (window.scrollY === windowY) window.scrollTo(window.scrollX, windowY);
            });
        } catch { this.abRefresh.unavailable = true; }
        finally { this.abRefresh.running = false; }
    }
}

export class ScopedOrderChatter extends Component {
    static template = "ab_storefront_callcenter_adapter.ScopedOrderChatter";
    static props = PortalChatterBase.props;
    get component() {
        return this.props.threadModel === "sale.order" && document.querySelector(`[data-ab-order-chatter="${this.props.threadId}"]`) ? OrderChatter : PortalChatterBase;
    }
}

patch(PortalChatter, { components: { ...PortalChatter.components, Chatter: ScopedOrderChatter } });
