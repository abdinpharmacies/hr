/** @odoo-module **/

import {registry} from "@web/core/registry";
import {Component, onMounted, onWillStart, onWillUnmount, useExternalListener, useState} from "@odoo/owl";
import {Dialog} from "@web/core/dialog/dialog";
import {useService} from "@web/core/utils/hooks";
import {FormViewDialog} from "@web/views/view_dialogs/form_view_dialog";
import {Many2One} from "@web/views/fields/many2one/many2one";
import {AbSalesBillWizardPrintDialog} from "@ab_sales/bill_wizard/print_dialog";
import {openBillWizardPrintWindow} from "@ab_sales/bill_wizard/print_preview";

const DEFAULT_POLL_MIN_SECONDS = 5;
const DEFAULT_POLL_MAX_SECONDS = 20;
const MAX_LIST_SIZE = 500;
const SORT_STORAGE_KEY = "ab_sales_cashier_sort_mode_v1";
const DEFAULT_SORT_MODE = "oldest";
const ALLOWED_SORT_MODES = new Set(["all", "oldest", "highest"]);

const toNumber = (value, fallback = 0) => {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : fallback;
};

const normalizePrinterRecords = (records) => {
    const out = [];
    for (const raw of Array.isArray(records) ? records : []) {
        if (!raw || typeof raw !== "object") {
            continue;
        }
        const id = Number.parseInt(raw.id || 0, 10) || 0;
        const label = String(raw.label || raw.name || "").trim();
        if (!id || !label) {
            continue;
        }
        out.push({
            id: id,
            name: String(raw.name || "").trim(),
            label: label,
            protocol: String(raw.protocol || "").trim(),
            paper_size: String(raw.paper_size || "").trim() === "pos_80mm" ? "pos_80mm" : "a4",
            ip: String(raw.ip || "").trim(),
            port: Number.parseInt(raw.port || 9100, 10) || 9100,
            printer_name: String(raw.printer_name || "").trim(),
            username: String(raw.username || "").trim(),
            is_default: !!raw.is_default,
        });
    }
    return out;
};

const findPrinterById = (records, printerId) => {
    const parsed = Number.parseInt(printerId || 0, 10) || 0;
    if (!parsed) {
        return null;
    }
    return (Array.isArray(records) ? records : []).find((rec) => rec.id === parsed) || null;
};

const deepClone = (value) => JSON.parse(JSON.stringify(value || {}));

const randomInRange = (min, max) => {
    const safeMin = Math.max(1, Math.floor(toNumber(min, DEFAULT_POLL_MIN_SECONDS)));
    const safeMax = Math.max(safeMin, Math.floor(toNumber(max, DEFAULT_POLL_MAX_SECONDS)));
    return safeMin + Math.floor(Math.random() * (safeMax - safeMin + 1));
};

const isTypingTarget = (target) => {
    if (!target) {
        return false;
    }
    if (target.isContentEditable) {
        return true;
    }
    const tag = (target.tagName || "").toLowerCase();
    return tag === "input" || tag === "textarea" || tag === "select";
};

const requestId = (prefix = "req") => `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;

class AbSalesCashierStoreDialog extends Component {
    static template = "ab_sales.CashierStoreDialog";
    static components = {Dialog, Many2One};
    static props = {
        domain: {type: Array, optional: true},
        defaultStoreId: {optional: true},
        onSelect: Function,
        close: Function,
    };

    setup() {
        const defaultId = toNumber(this.props.defaultStoreId, 0);
        this.state = useState({
            store: defaultId ? {id: defaultId, display_name: ""} : false,
        });
        this.storeDomain = this.storeDomain.bind(this);
        this.onStoreUpdate = this.onStoreUpdate.bind(this);
        this.confirm = this.confirm.bind(this);
        this.cancel = this.cancel.bind(this);
    }

    storeDomain() {
        return this.props.domain || [["allow_sale", "=", true]];
    }

    onStoreUpdate(value) {
        if (value && value.id) {
            this.state.store = value;
        } else {
            this.state.store = false;
        }
    }

    confirm() {
        const storeId = toNumber(this.state.store?.id, 0);
        if (storeId && this.props.onSelect) {
            this.props.onSelect(storeId);
        }
        if (this.props.close) {
            this.props.close();
        }
    }

    cancel() {
        if (this.props.close) {
            this.props.close();
        }
    }
}

class AbSalesCashierWalletDialog extends Component {
    static template = "ab_sales.CashierWalletDialog";
    static components = {Dialog};
    static props = {
        wallets: Array,
        defaultWalletId: {optional: true},
        onSelect: Function,
        close: Function,
    };

    setup() {
        const firstId = toNumber((this.props.wallets || [])[0]?.id, 0);
        this._done = false;
        this.state = useState({
            walletId: toNumber(this.props.defaultWalletId, firstId) || firstId || 0,
        });
        this.onWalletChange = this.onWalletChange.bind(this);
        this.walletLabel = this.walletLabel.bind(this);
        this.saveWallet = this.saveWallet.bind(this);
        this.cancel = this.cancel.bind(this);
        onWillUnmount(() => {
            if (!this._done && this.props.onSelect) {
                this.props.onSelect(false);
            }
        });
    }

    onWalletChange(ev) {
        this.state.walletId = toNumber(ev.target.value, 0);
    }

    walletLabel(wallet) {
        const name = String(wallet?.name || `#${wallet?.id || ""}`).trim();
        return name;
    }

    saveWallet() {
        let walletId = toNumber(this.state.walletId, 0);
        if (!walletId) {
            walletId = toNumber(this.props.defaultWalletId, 0) || toNumber((this.props.wallets || [])[0]?.id, 0);
        }
        if (!walletId) {
            return;
        }
        this._done = true;
        if (this.props.onSelect) {
            this.props.onSelect(walletId);
        }
        if (this.props.close) {
            this.props.close();
        }
    }

    cancel() {
        this._done = true;
        if (this.props.onSelect) {
            this.props.onSelect(false);
        }
        if (this.props.close) {
            this.props.close();
        }
    }
}

