import {Component, onMounted, onWillUnmount, useRef, useState, useExternalListener} from "@odoo/owl";
import {Dialog} from "@web/core/dialog/dialog";
import {ABMany2one} from "@ab_widgets/ab_many2one";
import {useHotkey} from "@web/core/hotkeys/hotkey_hook";
import {localization} from "@web/core/l10n/localization";
import {_t} from "@web/core/l10n/translation";

class OrderFrame extends Dialog {
    static props = {...Dialog.props, requestClose: Function};
    dismiss() { return this.props.requestClose(); }
}

export class OrderDialog extends Component {
    static template = "ab_crm_sales_workspace.OrderDialog";
    static components = {OrderFrame, ABMany2one};
    static props = {order: Object, orders: Array, cachedDrafts: Object, call: Function, context: Object, onSaved: Function, close: Function};
    setup() {
        this.title = _t("Channel order");
        this.direction = localization.direction;
        this.state = useState({order: structuredClone(this.props.order), products: [], query: "", category: "all", minimum: "", maximum: "", busy: false, error: "", closing: false, branch: false, reprice: false, history: false, reason: ""});
        this.searchRef = useRef("search");
        this.cardsRef = useRef("cards");
        this.state.selectionIndex = 0;
        this.state.qtyBuffer = "";
        this.state.maximized = true;
        this.state.minimized = false;
        this.choices = useState(this.props.orders.map(order => ({...order})));
        this.pendingDrafts = new Map([...this.props.cachedDrafts].filter(([id]) => this.props.orders.some(order => order.id === id)));
        const cached = this.pendingDrafts.get(this.props.order.id);
        if (cached) { this.state.order = JSON.parse(JSON.stringify(cached.order)); this.state.reprice = cached.reprice; }
        onMounted(() => this.searchRef.el?.focus());
        onWillUnmount(() => {
            clearTimeout(this.quantityTimer);
            if (!this.discarded) this.rememberDraft();
            for (const draft of this.choices) this.props.cachedDrafts.delete(draft.id);
            for (const [id, draft] of this.pendingDrafts) {
                if (JSON.stringify(draft.order) !== draft.saved) this.props.cachedDrafts.set(id, draft);
            }
        });
        useExternalListener(window, "keydown", event => {
            if (event.key === "F2") { event.preventDefault(); this.searchRef.el?.focus(); }
        });
        this.saved = cached?.saved || JSON.stringify(this.state.order);
        this.nextLine = Math.min(-1, ...this.state.order.lines.map(line => line.id - 1));
        useHotkey("control+s", () => this.save(), {bypassEditableProtection: true});
    }
    get draftChoices() { return this.choices; }
    rememberDraft() {
        this.pendingDrafts.set(this.state.order.id, {order: JSON.parse(JSON.stringify(this.state.order)), saved: this.saved, reprice: this.state.reprice});
    }
    discard() { this.discarded = true; this.pendingDrafts.clear(); this.props.close(); }
    updateChoice() {
        const choice = this.choices.find(order => order.id === this.state.order.id);
        if (choice) Object.assign(choice, {state: this.state.order.state, revision: this.state.order.revision});
    }
    async switchDraft(id) {
        if (id === this.state.order.id || this.state.busy) return;
        this.rememberDraft();
        await this.run(async () => {
            const cached = this.pendingDrafts.get(id);
            this.state.order = cached?.order || await this.props.call("ab_crm_channel_order", "workspace_data", [[id]]);
            this.saved = cached?.saved || JSON.stringify(this.state.order);
            this.state.reprice = cached?.reprice || false;
            this.state.products = [];
            this.state.branch = false;
            this.state.reason = "";
            this.nextLine = Math.min(-1, ...this.state.order.lines.map(line => line.id - 1));
        });
    }
    toggleMaximize() { this.state.maximized = !this.state.maximized; this.state.minimized = false; }
    async fullScreen() {
        this.state.minimized = false;
        const element = this.searchRef.el?.closest(".ab_chatter_order_modal");
        try {
            if (document.fullscreenElement) await document.exitFullscreen();
            else await element?.requestFullscreen();
        } catch (error) { this.state.error = error.message; }
    }
    productCard(product) {
        return {...product, default_price: product.price, pos_balance: product.balance,
            total_balance_unavailable: product.balance === null};
    }
    productLabel(product) { return product.name; }
    formatPrice(value) { return Number(value || 0).toFixed(2); }
    formatQty(value) { return Number(value || 0).toLocaleString(); }
    showBalance(product) { this.state.balance = product; }
    async searchKeydown(event) {
        if (event.key === "ArrowDown" && this.state.products.length) {
            event.preventDefault();
            this.state.selectionIndex = 0;
            this.cardsRef.el?.querySelector('[role="button"]')?.focus();
        }
    }
    cardKeydown(event) {
        const index = this.state.selectionIndex;
        if (["ArrowDown", "ArrowUp", "ArrowLeft", "ArrowRight"].includes(event.key)) {
            event.preventDefault();
            const backward = event.key === "ArrowUp" || event.key === (this.direction === "rtl" ? "ArrowRight" : "ArrowLeft");
            this.state.selectionIndex = Math.max(0, Math.min(this.state.products.length - 1, index + (backward ? -1 : 1)));
            this.cardsRef.el?.querySelectorAll('[role="button"]')[this.state.selectionIndex]?.focus();
        } else if (/^[0-9]$/.test(event.key)) {
            event.preventDefault();
            this.state.qtyBuffer = (this.state.qtyBuffer + event.key).slice(0, 5);
            clearTimeout(this.quantityTimer);
            this.quantityTimer = setTimeout(() => { this.state.qtyBuffer = ""; }, 2000);
        } else if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            this.add(this.state.products[index]);
            this.searchRef.el?.focus();
        } else if (event.key === "Escape") {
            this.state.qtyBuffer = "";
            this.searchRef.el?.focus();
        }
    }
    changeQuantity(line, delta) { line.quantity = Math.max(1, Number(line.quantity) + delta); }
    get editable() { return this.state.order.state === "draft"; }
    get total() { return this.state.order.lines.reduce((total, line) => total + Number(line.quantity) * Number(line.price), 0); }
    get store() { return this.state.order.stores.find(store => store.id === this.state.order.store_id) || false; }
    branchDomain() { return [["id", "in", this.state.order.stores.map(store => store.id)]]; }
    unitDomain(line) { return [["id", "in", (this.state.order.units[line.id] || []).map(unit => unit.id)]]; }
    unit(line) { return (this.state.order.units[line.id] || []).find(unit => unit.id === line.uom_id) || false; }
    async run(action) {
        if (this.state.busy) return false;
        this.state.busy = true;
        this.state.error = "";
        try { await action(); return true; }
        catch (error) { this.state.error = error.data?.message || error.message || _t("Operation failed."); return false; }
        finally { this.state.busy = false; }
    }
    close() {
        if (this.state.busy) return;
        if ((this.editable && JSON.stringify(this.state.order) !== this.saved) || [...this.pendingDrafts.values()].some(draft => JSON.stringify(draft.order) !== draft.saved)) this.state.closing = true;
        else this.props.close();
    }
    selectBranch(value) {
        if (!value || value.id === this.state.order.store_id) return;
        if (this.state.order.lines.length) this.state.branch = value;
        else return this.applyBranch(value);
    }
    async applyBranch(value = this.state.branch) {
        await this.run(async () => {
            const rows = await this.props.call("ab_crm_channel_order", "preview_branch", [[this.state.order.id], value.id, [...new Set(this.state.order.lines.map(line => line.product_id))]]);
            const replacements = this.state.order.lines.map(line => {
                const product = rows.find(row => row.id === line.product_id);
                const unit = product.units.find(unit => unit.id === line.uom_id);
                if (!unit) throw new Error(_t("The selected unit is unavailable in this branch."));
                return {...line, price: product.price * unit.factor / product.factor};
            });
            this.state.order.lines = replacements;
            for (const line of replacements) this.state.order.units[line.id] = rows.find(row => row.id === line.product_id).units;
            this.state.order.store_id = value.id;
            this.state.reprice = true;
            this.state.branch = false;
            this.state.products = [];
        });
    }
    async search() {
        await this.run(async () => {
            this.state.products = await this.props.call("ab_crm_channel_order", "search_products", [[this.state.order.id]], {query: this.state.query, store_id: this.state.order.store_id, category: this.state.category, minimum: this.state.minimum === "" ? false : Number(this.state.minimum), maximum: this.state.maximum === "" ? false : Number(this.state.maximum)});
            this.state.selectionIndex = 0;
            if (this.state.products.length === 1 && this.state.products[0].barcode_match) { this.add(this.state.products[0], true); this.state.query = ""; }
        });
    }
    add(product, fromSearch = false) {
        if (!this.editable || !product || (this.state.busy && !fromSearch)) return;
        const quantity = Math.max(1, Number(this.state.qtyBuffer || 1));
        this.state.qtyBuffer = "";
        const existing = this.state.order.lines.find(line => line.product_id === product.id && line.uom_id === product.uom_id);
        if (existing) { existing.quantity = Number(existing.quantity) + quantity; return; }
        const id = this.nextLine--;
        this.state.order.lines.push({id, product_id: product.id, product: product.name, quantity, price: product.price, uom_id: product.uom_id});
        this.state.order.units[id] = product.units;
    }
    updateUnit(line, value) {
        const previous = this.unit(line);
        const selected = this.state.order.units[line.id].find(unit => unit.id === value?.id);
        if (selected) { line.price = Number(line.price) * selected.factor / (previous?.factor || 1); line.uom_id = selected.id; }
    }
    remove(line) { this.state.order.lines = this.state.order.lines.filter(row => row.id !== line.id); }
    async save(accept = false, close = false) {
        if (!this.editable) return;
        const success = await this.run(async () => {
            const order = this.state.order;
            const result = await this.props.call("ab_crm_channel_order", "action_save_draft", [[order.id]], {
                values: {store_id: order.store_id || false, delivery_address: order.delivery_address || "", delivery_notes: order.delivery_notes || "", confirmation: order.confirmation || ""},
                lines: order.lines.map(line => ({id: line.id > 0 ? line.id : false, product_id: line.product_id, quantity: Number(line.quantity), price: Number(line.price), uom_id: line.uom_id})),
                edit_version: order.edit_version, reprice: this.state.reprice, accept,
            });
            this.state.order = result;
            this.state.reprice = false;
            this.saved = JSON.stringify(result);
            this.updateChoice();
            this.pendingDrafts.delete(result.id);
            this.state.closing = false;
            await this.props.onSaved();
        });
        if (success && close) this.close();
    }
    async transition(method) {
        await this.run(async () => {
            const args = [[this.state.order.id]];
            if (method !== "action_close") args.push(this.state.reason);
            await this.props.call("ab_crm_channel_order", method, args);
            this.state.order = await this.props.call("ab_crm_channel_order", "workspace_data", [[this.state.order.id]]);
            this.saved = JSON.stringify(this.state.order);
            this.updateChoice();
            await this.props.onSaved();
        });
    }
    channelLabel() { return {telegram: _t("Telegram"), whatsapp: _t("WhatsApp"), website: _t("Website")}[this.state.order.provider] || this.state.order.provider; }
    auditLabel(action) { return {created: _t("Created"), line_added: _t("Line added"), line_changed: _t("Line changed"), branch_changed: _t("Fulfillment branch"), accepted: _t("Accepted"), reopened: _t("Reopened"), closed: _t("Closed"), cancelled: _t("Cancelled")}[action] || action; }
    balanceLabel(product) {
        return {unavailable: _t("Balance unavailable"), stale: _t("Stale balance"), cached: _t("Cached balance")}[product.balance_state];
    }
    stateLabel(value) { return {draft: _t("Draft"), accepted: _t("Accepted"), closed: _t("Closed"), cancelled: _t("Cancelled")}[value] || value; }
}
