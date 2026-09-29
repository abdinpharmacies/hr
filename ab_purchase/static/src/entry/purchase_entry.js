/** @odoo-module **/
import { Component, onPatched, onWillStart, useRef, useState } from "@odoo/owl";
import { AutoComplete } from "@web/core/autocomplete/autocomplete";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { useSetupAction } from "@web/search/action_hook";
import { formatFloat } from "@web/views/fields/formatters";

export class PurchaseDataEntry extends Component {
    static template = "ab_purchase.DataEntry";
    static components = { AutoComplete };
    static props = { "*": true };
    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.dialog = useService("dialog");
        this.selectSupplier = this.selectSupplier.bind(this);
        this.lookupVersions = {};
        this.key = 0;
        this.refs = Object.fromEntries(["productSearch", "documentNumber", "quickQty", "quickPurchase", "quickSelling"].map((name) => [name, useRef(name)]));
        onPatched(() => { if (this.pendingFocus) { const name = this.pendingFocus; this.pendingFocus = null; setTimeout(() => this.focus(name), 0); } });
        this.state = useState({ loading: true, error: false, saving: false, dirty: false, kind: "purchase",
            config: { stores: [], taxes: [], drafts: [] }, doc: {}, productQuery: "", supplierQuery: "", invoiceQuery: "",
            products: [], suppliers: [], invoices: [], productIndex: 0, quick: null });
        useSetupAction({ beforeLeave: () => this.confirmDiscard(), beforeUnload: (event) => {
            if (this.state.dirty) { event.preventDefault(); event.returnValue = ""; }
        } });
        onWillStart(() => this.start());
    }
    async start() {
        this.state.loading = true;
        this.state.error = false;
        try { this.state.config = await this.orm.call("ab_purchase_header", "entry_bootstrap", []); this.reset(); }
        catch (error) { this.state.error = true; this.showError(error); }
        finally { this.state.loading = false; }
    }
    reset() {
        this.state.doc = { id: false, store_id: this.state.doc.store_id || this.state.config.stores[0]?.id || false,
            supplier_id: false, supplier: "", doc_code: "", doc_date: this.state.config.date, invoice_type: "medical",
            net_invoice: 0, net_tax: 0, total_extra_discount: 0, description: "", purchase_header_id: false, lines: [] };
        this.state.dirty = false;
        this.state.productQuery = this.state.supplierQuery = this.state.invoiceQuery = "";
        this.state.products = []; this.state.suppliers = []; this.state.invoices = [];
        this.state.quick = null; this.state.productIndex = 0;
        for (const kind of ["product", "supplier", "invoice"]) { this.lookupVersions[kind] = (this.lookupVersions[kind] || 0) + 1; }
    }
    async confirmDiscard() {
        if (this.state.saving) { return false; }
        if (!this.state.dirty) { return true; }
        return new Promise((resolve) => this.dialog.add(ConfirmationDialog, {
            title: _t("Unsaved entry"), body: _t("Discard the changes you have not saved?"),
            confirmLabel: _t("Discard"), confirm: () => resolve(true), cancel: () => resolve(false),
        }, { onClose: () => resolve(false) }));
    }
    async newDocument(kind = this.state.kind) {
        if (!(await this.confirmDiscard())) { return; }
        this.state.kind = kind; this.reset();
    }
    async loadDraft(draft) {
        if (!(await this.confirmDiscard())) { return; }
        this.state.saving = true;
        try {
            const doc = await this.orm.call("ab_purchase_header", "entry_load", [draft.kind, draft.id]);
            this.state.kind = draft.kind; this.reset(); this.setDocument(doc);
        } catch (error) { this.showError(error); }
        finally { this.state.saving = false; }
    }
    setDocument(doc) {
        this.state.doc = { ...this.state.doc, ...doc, lines: doc.lines.map((line) => ({ ...line, key: ++this.key })) };
        this.state.supplierQuery = doc.supplier || ""; this.state.invoiceQuery = doc.invoice || ""; this.state.dirty = false;
    }
    setHeader(name, event) {
        const numeric = ["store_id", "net_invoice", "net_tax", "total_extra_discount"].includes(name);
        this.state.doc[name] = numeric ? Number(event.target.value) : event.target.value;
        this.state.dirty = true;
        if (name === "store_id" && this.state.kind === "return") {
            this.state.doc.purchase_header_id = false; this.state.doc.lines = [];
            this.state.doc.supplier_id = false; this.state.doc.supplier = ""; this.state.invoiceQuery = "";
        }
    }
    documentKeydown(event) {
        if (event.key === "Enter" && this.state.kind === "purchase") {
            event.preventDefault(); this.focus("productSearch");
        }
    }
    setLine(line, name, event) {
        line[name] = name === "exp_date" ? event.target.value : Number(event.target.value);
        this.state.dirty = true;
    }
    toggleTax(line, tax, event) {
        line.taxes_ids = event.target.checked ? [...new Set([...line.taxes_ids, tax.id])]
            : line.taxes_ids.filter((id) => id !== tax.id);
        this.state.dirty = true;
    }
    selectedTaxes(line) { return this.state.config.taxes.filter((tax) => line.taxes_ids.includes(tax.id)); }
    async lookup(kind, event) {
        const query = event.target.value;
        this.state[`${kind}Query`] = query;
        if (kind === "supplier") { this.state.doc.supplier_id = false; this.state.dirty = true; }
        const version = (this.lookupVersions[kind] || 0) + 1;
        this.lookupVersions[kind] = version;
        try {
            const rows = await this.orm.call("ab_purchase_header", "entry_lookup", [kind, query, this.state.doc.store_id]);
            if (this.lookupVersions[kind] === version) { this.state[`${kind}s`] = rows; if (kind === "product") { this.state.productIndex = 0; } }
        } catch (error) { this.showError(error); }
    }
    selectSupplier(supplier) {
        this.state.doc.supplier_id = supplier.id; this.state.doc.supplier = supplier.name;
        this.state.supplierQuery = supplier.name; this.state.suppliers = []; this.state.dirty = true;
        this.pendingFocus = this.state.doc.doc_code ? "productSearch" : "documentNumber";
    }
    get supplierAutocompleteProps() {
        return { value: this.state.supplierQuery, placeholder: _t("Search supplier name or code"), autoSelect: true,
            onChange: ({ inputValue }) => {
                if (inputValue !== this.state.doc.supplier) {
                    this.state.supplierQuery = inputValue; this.state.doc.supplier_id = false;
                    this.state.doc.supplier = ""; this.state.dirty = true;
                }
            },
            inputDebounceDelay: 150, onInput: ({ inputValue }) => {
                this.state.doc.supplier_id = false;
                this.state.doc.supplier = ""; this.state.dirty = true;
            }, sources: [{ options: async (query) => {
                try {
                    const rows = await this.orm.call("ab_purchase_header", "entry_lookup", ["supplier", query, this.state.doc.store_id]);
                    return rows.map((row) => ({ label: row.code ? `${row.name} (${row.code})` : row.name,
                        onSelect: () => this.selectSupplier(row) }));
                } catch (error) { this.showError(error); return []; }
            } }] };
    }
    focus(name) {
        const input = this.refs[name]?.el;
        if (input) { input.focus(); input.select?.(); }
        else { this.pendingFocus = name; }
    }
    chooseProduct(product) {
        if (this.state.quick && !this.commitProduct()) { return; }
        this.state.quick = { product_id: product.id, name: product.name, code: product.code,
            units: product.units, uom_id: product.uom_id, qty: 1, bonus: 0, price: product.price,
            purchase_price: product.purchase_price, extra_discount_percentage: 0, taxes_ids: [], exp_date: this.state.config.expiry };
        this.state.productQuery = ""; this.state.products = []; this.state.dirty = true;
        this.lookupVersions.product = (this.lookupVersions.product || 0) + 1;
        this.focus("quickQty");
    }
    commitProduct() {
        const row = this.state.quick;
        if (!row) { return true; }
        if (![row.qty, row.bonus, row.purchase_price, row.price].every((value) => Number.isFinite(value) && value >= 0)
            || (!row.qty && !row.bonus) || !Number.isInteger(row.bonus)) {
            this.notification.add(_t("Enter a positive quantity or bonus and valid non-negative prices."), { type: "warning" });
            this.focus("quickQty"); return false;
        }
        this.state.doc.lines.push({ ...row, key: ++this.key });
        this.state.quick = null; this.state.dirty = true; this.focus("productSearch");
        return true;
    }
    quickKeydown(event, next) {
        if (event.key === "Enter") {
            event.preventDefault();
            if (event.ctrlKey || !next) { this.commitProduct(); }
            else { this.focus(next); }
        } else if (event.key === "Escape") {
            event.preventDefault(); this.state.quick = null; this.focus("productSearch");
        }
    }
    gridKeydown(event) {
        if (event.key !== "Enter" || event.target.tagName !== "INPUT") { return; }
        event.preventDefault();
        const row = event.target.closest("tr");
        const field = event.target.getAttribute("aria-label");
        const next = this.state.kind === "return" ? { Quantity: "Bonus" }
            : { Quantity: "Purchase price", "Purchase price": "Selling price", "Selling price": "Bonus" };
        const target = !event.ctrlKey && next[field] ? row.querySelector(`input[aria-label="${next[field]}"]`)
            : row.nextElementSibling?.querySelector('input[aria-label="Quantity"]');
        if (target) { target.focus(); target.select(); }
        else if (this.state.kind === "purchase") { this.focus("productSearch"); }
    }
    productKeydown(event) {
        if (["ArrowDown", "ArrowUp"].includes(event.key) && this.state.products.length) {
            event.preventDefault();
            this.state.productIndex = (this.state.productIndex + (event.key === "ArrowDown" ? 1 : -1) + this.state.products.length) % this.state.products.length;
        } else if (event.key === "Enter") {
            event.preventDefault();
            if (this.state.products.length) { this.chooseProduct(this.state.products[this.state.productIndex] || this.state.products[0]); }
        } else if (event.key === "Escape") { this.state.products = []; }
    }
    async selectInvoice(invoice) {
        this.state.saving = true;
        try {
            const doc = await this.orm.call("ab_purchase_header", "entry_invoice", [invoice.id]);
            Object.assign(this.state.doc, { purchase_header_id: doc.id, supplier_id: doc.supplier_id,
                supplier: doc.supplier, store_id: doc.store_id, lines: doc.lines.map((line) => ({ ...line, key: ++this.key })) });
            this.state.invoiceQuery = doc.code; this.state.invoices = []; this.state.dirty = true;
        } catch (error) { this.showError(error); }
        finally { this.state.saving = false; }
    }
    removeLine(line) { this.state.doc.lines = this.state.doc.lines.filter((row) => row.key !== line.key); this.state.dirty = true; }
    lineTotals(line) {
        const qty = Number(line.qty) || 0, bonus = Number(line.bonus) || 0;
        if (this.state.kind === "return") {
            return { tax: (qty + bonus) * line.unit_tax, cost: (qty * line.unit_purchase + (qty + bonus) * line.unit_tax) * line.factor };
        }
        const price = (Number(line.purchase_price) || 0) * (1 - (Number(line.extra_discount_percentage) || 0) / 100);
        const taxes = this.state.config.taxes.filter((tax) => line.taxes_ids.includes(tax.id));
        const baseTax = taxes.filter((tax) => !tax.apply_on_total).reduce((sum, tax) => sum + price * tax.percentage / 100, 0);
        const tax = baseTax + taxes.filter((tax) => tax.apply_on_total).reduce((sum, tax) => sum + (price + baseTax) * tax.percentage / 100, 0);
        return { tax: (qty + bonus) * tax, cost: qty * price + (qty + bonus) * tax };
    }
    get totals() {
        return this.state.doc.lines.reduce((sum, line) => { const row = this.lineTotals(line);
            return { cost: sum.cost + row.cost, tax: sum.tax + row.tax, qty: sum.qty + Number(line.qty || 0) }; },
            { cost: this.state.kind === "purchase" ? -Number(this.state.doc.total_extra_discount || 0) : 0, tax: 0, qty: 0 });
    }
    money(value) { return formatFloat(value || 0, { digits: [16, 3] }); }
    async save(next = false) {
        if (this.state.saving) { return; }
        if (!this.commitProduct()) { return; }
        if (this.state.kind === "purchase" && !this.state.doc.supplier_id) {
            this.notification.add(_t("Select a supplier from the suggestions."), { type: "warning" }); return;
        }
        this.state.saving = true;
        try {
            const doc = await this.orm.call("ab_purchase_header", "entry_save", [this.state.kind, JSON.parse(JSON.stringify(this.state.doc))]);
            this.setDocument(doc);
            this.notification.add(_t("Draft saved. Stock is unchanged."), { type: "success" });
            this.state.config = await this.orm.call("ab_purchase_header", "entry_bootstrap", []);
            if (next) { this.reset(); }
        } catch (error) { this.showError(error); }
        finally { this.state.saving = false; }
    }
    showError(error) { this.notification.add(error?.data?.message || error?.message || _t("Could not complete the entry."), { type: "danger" }); }
}
registry.category("actions").add("ab_purchase.data_entry", PurchaseDataEntry);