class AbSalesCashierAction extends Component {
    static template = "ab_sales.CashierAction";

    setup() {
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        this.notification = useService("notification");

        this.pendingInvoices = new Map();
        this.savedInvoices = new Map();
        this.newInvoiceIds = new Set();
        this._pollTimer = null;
        this._clockTimer = null;
        this._pollSeq = 0;
        this._pollAppliedSeq = 0;
        this._snapshotSeq = 0;

        this.state = useState({
            branchName: "",
            deviceName: "",
            now: new Date(),
            connected: true,
            loadingInitial: true,
            refreshing: false,
            pollMinSeconds: DEFAULT_POLL_MIN_SECONDS,
            pollMaxSeconds: DEFAULT_POLL_MAX_SECONDS,
            query: "",
            sortMode: this._restoreSortMode(),
            stores: [],
            storeById: {},
            allowedStoreIds: [],
            defaultStoreId: null,
            selectedStoreId: null,
            selectedStoreName: "",
            pendingCount: 0,
            newArrivalsCount: 0,
            selectedInvoiceKey: null,
            selectedInvoiceSnapshot: null,
            selectedStale: false,
            loadingSnapshot: false,
            isSaving: false,
            saveError: "",
            highlightedInvoiceKey: null,
            lastSavedSnapshot: null,
            listVersion: 0,
            printerId: 0,
            printerName: "",
            receiptHeader: "",
            receiptFooter: "",
            availablePrinters: [],
            defaultPrintFormat: "a4",
            lastSyncLabel: "",
        });

        this.onSearchInput = this.onSearchInput.bind(this);
        this.onSortChange = this.onSortChange.bind(this);
        this.onInvoiceCardClick = this.onInvoiceCardClick.bind(this);
        this.onKeyDown = this.onKeyDown.bind(this);
        this.storeDomain = this.storeDomain.bind(this);
        this.openStoreDialog = this.openStoreDialog.bind(this);
        this.applyStoreSelection = this.applyStoreSelection.bind(this);
        this.chooseWalletForSave = this.chooseWalletForSave.bind(this);
        this.openCloseCashierDialog = this.openCloseCashierDialog.bind(this);

        useExternalListener(window, "keydown", this.onKeyDown, {capture: true});

        onWillStart(async () => {
            await this.loadBootstrap();
            await this.loadStores();
            await this._applyInitialStore();
            if (this.state.selectedStoreId) {
                await this.refreshPending({manual: false});
            } else {
                this.state.loadingInitial = false;
            }
        });

        onMounted(() => {
            this._clockTimer = setInterval(() => {
                this.state.now = new Date();
            }, 1000);
        });

        onWillUnmount(() => {
            if (this._pollTimer) {
                clearTimeout(this._pollTimer);
                this._pollTimer = null;
            }
            if (this._clockTimer) {
                clearInterval(this._clockTimer);
                this._clockTimer = null;
            }
        });
    }

    get visibleInvoices() {
        this.state.listVersion;
        const query = (this.state.query || "").trim().toLowerCase();
        let rows = Array.from(this.pendingInvoices.values());
        if (query) {
            rows = rows.filter((invoice) => invoice.searchKey.includes(query));
        }
        if (this.state.sortMode === "oldest") {
            rows.sort((a, b) => a.createDateMs - b.createDateMs || a.id - b.id);
        } else if (this.state.sortMode === "highest") {
            rows.sort((a, b) => b.totalAmount - a.totalAmount || b.id - a.id);
        } else {
            rows.sort((a, b) => b.createDateMs - a.createDateMs || b.id - a.id);
        }
        return rows;
    }

    get selectedInvoice() {
        return this.state.selectedInvoiceSnapshot;
    }

    get connectionClassName() {
        return this.state.connected ? "is-connected" : "is-disconnected";
    }

    get connectionLabel() {
        return this.state.connected ? "Connected" : "Disconnected";
    }

    get nowLabel() {
        return this.formatDateTime(this.state.now);
    }

    get lastSavedInvoice() {
        return this.state.lastSavedSnapshot;
    }

    onSearchInput(ev) {
        this.state.query = ev.target.value || "";
        this.ensureHighlightedInvoice();
    }

    onSortChange(ev) {
        const nextMode = ev.target.value || DEFAULT_SORT_MODE;
        this.state.sortMode = ALLOWED_SORT_MODES.has(nextMode) ? nextMode : DEFAULT_SORT_MODE;
        this._persistSortMode(this.state.sortMode);
        this.ensureHighlightedInvoice();
    }

