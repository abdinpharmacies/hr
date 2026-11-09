import {Component, onMounted, onPatched, onWillStart, onWillUnmount, useState, useRef, useEffect, useExternalListener} from "@odoo/owl";
import {Dialog} from "@web/core/dialog/dialog";
import {deserializeDateTime} from "@web/core/l10n/dates";
import {user} from "@web/core/user";

export function messageDate(timestamp) {
    return timestamp ? deserializeDateTime(timestamp, {tz: user.context.tz}) : null;
}

export function compactUpdateTime(timestamp, now = luxon.DateTime.now()) {
    const date = messageDate(timestamp);
    if (!date) return "";
    const today = now.setZone(date.zone);
    const age = today.startOf("day").diff(date.startOf("day"), "days").days;
    if (age === 0) return date.toLocaleString({hour: "numeric", minute: "2-digit"});
    if (age > 0 && age < 7) return date.toLocaleString({weekday: "short"});
    return date.toLocaleString({month: "short", day: "numeric"});
}

export function visibleMessageId(container) {
    if (!container || document.visibilityState !== "visible" || document.body.classList.contains("modal-open")) return null;
    const bounds = container.getBoundingClientRect();
    return [...container.querySelectorAll("[data-message-id]")].filter(element => {
        const rect = element.getBoundingClientRect();
        return rect.bottom > bounds.top && rect.bottom <= bounds.bottom && rect.right > bounds.left && rect.left < bounds.right;
    }).map(element => Number(element.dataset.messageId)).at(-1) || null;
}

export function mediaBlob(result) {
    const raw = Uint8Array.from(atob(result.data), character => character.charCodeAt(0));
    return new Blob([raw], {type: result.mimetype});
}

export class MessageQuote extends Component {
    static template = "ab_crm_sales_workspace.MessageQuote";
    static props = {quote: Object, call: Function, open: Function, cancel: {type: Function, optional: true}};
    setup() {
        this.state = useState({url: ""});
        this.destroyed = false;
        onWillStart(async () => {
            const media = this.props.quote.thumbnail;
            if (!media) return;
            try {
                const result = await this.props.call("ab_crm_message_media", "download", [[media.id]]);
                if (!this.destroyed) this.state.url = URL.createObjectURL(mediaBlob(result));
            } catch { }
        });
        onWillUnmount(() => { this.destroyed = true; if (this.state.url) URL.revokeObjectURL(this.state.url); });
    }
}

export class MessagePreview extends Component {
    static template = "ab_crm_sales_workspace.MessagePreview";
    static components = {Dialog};
    static props = {url: String, media: Object, close: Function, provider: {type: String, optional: true}};
    get theme() { return this.props.provider === "whatsapp" ? "whatsapp" : "telegram"; }
    setup() {
        onWillUnmount(() => URL.revokeObjectURL(this.props.url));
    }
}

