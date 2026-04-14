/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { FormViewDialog } from "@web/views/view_dialogs/form_view_dialog";
import { Component, onMounted, onWillStart, useExternalListener, useRef, useState } from "@odoo/owl";

const ADD_PRODUCTS_FILTER_PREFS_KEY = "ab_sales_add_products_filters_v1";

class AbSalesAddProductsAction extends Component {
    static template = "ab_sales.AddProductsAction";
    static target = "new";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.dialog = useService("dialog");
        this.notification = useService("notification");

        const headerId =
            this.props?.action?.context?.active_id ||
            (this.props?.action?.context?.active_ids || [])[0] ||
            null;
        const storeName = this.props?.action?.context?.pos_store_name || "";
        const storeId =
            this.props?.action?.context?.pos_store_id ||
            this.props?.action?.context?.pos_store_id?.[0] ||
            null;
        const savedHasPosBalanceOnly = this._loadSavedHasPosBalanceOnly();

        this._productSearchTimer = null;

        this.searchInputRef = useRef("searchInput");
        this.cardsContainerRef = useRef("cardsContainer");

        this.state = useState({
            headerId,
            storeName,
            storeId: storeId ? parseInt(storeId, 10) : null,
            loading: true,
            query: "",
            hasBalanceOnly: true,
            hasPosBalanceOnly: savedHasPosBalanceOnly,
            products: [],
            selected: new Map(), // product_id -> {product, qty}
            selectionIndex: -1,
            qtyBuffer: "",
            qtyBufferProductId: null,
            applying: false,
        });

        this.addProduct = this.addProduct.bind(this);
        this.inc = this.inc.bind(this);
        this.dec = this.dec.bind(this);
        this.apply = this.apply.bind(this);
        this.back = this.back.bind(this);
        this.formatPrice = this.formatPrice.bind(this);
        this.formatQty = this.formatQty.bind(this);
        this.productLabel = this.productLabel.bind(this);
        this.openStoresBalance = this.openStoresBalance.bind(this);
        this.onSearchKeydown = this.onSearchKeydown.bind(this);
        this.onHasBalanceChange = this.onHasBalanceChange.bind(this);
        this.onHasPosBalanceChange = this.onHasPosBalanceChange.bind(this);
        this.schedulePosBalanceRefresh = this.schedulePosBalanceRefresh.bind(this);
        this._refreshPosBalancesForResults = this._refreshPosBalancesForResults.bind(this);
        this._saveHasPosBalanceOnly = this._saveHasPosBalanceOnly.bind(this);
        this._posBalanceTimer = null;
        this._posBalanceRequestId = 0;

        // Hotkey -> handler mapping (keep current behavior).
        this.shortcutHandlers = new Map([
            ["F2", this._onHotkeyF2.bind(this)],
            ["ArrowDown", this._onHotkeyArrowDown.bind(this)],
            ["ArrowUp", this._onHotkeyArrowUp.bind(this)],
            ["Enter", this._onHotkeyEnter.bind(this)],
        ]);

        useExternalListener(window, "keydown", (ev) => this.onKeydown(ev));

        onWillStart(async () => {
            await this.loadProducts("");
        });