    _restoreSortMode() {
        try {
            const saved = window.localStorage.getItem(SORT_STORAGE_KEY) || "";
            if (ALLOWED_SORT_MODES.has(saved)) {
                return saved;
            }
        } catch {
            // Ignore storage errors and use default.
        }
        return DEFAULT_SORT_MODE;
    }

    _persistSortMode(mode) {
        try {
            window.localStorage.setItem(SORT_STORAGE_KEY, mode || DEFAULT_SORT_MODE);
        } catch {
            // Ignore storage errors.
        }
    }

    onInvoiceCardClick(ev) {
        const invoiceKey = String(ev.currentTarget?.dataset?.invoiceKey || "").trim();
        if (!invoiceKey) {
            return;
        }
        this.selectInvoice(invoiceKey);
    }

    async loadBootstrap() {
        try {
            const payload = await this.orm.call("ab_sales_cashier_api", "get_cashier_bootstrap", [], {});
            this.state.branchName = payload?.branch_name || "";
            this.state.deviceName = payload?.device_name || "";
            this.state.pollMinSeconds = toNumber(payload?.poll_min_seconds, DEFAULT_POLL_MIN_SECONDS);
            this.state.pollMaxSeconds = toNumber(payload?.poll_max_seconds, DEFAULT_POLL_MAX_SECONDS);
            this.state.printerName = payload?.printer_name || "";
            this.state.receiptHeader = payload?.receipt_header || "";
            this.state.receiptFooter = payload?.receipt_footer || "";
            this.state.allowedStoreIds = Array.isArray(payload?.allowed_store_ids) ? payload.allowed_store_ids : [];
            this.state.defaultStoreId = toNumber(payload?.default_store_id, 0) || null;
        } catch (err) {
            this.notification.add(this._rpcError(err, "Error happened."), {
                type: "warning",
            });
        }
    }

    async loadStores() {
        try {
            const domain = this.storeDomain();
            const stores = await this.orm.searchRead("ab_store", domain, ["name", "code", "ip1"]);
            const byId = {};
            for (const store of stores || []) {
                byId[store.id] = store;
            }
            this.state.stores = stores || [];
            this.state.storeById = byId;
        } catch (err) {
            this.state.stores = [];
            this.state.storeById = {};
            this.notification.add(this._rpcError(err, "Failed to load stores."), {type: "warning"});
        }
    }

    storeDomain() {
        const domain = [["allow_sale", "=", true]];
        if (Array.isArray(this.state.allowedStoreIds) && this.state.allowedStoreIds.length) {
            domain.push(["id", "in", this.state.allowedStoreIds]);
        }
        return domain;
    }

    _clearInvoicesState() {
        this.pendingInvoices = new Map();
        this.newInvoiceIds = new Set();
        this.clearSelection();
        this.state.pendingCount = 0;
        this.state.newArrivalsCount = 0;
        this.state.listVersion += 1;
    }

    async _applyInitialStore() {
        const stores = this.state.stores || [];
        if (!stores.length) {
            this.notification.add("No sales stores are available for this cashier.", {type: "warning"});
            return;
        }

        const defaultStoreId = toNumber(this.state.defaultStoreId, 0);
        if (defaultStoreId && stores.some((store) => store.id === defaultStoreId)) {
            await this.applyStoreSelection(defaultStoreId, {refresh: false});
            return;
        }
        if (stores.length === 1) {
            await this.applyStoreSelection(stores[0].id, {refresh: false});
            return;
        }
        this.openStoreDialog();
    }

    openStoreDialog() {
        if (!this.state.stores.length) {
            this.notification.add("No stores available.", {type: "warning"});
            return;
        }
        this.dialog.add(AbSalesCashierStoreDialog, {
            domain: this.storeDomain(),
            defaultStoreId: this.state.selectedStoreId || this.state.defaultStoreId || false,
            onSelect: (storeId) => this.applyStoreSelection(storeId),
        });
    }

    async applyStoreSelection(storeId, {refresh = true} = {}) {
        const parsedStoreId = toNumber(storeId, 0);
        if (!parsedStoreId) {
            return;
        }
        const store = this.state.storeById?.[parsedStoreId];
        if (!store) {
            this.notification.add("Invalid store selection.", {type: "warning"});
            return;
        }
        this.state.selectedStoreId = parsedStoreId;
        this.state.selectedStoreName = store.name || store.code || `#${parsedStoreId}`;
        this._clearInvoicesState();
        if (refresh) {
            await this.refreshPending({manual: true});
        }
    }

    async chooseWalletForSave() {
        const selectedStoreId = toNumber(this.state.selectedStoreId, 0);
        if (!selectedStoreId) {
            this.notification.add("Select a store first.", {type: "warning"});
            return null;
        }
        try {
            const payload = await this.orm.call("ab_sales_cashier_api", "get_store_wallets", [], {
                store_id: selectedStoreId,
            });
            const wallets = Array.isArray(payload?.wallets)
                ? payload.wallets.filter((wallet) => toNumber(wallet?.id, 0))
                : [];
            if (!wallets.length) {
                this.notification.add("No wallets found for this store.", {type: "warning"});
                return null;
            }
            return await new Promise((resolve) => {
                let settled = false;
                const finish = (walletId) => {
                    if (settled) {
                        return;
                    }
                    settled = true;
                    resolve(toNumber(walletId, 0) || null);
                };
                this.dialog.add(AbSalesCashierWalletDialog, {
                    wallets,
                    defaultWalletId: toNumber(payload?.default_wallet_id, toNumber(wallets[0]?.id, 0)),
                    onSelect: (walletId) => finish(walletId),
                });
            });
        } catch (err) {
            this.notification.add(this._rpcError(err, "Failed to load wallets."), {
                type: "danger",
            });
            return null;
        }
    }