export class MessageActions extends Component {
    static template = "ab_crm_sales_workspace.MessageActions";
    static props = {message: Object, reply: Function, react: Function, copy: Function, preview: Function, retry: Function, busy: {type: Boolean, optional: true}};
    setup() {
        this.root = useRef("root");
        this.menu = useRef("menu");
        this.state = useState({open: false, reactions: false, x: 0, y: 0});
        this.contextHandler = event => {
            if (event.shiftKey || (event.target.isContentEditable || event.target.closest('input, textarea, a')) || window.getSelection()?.toString()) return;
            event.preventDefault();
            this.open(event.clientX, event.clientY, this.article);
        };
        this.keyboardHandler = event => {
            if (event.key !== "F10" || !event.shiftKey || event.target.isContentEditable || event.target.closest('input, textarea, a') || window.getSelection()?.toString()) return;
            event.preventDefault();
            this.openAt(this.article);
        };
        onMounted(() => {
            this.article = this.root.el.closest("article");
            this.article.addEventListener("contextmenu", this.contextHandler);
            this.article.addEventListener("keydown", this.keyboardHandler);
        });
        onWillUnmount(() => {
            this.article.removeEventListener("contextmenu", this.contextHandler);
            this.article.removeEventListener("keydown", this.keyboardHandler);
        });
        useExternalListener(document, "pointerdown", event => { if (this.state.open && !this.root.el?.contains(event.target)) this.close(false); });
        useExternalListener(document, "focusin", event => { if (this.state.open && !this.root.el?.contains(event.target)) this.close(false); });
        useExternalListener(window, "resize", () => this.close());
        useExternalListener(document, "scroll", event => { if (this.state.open && !this.menu.el?.contains(event.target)) this.close(); }, {capture: true});
        onPatched(() => {
            if (!this.state.open || !this.menu.el) return;
            const menu = this.menu.el;
            const bounds = menu.getBoundingClientRect();
            menu.style.left = `${Math.max(8, Math.min(this.state.x, window.innerWidth - bounds.width - 8))}px`;
            menu.style.top = `${Math.max(8, Math.min(this.state.y, window.innerHeight - bounds.height - 8))}px`;
            if (this.focusMenu) { menu.querySelector("button:not(:disabled)")?.focus(); this.focusMenu = false; }
        });
    }
    open(x, y, origin) {
        this.origin = origin;
        this.state.x = x;
        this.state.y = y;
        this.state.reactions = false;
        this.state.open = true;
        this.focusMenu = true;
    }
    openAt(origin) {
        const bounds = origin.getBoundingClientRect();
        this.open(getComputedStyle(origin).direction === "rtl" ? bounds.left : bounds.right, bounds.bottom, origin);
    }
    toggle(event) { if (this.state.open) this.close(); else this.openAt(event.currentTarget); }
    close(restore = true) {
        if (!this.state.open) return;
        this.state.open = false;
        if (restore && this.origin?.isConnected) this.origin.focus({preventScroll: true});
    }
    choose(action, ...args) {
        if (this.props.busy) return;
        this.close();
        this.props[action](...args);
    }
    keydown(event) {
        if (event.key === "Escape") { event.preventDefault(); event.stopPropagation(); this.close(); }
        if (event.key === "Tab") this.close(false);
        if (["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) {
            event.preventDefault();
            const buttons = [...this.menu.el.querySelectorAll("button:not(:disabled)")];
            const current = buttons.indexOf(document.activeElement);
            const index = event.key === "Home" ? 0 : event.key === "End" ? buttons.length - 1 : (current + (event.key === "ArrowDown" ? 1 : -1) + buttons.length) % buttons.length;
            buttons[index]?.focus();
        }
    }
}

export function formatMediaSize(size) {
    if (!size) return "";
    if (size < 1024) return `${size} B`;
    if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
    return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

export class MessageMedia extends Component {
    static template = "ab_crm_sales_workspace.MessageMedia";
    static props = {media: Object, call: Function, preview: Function};
    setup() {
        this.root = useRef("media");
        this.state = useState({url: "", loading: false, failed: false});
        useEffect(() => {
            let disposed = false;
            let url = "";
            let observer;
            this.state.url = "";
            this.state.failed = false;
            this.state.loading = false;
            if (this.props.media.kind === "image" && this.props.media.state === "ready") {
                const load = async () => {
                    this.state.loading = true;
                    try {
                        const result = await this.props.call("ab_crm_message_media", "download", [[this.props.media.id]]);
                        if (!disposed) { url = URL.createObjectURL(mediaBlob(result)); this.state.url = url; }
                    } catch { if (!disposed) this.state.failed = true; }
                    finally { if (!disposed) this.state.loading = false; }
                };
                observer = new IntersectionObserver(entries => {
                    if (entries.some(entry => entry.isIntersecting)) { observer.disconnect(); load(); }
                }, {root: this.root.el.closest(".ab_messages"), rootMargin: "100px"});
                observer.observe(this.root.el);
            }
            return () => { disposed = true; observer?.disconnect(); if (url) URL.revokeObjectURL(url); };
        }, () => [this.props.media.id, this.props.media.state]);
    }
    get size() { return formatMediaSize(this.props.media.size); }
}