        onMounted(() => {
            // Let the dialog mount/render first.
            setTimeout(() => this.searchInputRef.el?.focus(), 0);
        });
    }

    _loadSavedHasPosBalanceOnly() {
        try {
            const raw = localStorage.getItem(ADD_PRODUCTS_FILTER_PREFS_KEY);
            if (!raw) {
                return true;
            }
            const payload = JSON.parse(raw);
            if (typeof payload?.hasPosBalanceOnly === "boolean") {
                return payload.hasPosBalanceOnly;
            }
        } catch {
            // Ignore broken preference payload.
        }
        return true;
    }

    _saveHasPosBalanceOnly(value) {
        try {
            const payload = {
                hasPosBalanceOnly: !!value,
            };
            localStorage.setItem(ADD_PRODUCTS_FILTER_PREFS_KEY, JSON.stringify(payload));
        } catch {
            // Ignore localStorage write failures.
        }
    }

    _focusSearchSelectAll() {
        const el = this.searchInputRef.el;
        if (!el) {
            return;
        }
        // In dialogs, focusing/selecting is sometimes ignored unless deferred.
        setTimeout(() => {
            el.focus();
            if (typeof el.select === "function") {
                el.select();
            }
        }, 0);
        this.state.selectionIndex = -1;
        this.state.qtyBuffer = "";
        this.state.qtyBufferProductId = null;
    }

    _selectPreviousCard() {
        const products = this.state.products || [];
        if (!products.length) {
            return;
        }
        if (this.state.selectionIndex <= 0) {
            this._focusSearchSelectAll();
            return;
        }
        this._setSelectionIndex(this.state.selectionIndex - 1);
    }

    _selectNextCard() {
        const products = this.state.products || [];
        if (!products.length) {
            return;
        }
        if (this.state.selectionIndex < 0) {
            this._setSelectionIndex(0);
            return;
        }
        this._setSelectionIndex(Math.min(this.state.selectionIndex + 1, products.length - 1));
    }

    _applyOrder() {
        if (this.state.loading || this.state.applying) {
            return;
        }
        if (!this.selectedItems.length) {
            return;
        }
        this.apply();
    }

    _getSelectedProduct(products) {
        if (this.state.selectionIndex < 0) {
            return null;
        }
        return (products || [])[this.state.selectionIndex] || null;
    }

    _consumeQtyForProduct(product) {
        let qty = 1;
        if (this.state.qtyBufferProductId === product.id && this.state.qtyBuffer) {
            const parsed = parseFloat(this.state.qtyBuffer);
            if (Number.isFinite(parsed) && parsed > 0) {
                qty = parsed;
            }
        }
        this.state.qtyBuffer = "";
        this.state.qtyBufferProductId = null;
        return qty;
    }

    _isQtyInputKey(key) {
        const isDigit = key.length === 1 && key >= "0" && key <= "9";
        return isDigit || key === "." || key === "Backspace" || key === "Escape";
    }

    _handleQtyInputKey(ev, key, products, isSearchFocused) {
        if (isSearchFocused) {
            return false;
        }
        if (this.state.selectionIndex < 0) {
            return false;
        }
        if (!this._isQtyInputKey(key)) {
            return false;
        }
        const product = this._getSelectedProduct(products);
        if (!product) {
            return true;
        }

        ev.preventDefault();

        if (key === "Escape") {
            this.state.qtyBuffer = "";
            this.state.qtyBufferProductId = null;
            return true;
        }
        if (key === "Backspace") {
            if (this.state.qtyBufferProductId === product.id) {
                this.state.qtyBuffer = (this.state.qtyBuffer || "").slice(0, -1);
                if (!this.state.qtyBuffer) {
                    this.state.qtyBufferProductId = null;
                }
            }
            return true;
        }
        if (key === ".") {
            if ((this.state.qtyBufferProductId === product.id ? this.state.qtyBuffer : "").includes(".")) {
                return true;
            }
        }

        if (this.state.qtyBufferProductId !== product.id) {
            this.state.qtyBuffer = "";
            this.state.qtyBufferProductId = product.id;
        }
        this.state.qtyBuffer = `${this.state.qtyBuffer || ""}${key}`;
        return true;
    }

    _onHotkeyF2(ev, { isSearchFocused } = {}) {
        ev.preventDefault();
        if (this.state.loading || this.state.applying) {
            return;
        }
        if (this.state.selectionIndex >= 0 && !isSearchFocused) {
            this._focusSearchSelectAll();
            return;
        }
        this._applyOrder();
    }

    _onHotkeyArrowDown(ev, { isSearchFocused } = {}) {
        if (isSearchFocused) {
            return;
        }
        ev.preventDefault();
        this._selectNextCard();
    }

    _onHotkeyArrowUp(ev, { isSearchFocused } = {}) {
        if (isSearchFocused) {
            return;
        }
        ev.preventDefault();
        this._selectPreviousCard();
    }

    _onHotkeyEnter(ev, { isSearchFocused, products } = {}) {
        if (isSearchFocused) {
            ev.preventDefault();
            this._applyOrder();
            return;
        }
        if (this.state.selectionIndex < 0) {
            return;
        }
        ev.preventDefault();
        const product = this._getSelectedProduct(products);
        if (!product) {
            return;
        }
        const qty = this._consumeQtyForProduct(product);
        this.addProduct(product, qty);

        // Keep focus on the card; go back to search only on ArrowUp/F2.
        const container = this.cardsContainerRef.el;
        const card = container?.querySelector?.(`[data-product-id="${product.id}"]`);
        card?.focus?.();
    }

    onSearchKeydown(ev) {
        const key = ev.key;
        if (this.state.loading || this.state.applying) {
            return;
        }

        // Enter in search behaves like Apply
        if (key === "Enter") {
            ev.preventDefault();
            ev.stopPropagation();
            this._applyOrder();
            return;
        }

        // ArrowDown from search selects first card
        if (key === "ArrowDown") {
            const products = this.state.products || [];
            if (products.length) {
                ev.preventDefault();
                ev.stopPropagation();
                this._selectNextCard();
            }
            return;
        }

        // Prevent global hotkeys from eating digits while typing in the search input.
        // Allow browser/editor shortcuts (ctrl/cmd/alt combos).
        if (ev.ctrlKey || ev.metaKey || ev.altKey) {
            return;
        }
        if ((key && key.length === 1) || key === "Backspace" || key === "Delete") {
            ev.stopPropagation();
        }
    }

    onKeydown(ev) {
        const key = ev.key;

        if (this.state.loading || this.state.applying) {
            return;
        }

        const isSearchFocused = document.activeElement === this.searchInputRef.el;
        const products = this.state.products || [];

        // Search input handles its own keydown for typing/navigation.
        // Exception: F2 is intentionally handled globally.
        if (isSearchFocused && key !== "F2") {
            return;
        }

        if (this._handleQtyInputKey(ev, key, products, isSearchFocused)) {
            return;
        }

        const handler = this.shortcutHandlers.get(key);
        if (!handler) {
            return;
        }
        handler(ev, { isSearchFocused, products });
    }

    _setSelectionIndex(index) {
        const products = this.state.products || [];
        if (!products.length) {
            this.state.selectionIndex = -1;
            this.state.qtyBuffer = "";
            this.state.qtyBufferProductId = null;
            return;
        }
        const next = Math.max(-1, Math.min(index, products.length - 1));
        this.state.selectionIndex = next;
        this.state.qtyBuffer = "";
        this.state.qtyBufferProductId = null;
        if (next >= 0) {
            const product = products[next];
            const container = this.cardsContainerRef.el;
            if (container && product) {
                const card = container.querySelector(`[data-product-id="${product.id}"]`);
                card?.scrollIntoView?.({ block: "nearest" });
                card?.focus?.();
            }
        }
    }

    formatPrice(value) {
        return this._formatCompactNumber(value, 2);
    }

    formatQty(value) {
        return this._formatCompactNumber(value, 2);
    }

    _formatCompactNumber(value, decimals = 2) {
        const numberValue = typeof value === "number" ? value : parseFloat(value ?? 0);
        if (!Number.isFinite(numberValue)) {
            return "0";
        }
        const fixed = numberValue.toFixed(decimals);
        // Remove trailing zeros and a trailing dot: 1.00 -> 1, 1.50 -> 1.5
        return fixed.replace(/(?:\.0+|(\.\d*?)0+)$/, "$1");
    }

    productLabel(p) {
        return p.name || p.product_card_name || `${p.code || ""}`.trim() || `#${p.id}`;
    }

    async openStoresBalance(product) {
        if (!product?.id) {
            return;
        }
        this.dialog.add(FormViewDialog, {
            resModel: "ab_product_balance_wizard",
            title: "Store Balances",
            context: {
                default_product_id: product.id,
            },
            readonly: true,
            size: "lg",
        });
    }

    async loadProducts(query) {
        this.state.loading = true;
        try {
            this.state.products = await this.orm.call("ab_sales_ui_api", "search_products", [], {
                query: query || "",
                limit: 60,
                has_balance: this.state.hasBalanceOnly,
                has_pos_balance: this.state.hasPosBalanceOnly,
                header_id: this.state.headerId,
            });
            this.schedulePosBalanceRefresh(this.state.products, this.state.storeId);
            this.state.selectionIndex = -1;
            this.state.qtyBuffer = "";
            this.state.qtyBufferProductId = null;
        } catch (e) {
            this.notification.add(e?.message || "Failed to load products.", { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    schedulePosBalanceRefresh(results, storeId) {
        if (this._posBalanceTimer) {
            clearTimeout(this._posBalanceTimer);
        }
        const requestId = ++this._posBalanceRequestId;
        this._posBalanceTimer = setTimeout(() => {
            this._posBalanceTimer = null;
            this._refreshPosBalancesForResults(results, storeId, requestId);
        }, 300);
    }

    _refreshPosBalancesForResults(results, storeId, requestId) {
        if (!storeId || !Array.isArray(results) || !results.length) {
            return;
        }
        const productIds = results
            .map((row) => row?.id)
            .filter((id) => Number.isFinite(id) || parseInt(id || 0, 10));
        if (!productIds.length) {
            return;
        }
        this.orm
            .call("ab_sales_pos_api", "pos_refresh_pos_balances", [], {
                store_id: storeId,
                product_ids: productIds,
            })
            .then((balances) => {
                if (requestId !== this._posBalanceRequestId) {
                    return;
                }
                if (!balances || typeof balances !== "object") {
                    return;
                }
                const list = this.state.products || [];
                for (const product of list) {
                    const balance = balances[product.id];
                    if (balance === undefined) {
                        continue;
                    }
                    const val = parseFloat(balance || 0) || 0;
                    product.pos_balance = val;
                }
            })
            .catch(() => {});
    }

    onSearch(ev) {
        this.state.query = ev.target.value || "";
        if (this._productSearchTimer) {
            clearTimeout(this._productSearchTimer);
        }
        this._productSearchTimer = setTimeout(async () => {
            await this.loadProducts(this.state.query);
        }, 150);
    }

    async onHasBalanceChange(ev) {
        this.state.hasBalanceOnly = !!ev.target.checked;
        await this.loadProducts(this.state.query);
    }

    async onHasPosBalanceChange(ev) {
        this.state.hasPosBalanceOnly = !!ev.target.checked;
        this._saveHasPosBalanceOnly(this.state.hasPosBalanceOnly);
        await this.loadProducts(this.state.query);
    }

    addProduct(product, qty = 1) {
        const key = product.id;
        const existing = this.state.selected.get(key);
        if (existing) {
            existing.qty += qty;
            return;
        }
        this.state.selected.set(key, { product, qty });
    }

    inc(item) {
        item.qty += 1;
    }

    dec(item) {
        item.qty -= 1;
        if (item.qty <= 0) {
            this.state.selected.delete(item.product.id);
        }
    }

    get selectedItems() {
        return Array.from(this.state.selected.values());
    }

    get selectedCount() {
        let count = 0;
        for (const item of this.state.selected.values()) {
            count += item.qty;
        }
        return count;
    }

    async apply() {
        if (!this.state.headerId) {
            this.notification.add("No active sales header.", { type: "danger" });
            return;
        }
        const items = this.selectedItems.map((i) => ({ product_id: i.product.id, qty: i.qty }));
        if (!items.length) {
            this.notification.add("Select at least one product.", { type: "warning" });
            return;
        }

        this.state.applying = true;
        try {
            const res = await this.orm.call("ab_sales_ui_api", "apply_products", [], {
                header_id: this.state.headerId,
                items,
            });
            this.notification.add(`Added lines: ${res.created}, updated: ${res.updated}`, { type: "success" });
            this.state.selected.clear();
            if (this.env.dialogData?.close) {
                await this.env.dialogData.close({ ab_sales_refresh: true });
            } else {
                await this.action.doAction({ type: "ir.actions.act_window_close" });
            }
        } catch (e) {
            this.notification.add(e?.message || "Failed to apply products.", { type: "danger" });
        } finally {
            this.state.applying = false;
        }
    }

    async back() {
        await this.action.doAction({ type: "ir.actions.act_window_close" });
    }
}

registry.category("actions").add("ab_sales.add_products", AbSalesAddProductsAction);