    openCloseCashierDialog() {
        const selectedStoreId = toNumber(this.state.selectedStoreId || this.state.defaultStoreId, 0);
        if (!selectedStoreId) {
            this.notification.add("Select a store first.", {type: "warning"});
            return;
        }
        this.dialog.add(FormViewDialog, {
            resModel: "ab_sales_cashier_close_wizard",
            title: "Close Cashier",
            context: {
                default_store_id: selectedStoreId,
            },
            size: "lg",
        });
    }

    async refreshPending({manual = false} = {}) {
        const currentSeq = ++this._pollSeq;
        const selectedStoreId = toNumber(this.state.selectedStoreId, 0);
        if (!selectedStoreId) {
            this.state.loadingInitial = false;
            this.state.connected = true;
            this._clearInvoicesState();
            return;
        }
        if (manual) {
            this.state.refreshing = true;
        }
        try {
            const payload = await this.orm.call("ab_sales_cashier_api", "get_pending_invoices", [], {
                limit: MAX_LIST_SIZE,
                store_id: selectedStoreId,
            });
            if (currentSeq < this._pollAppliedSeq) {
                return;
            }
            this._pollAppliedSeq = currentSeq;
            this.state.connected = true;
            this.state.loadingInitial = false;
            if (payload?.store_name) {
                this.state.selectedStoreName = payload.store_name;
            }
            this.applyIncomingInvoices(payload?.invoices || []);
            this.state.lastSyncLabel = this.formatDateTime(payload?.server_time || new Date());
        } catch (err) {
            if (currentSeq < this._pollAppliedSeq) {
                return;
            }
            const wasConnected = this.state.connected;
            this.state.connected = false;
            this.state.loadingInitial = false;
            if (manual || wasConnected) {
                this.notification.add(this._rpcError(err, "Failed to refresh pending invoices."), {
                    type: "danger",
                });
            }
        } finally {
            if (currentSeq === this._pollSeq) {
                this.state.refreshing = false;
                this.scheduleNextPoll();
            }
        }
    }

    scheduleNextPoll() {
        if (this._pollTimer) {
            clearTimeout(this._pollTimer);
        }
        const delaySeconds = randomInRange(this.state.pollMinSeconds, this.state.pollMaxSeconds);
        this._pollTimer = setTimeout(() => {
            this.refreshPending({manual: false});
        }, delaySeconds * 1000);
    }

    applyIncomingInvoices(rawInvoices) {
        const selectedKey = this.state.selectedInvoiceKey;
        const nextMap = new Map();
        for (const raw of rawInvoices || []) {
            const normalized = this.normalizeInvoice(raw);
            if (normalized.key) {
                nextMap.set(normalized.key, normalized);
            }
        }

        const nextNewSet = new Set();
        for (const invoiceKey of this.newInvoiceIds) {
            if (nextMap.has(invoiceKey) && invoiceKey !== selectedKey) {
                nextNewSet.add(invoiceKey);
            }
        }
        for (const [invoiceKey] of nextMap) {
            if (!this.pendingInvoices.has(invoiceKey) && invoiceKey !== selectedKey) {
                nextNewSet.add(invoiceKey);
            }
        }

        this.pendingInvoices = nextMap;
        this.newInvoiceIds = nextNewSet;
        this.state.pendingCount = this.pendingInvoices.size;
        this.state.newArrivalsCount = this.newInvoiceIds.size;
        if (selectedKey) {
            this.state.selectedStale = !this.pendingInvoices.has(selectedKey);
        }
        this.ensureHighlightedInvoice();
        this.state.listVersion += 1;
    }

    normalizeInvoice(raw) {
        const id = toNumber(raw?.id, 0);
        const documentType = String(raw?.document_type || "sale").toLowerCase() === "return" ? "return" : "sale";
        const key = id ? `${documentType}:${id}` : "";
        const invoiceNumber = raw?.invoice_number || id;
        const customerName = (raw?.customer_name || "").trim() || "\u0628\u062f\u0648\u0646 \u0639\u0645\u064a\u0644";
        const customerPhone = (raw?.customer_phone || "").trim();
        const totalAmount = toNumber(raw?.total_amount, 0);
        const itemCount = toNumber(raw?.item_count, 0);
        const createDate = raw?.create_date || raw?.write_date || "";
        const storeName = raw?.store_name || "";
        const paymentMethod = raw?.payment_method || "";
        const note = raw?.note || "";
        const searchKey = `${invoiceNumber} ${customerName} ${customerPhone} ${note}`.toLowerCase();
        const createDateMs = this._toDateMs(createDate);
        return {
            id,
            key,
            documentType,
            invoiceNumber,
            customerName,
            customerPhone,
            totalAmount,
            itemCount,
            createDate,
            createDateMs,
            createDateLabel: this.formatDateTime(createDate),
            storeName,
            paymentMethod,
            note,
            status: raw?.status || "pending",
            searchKey,
        };
    }

    ensureHighlightedInvoice() {
        const rows = this.visibleInvoices;
        if (!rows.length) {
            this.state.highlightedInvoiceKey = null;
            return;
        }
        const selectedKey = this.state.selectedInvoiceKey;
        if (selectedKey && rows.some((row) => row.key === selectedKey)) {
            this.state.highlightedInvoiceKey = selectedKey;
            return;
        }
        const currentHighlight = this.state.highlightedInvoiceKey;
        if (currentHighlight && rows.some((row) => row.key === currentHighlight)) {
            return;
        }
        this.state.highlightedInvoiceKey = rows[0].key;
    }

    async selectInvoice(invoiceKey, {forceReload = false} = {}) {
        const key = String(invoiceKey || "").trim();
        if (!key) {
            return;
        }
        const selectedStoreId = toNumber(this.state.selectedStoreId, 0);
        if (!selectedStoreId) {
            this.notification.add("Select a store first.", {type: "warning"});
            return;
        }
        let selectedRow = this.pendingInvoices.get(key);
        if (!selectedRow && this.state.selectedInvoiceSnapshot?.key === key) {
            selectedRow = this.state.selectedInvoiceSnapshot;
        }
        if (!selectedRow) {
            return;
        }
        if (
            !forceReload
            && this.state.selectedInvoiceKey === key
            && this.state.selectedInvoiceSnapshot
            && !this.state.selectedStale
        ) {
            return;
        }
        const currentSeq = ++this._snapshotSeq;
        this.state.loadingSnapshot = true;
        this.state.saveError = "";
        try {
            const snapshot = await this.orm.call("ab_sales_cashier_api", "get_invoice_snapshot", [selectedRow.id], {
                store_id: selectedStoreId,
                document_type: selectedRow.documentType || "sale",
            });
            if (currentSeq !== this._snapshotSeq) {
                return;
            }
            const normalized = this.normalizeSnapshot(snapshot);
            this.state.selectedInvoiceKey = normalized.key;
            this.state.selectedInvoiceSnapshot = normalized;
            this.state.selectedStale = false;
            this.state.highlightedInvoiceKey = normalized.key;
            if (this.newInvoiceIds.has(normalized.key)) {
                this.newInvoiceIds.delete(normalized.key);
                this.state.newArrivalsCount = this.newInvoiceIds.size;
            }
        } catch (err) {
            if (currentSeq !== this._snapshotSeq) {
                return;
            }
            this.notification.add(this._rpcError(err, "Failed to load invoice details."), {
                type: "danger",
            });
        } finally {
            if (currentSeq === this._snapshotSeq) {
                this.state.loadingSnapshot = false;
            }
        }
    }

    normalizeSnapshot(snapshot) {
        const summary = this.normalizeInvoice(snapshot || {});
        const lines = (snapshot?.lines || []).map((line) => ({
            id: toNumber(line?.id, 0),
            productName: line?.product_name || "",
            productCode: line?.product_code || "",
            qty: toNumber(line?.qty, 0),
            qtyLabel: line?.qty_str || this.formatQty(line?.qty),
            uomName: line?.uom_name || "",
            sellPrice: toNumber(line?.sell_price, 0),
            netAmount: toNumber(line?.net_amount, 0),
        }));
        return {
            ...summary,
            lineCount: toNumber(snapshot?.line_count, lines.length),
            totalPrice: toNumber(snapshot?.total_price, summary.totalAmount),
            totalNetAmount: toNumber(snapshot?.total_net_amount, summary.totalAmount),
            promoDiscountAmount: toNumber(snapshot?.promo_discount_amount, 0),
            appliedProgramName: String(snapshot?.applied_program_name || "").trim(),
            selectedProgramName: String(snapshot?.selected_program_name || "").trim(),
            lines,
            capturedAt: new Date().toISOString(),
        };
    }

    async refreshSelectedSnapshot() {
        if (!this.state.selectedInvoiceKey) {
            return;
        }
        await this.selectInvoice(this.state.selectedInvoiceKey, {forceReload: true});
    }

    clearSelection() {
        this.state.selectedInvoiceKey = null;
        this.state.selectedInvoiceSnapshot = null;
        this.state.selectedStale = false;
        this.state.loadingSnapshot = false;
        this.state.saveError = "";
        this.ensureHighlightedInvoice();
    }

    async saveSelectedInvoice() {
        if (this.state.isSaving) {
            return;
        }
        const selectedStoreId = toNumber(this.state.selectedStoreId, 0);
        if (!selectedStoreId) {
            this.notification.add("Select a store first.", {type: "warning"});
            return;
        }
        const snapshot = this.state.selectedInvoiceSnapshot;
        if (!snapshot?.id) {
            return;
        }
        let walletId = null;
        if (snapshot.documentType === "sale") {
            walletId = await this.chooseWalletForSave();
            if (!walletId) {
                return;
            }
        }
        this.state.isSaving = true;
        this.state.saveError = "";
        const callRequestId = requestId(`cashier_save_${snapshot.documentType || "sale"}_${snapshot.id}`);
        try {
            const result = await this.orm.call("ab_sales_cashier_api", "save_pending_invoice", [snapshot.id], {
                request_id: callRequestId,
                store_id: selectedStoreId,
                wallet_id: walletId || false,
                document_type: snapshot.documentType || "sale",
            });
            const status = result?.status || "";
            if (status === "saved" || status === "already_saved") {
                const savedSnapshot = {
                    ...deepClone(snapshot),
                    status: "saved",
                    savedAt: result?.saved_at || new Date().toISOString(),
                };
                this.savedInvoices.set(savedSnapshot.key, savedSnapshot);
                this.state.lastSavedSnapshot = savedSnapshot;
                this.pendingInvoices.delete(savedSnapshot.key);
                this.newInvoiceIds.delete(savedSnapshot.key);
                this.state.pendingCount = this.pendingInvoices.size;
                this.state.newArrivalsCount = this.newInvoiceIds.size;
                this.clearSelection();
                this.state.listVersion += 1;
                this.notification.add("Invoice saved successfully.", {type: "success"});
                return;
            }

            if (status === "invalid_status") {
                const current = result?.current_status || "";
                this.state.saveError = `Cannot save invoice: current status is ${current || "-"}.`;
                this.notification.add(this.state.saveError, {type: "warning"});
                return;
            }

            this.state.saveError = "Failed to save invoice due to an unexpected status.";
            this.notification.add(this.state.saveError, {type: "danger"});
        } catch (err) {
            this.state.saveError = this._rpcError(err, "Failed to save invoice.");
            this.notification.add(this.state.saveError, {type: "danger"});
        } finally {
            this.state.isSaving = false;
        }
    }

    acknowledgeNewInvoices() {
        this.newInvoiceIds.clear();
        this.state.newArrivalsCount = 0;
        this.state.listVersion += 1;
    }

    async refreshListNow() {
        await this.refreshPending({manual: true});
    }

    invoiceCardClass(invoice) {
        const classes = ["ab_cashier_invoice_card"];
        if (invoice.key === this.state.selectedInvoiceKey) {
            classes.push("is-selected");
        }
        if (invoice.key === this.state.highlightedInvoiceKey) {
            classes.push("is-highlighted");
        }
        return classes.join(" ");
    }

    isInvoiceNew(invoiceKey) {
        return this.newInvoiceIds.has(invoiceKey);
    }

    formatMoney(value) {
        return toNumber(value, 0).toLocaleString("en-US", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        });
    }

    formatQty(value) {
        return toNumber(value, 0).toLocaleString("en-US", {
            minimumFractionDigits: 0,
            maximumFractionDigits: 3,
        });
    }

    formatDateTime(value) {
        if (!value) {
            return "-";
        }
        try {
            const dateObj = value instanceof Date ? value : new Date(String(value).replace(" ", "T"));
            if (!Number.isFinite(dateObj.getTime())) {
                return String(value);
            }
            return `${dateObj.toLocaleDateString()} ${dateObj.toLocaleTimeString()}`;
        } catch {
            return String(value);
        }
    }

    _toDateMs(value) {
        if (!value) {
            return 0;
        }
        const dateObj = new Date(String(value).replace(" ", "T"));
        return Number.isFinite(dateObj.getTime()) ? dateObj.getTime() : 0;
    }

    _rpcError(err, fallback) {
        const data = err?.data || err?.response?.data || {};
        const args = data?.arguments;
        return data?.message || (Array.isArray(args) && args[0]) || err?.message || fallback;
    }

    navigateList(step) {
        const rows = this.visibleInvoices;
        if (!rows.length) {
            return;
        }
        const currentKey = this.state.highlightedInvoiceKey || this.state.selectedInvoiceKey;
        let index = rows.findIndex((row) => row.key === currentKey);
        if (index < 0) {
            index = 0;
        } else {
            index = (index + step + rows.length) % rows.length;
        }
        this.state.highlightedInvoiceKey = rows[index].key;
    }

    async openHighlightedInvoice() {
        const rows = this.visibleInvoices;
        if (!rows.length) {
            return;
        }
        const currentKey = this.state.highlightedInvoiceKey || rows[0].key;
        await this.selectInvoice(currentKey);
    }

    onKeyDown(ev) {
        const key = ev.key;
        const keyLower = (key || "").toLowerCase();
        const isCtrlPrint = ev.ctrlKey && keyLower === "p";

        if (isTypingTarget(ev.target) && !["F9", "F10", "Escape", "ArrowDown", "ArrowUp", "Enter"].includes(key) && !isCtrlPrint) {
            return;
        }

        if (key === "ArrowDown") {
            ev.preventDefault();
            this.navigateList(1);
            return;
        }
        if (key === "ArrowUp") {
            ev.preventDefault();
            this.navigateList(-1);
            return;
        }
        if (key === "Enter") {
            ev.preventDefault();
            this.openHighlightedInvoice();
            return;
        }
        if (key === "F10") {
            ev.preventDefault();
            this.saveSelectedInvoice();
            return;
        }
        if (key === "F9" || isCtrlPrint) {
            ev.preventDefault();
            this.printReceipt();
            return;
        }
        if (key === "Escape") {
            ev.preventDefault();
            this.clearSelection();
        }
    }

    _buildSnapshotPrintPayload(snapshot) {
        const snapshotId = toNumber(snapshot?.id, 0);
        const isReturn = snapshot?.documentType === "return";
        return {
            document_type: isReturn ? "return" : "sale",
            header: {
                id: snapshotId || "",
                invoice_number: snapshot?.invoiceNumber || "",
                eplus_serial: snapshot?.invoiceNumber || snapshotId || "",
                origin_header_id: isReturn ? (toNumber(snapshot?.invoiceNumber, 0) || false) : false,
                create_date: snapshot?.createDate || snapshot?.capturedAt || new Date().toISOString(),
                store_name: snapshot?.storeName || "",
                customer_name: snapshot?.customerName || "",
                customer_phone: snapshot?.customerPhone || "",
                bill_customer_name: snapshot?.customerName || "",
                bill_customer_phone: snapshot?.customerPhone || "",
                employee_name: this.state.deviceName || "",
                total_price: toNumber(snapshot?.totalPrice, snapshot?.totalAmount || 0),
                total_net_amount: toNumber(snapshot?.totalNetAmount, snapshot?.totalAmount || 0),
                promo_discount_amount: toNumber(snapshot?.promoDiscountAmount, 0),
                applied_program_name: snapshot?.appliedProgramName || "",
                selected_program_name: snapshot?.selectedProgramName || "",
            },
            lines: (snapshot?.lines || []).map((line) => ({
                product_name: line?.productName || "",
                product_code: line?.productCode || "",
                qty: toNumber(line?.qty, 0),
                qty_str: line?.qtyLabel || String(toNumber(line?.qty, 0)),
                sell_price: toNumber(line?.sellPrice, 0),
                net_amount: toNumber(line?.netAmount, 0),
            })),
        };
    }

    async _loadPrintOptions({silent = false} = {}) {
        try {
            const result = await this.orm.call("ab_sales_ui_api", "bill_wizard_get_print_options", [], {});
            this.state.printerId = Number.parseInt(result?.printer_id || 0, 10) || 0;
            this.state.receiptHeader = result?.receipt_header || "Sales Receipt";
            this.state.receiptFooter = result?.receipt_footer || "Thank you.";
            const printers = normalizePrinterRecords(result?.available_printer_records || []);
            const selected = findPrinterById(printers, this.state.printerId);
            this.state.printerName = selected?.label || (result?.printer_name || "").trim();
            this.state.defaultPrintFormat = selected?.paper_size || (result?.print_format === "pos_80mm" ? "pos_80mm" : "a4");
            this.state.availablePrinters = printers;
            return printers;
        } catch (err) {
            if (!silent) {
                this.notification.add(this._rpcError(err, "Failed to load printer options."), {type: "warning"});
            }
            return this.state.availablePrinters || [];
        }
    }

    async _discoverServerSharedPrinters(startIp, endIp) {
        const startText = String(startIp || "").trim();
        const endText = String(endIp || "").trim();
        if (!startText || !endText) {
            this.notification.add("Start IP and End IP are required.", {type: "warning"});
            return this.state.availablePrinters || [];
        }
        try {
            await this.orm.call("ab_sales_ui_api", "bill_wizard_discover_shared_printers", [], {
                start_ip: startText,
                end_ip: endText,
            });
            const printers = await this._loadPrintOptions({silent: true});
            const installedCount = printers.length;
            this.notification.add(
                `Discovery completed. Available printers: ${installedCount}.`,
                {type: "success"}
            );
            return printers;
        } catch (err) {
            this.notification.add(this._rpcError(err, "Printer discovery failed."), {type: "danger"});
            return this.state.availablePrinters || [];
        }
    }

    async _saveBillWizardPrintPreferences(payload = {}) {
        const selectedId = Number.parseInt(
            payload?.printerId !== undefined ? payload.printerId : (this.state.printerId || 0),
            10
        ) || 0;
        const selectedRecord = findPrinterById(this.state.availablePrinters, selectedId) || payload?.printer || null;
        const selectedPrinter = selectedRecord?.label || String(
            payload?.printerName !== undefined ? payload.printerName : (this.state.printerName || "")
        ).trim();
        const selectedFormat = selectedRecord?.paper_size || (payload?.printFormat === "pos_80mm" ? "pos_80mm" : "a4");
        const result = await this.orm.call("ab_sales_ui_api", "bill_wizard_set_print_preferences", [], {
            printer_id: selectedId,
            printer_name: selectedPrinter,
            print_format: selectedFormat,
        });
        this.state.printerId = Number.parseInt(result?.printer_id || selectedId || 0, 10) || 0;
        const canonical = findPrinterById(this.state.availablePrinters, this.state.printerId);
        this.state.printerName = canonical?.label || (result?.printer_name || selectedPrinter || "").trim();
        this.state.defaultPrintFormat = canonical?.paper_size || (result?.print_format === "pos_80mm" ? "pos_80mm" : "a4");
        return {
            printerId: this.state.printerId,
            printerName: this.state.printerName,
            printFormat: this.state.defaultPrintFormat,
            printer: canonical || selectedRecord || null,
        };
    }

    async _resolveSnapshotBillWizardRef(snapshot) {
        const snapshotId = toNumber(snapshot?.id, 0);
        if (!snapshotId) {
            return false;
        }
        const selectedStoreId = toNumber(this.state.selectedStoreId, 0) || false;
        const documentType = snapshot?.documentType === "return" ? "return" : "sale";
        try {
            const result = await this.orm.call("ab_sales_cashier_api", "get_invoice_print_ref", [], {
                invoice_id: snapshotId,
                store_id: selectedStoreId,
                document_type: documentType,
            });
            const ref = toNumber(result?.header_ref, 0);
            return ref || false;
        } catch {
            return false;
        }
    }

    async _previewSnapshotReceipt(snapshot, payload = {}) {
        const printPayload = this._buildSnapshotPrintPayload(snapshot);
        await this._loadPrintOptions({silent: true});
        const hasPayloadFormat = Object.prototype.hasOwnProperty.call(payload || {}, "printFormat");
        const selectedId = Number.parseInt(
            payload?.printerId !== undefined ? payload.printerId : (this.state.printerId || 0),
            10
        ) || 0;
        const selectedRecord = findPrinterById(this.state.availablePrinters, selectedId) || payload?.printer || null;
        const format = selectedRecord?.paper_size || (
            hasPayloadFormat
                ? (payload?.printFormat === "pos_80mm" ? "pos_80mm" : "a4")
                : (this.state.defaultPrintFormat === "pos_80mm" ? "pos_80mm" : "a4")
        );
        try {
            await this._saveBillWizardPrintPreferences({
                printerId: selectedId,
                printerName: payload?.printerName,
                printFormat: format,
                printer: selectedRecord,
            });
            const headerRef = await this._resolveSnapshotBillWizardRef(snapshot);
            const result = headerRef
                ? await this.orm.call("ab_sales_ui_api", "bill_wizard_render_print_html", [], {
                    header_id: headerRef,
                    print_format: format,
                })
                : await this.orm.call("ab_sales_ui_api", "bill_wizard_render_print_html_from_payload", [], {
                    payload: printPayload,
                    print_format: format,
                });
            const content = String(result?.content || "").trim();
            if (!content) {
                this.notification.add("Nothing to preview.", {type: "warning"});
                return;
            }
            const win = openBillWizardPrintWindow(content, format, {focus: true});
            if (!win) {
                this.notification.add("Pop-up blocked. Allow popups to print.", {type: "warning"});
            }
        } catch (err) {
            this.notification.add(this._rpcError(err, "Preview failed."), {type: "danger"});
        }
    }

    async _confirmSnapshotPrint(snapshot, payload = {}) {
        const printPayload = this._buildSnapshotPrintPayload(snapshot);
        const selectedId = Number.parseInt(
            payload?.printerId !== undefined ? payload.printerId : (this.state.printerId || 0),
            10
        ) || 0;
        const selectedRecord = findPrinterById(this.state.availablePrinters, selectedId) || payload?.printer || null;
        const selectedPrinter = selectedRecord?.label || String(
            payload?.printerName !== undefined ? payload.printerName : (this.state.printerName || "")
        ).trim();
        const printFormat = selectedRecord?.paper_size || (payload?.printFormat === "pos_80mm" ? "pos_80mm" : "a4");
        try {
            await this._saveBillWizardPrintPreferences({
                printerId: selectedId,
                printerName: selectedPrinter,
                printFormat: printFormat,
                printer: selectedRecord,
            });
        } catch (err) {
            this.notification.add(this._rpcError(err, "Failed to save print preferences."), {type: "danger"});
            return;
        }
        try {
            const headerRef = await this._resolveSnapshotBillWizardRef(snapshot);
            const result = headerRef
                ? await this.orm.call("ab_sales_ui_api", "bill_wizard_direct_print", [], {
                    header_id: headerRef,
                    print_format: printFormat,
                    printer_id: selectedId,
                    printer_name: selectedPrinter || this.state.printerName || "",
                    selected_printer: selectedRecord || false,
                })
                : await this.orm.call("ab_sales_ui_api", "bill_wizard_direct_print_from_payload", [], {
                    payload: printPayload,
                    print_format: printFormat,
                    printer_id: selectedId,
                    printer_name: selectedPrinter || this.state.printerName || "",
                    selected_printer: selectedRecord || false,
                });
            const finalPrinter = (result?.printer_name || selectedPrinter || this.state.printerName || "").trim();
            this.state.printerId = Number.parseInt(result?.printer_id || this.state.printerId || 0, 10) || 0;
            this.notification.add(
                finalPrinter
                    ? `Print command sent to '${finalPrinter}'.`
                    : "Print command sent to default system printer.",
                {type: "success"}
            );
        } catch (err) {
            this.notification.add(this._rpcError(err, "Direct print failed."), {type: "danger"});
        }
    }

    async _openSnapshotPrintDialog(snapshot) {
        await this._loadPrintOptions({silent: true});
        this.dialog.add(AbSalesBillWizardPrintDialog, {
            printerId: this.state.printerId || 0,
            printerName: this.state.printerName || "",
            printFormat: this.state.defaultPrintFormat || "a4",
            availablePrinters: this.state.availablePrinters || [],
            onRefreshPrinters: async () => this._loadPrintOptions(),
            onPreview: async (payload) => {
                await this._previewSnapshotReceipt(snapshot, payload || {});
            },
            onConfirm: async (payload) => {
                await this._confirmSnapshotPrint(snapshot, payload || {});
            },
        });
    }

    async printReceipt() {
        const snapshot = this.state.selectedInvoiceSnapshot || this.state.lastSavedSnapshot;
        if (!snapshot) {
            this.notification.add("Select invoice first for printing.", {type: "warning"});
            return;
        }
        if (!snapshot.lines?.length) {
            this.notification.add("No items to print.", {type: "warning"});
            return;
        }
        await this._openSnapshotPrintDialog(snapshot);
    }

}

registry.category("actions").add("ab_sales.cashier", AbSalesCashierAction);
