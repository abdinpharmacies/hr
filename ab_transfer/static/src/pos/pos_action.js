/** @odoo-module **/

import {registry} from "@web/core/registry";
import {Component, markup, onMounted, onWillStart, onWillUnmount, useExternalListener, useRef, useState} from "@odoo/owl";
import {Dialog} from "@web/core/dialog/dialog";
import {useService} from "@web/core/utils/hooks";
import {session} from "@web/session";
import {ABMany2many} from "@ab_widgets/ab_many2many";
import {ABMany2one} from "@ab_widgets/ab_many2one";

const CACHE_PREFIX = "ab_transfer_pos_cache_v1";
const LEGACY_CACHE_KEY = "ab_transfer_pos_cache_v1";
const SAFE_QTY_RE = /^[0-9+\-*/().\s]+$/;
const MIN_WINDOW_WIDTH = 720;
const MIN_WINDOW_HEIGHT = 520;
const BARCODE_START_KEY = "F12";
const BARCODE_END_KEY = "Enter";
const TRANSFER_TYPE_OPTIONS = [
    {value: "1", label: "1 - دورة رواكد رئيسية"},
    {value: "2", label: "2 - دورة رواكد مصغرة"},
    {value: "3", label: "3 - دورة القريب من انتهاء الصلاحية"},
    {value: "4", label: "4 - اخرى"},
];

const getViewportRect = () => {
    if (typeof window === "undefined") {
        return {width: 1280, height: 720};
    }
    if (window.visualViewport) {
        return {
            width: window.visualViewport.width || window.innerWidth || 1280,
            height: window.visualViewport.height || window.innerHeight || 720,
        };
    }
    return {width: window.innerWidth || 1280, height: window.innerHeight || 720};
};

const generateId = (prefix) => {
    const rand = Math.random().toString(36).slice(2, 8);
    return `${prefix}_${Date.now()}_${rand}`;
};

const parseQtyExpression = (value) => {
    const raw = String(value || "").trim();
    if (!raw) {
        return 0;
    }
    if (!SAFE_QTY_RE.test(raw)) {
        const parsed = parseFloat(raw);
        return Number.isFinite(parsed) ? parsed : 0;
    }
    try {
        const result = Function(`"use strict"; return (${raw});`)();
        return Number.isFinite(result) ? result : 0;
    } catch {
        const parsed = parseFloat(raw);
        return Number.isFinite(parsed) ? parsed : 0;
    }
};

class AbTransferPosBarcodeLinkDialog extends Component {
    static template = "ab_transfer.PosBarcodeLinkDialog";
    static components = {Dialog, ABMany2many};
    static props = {
        barcode: String,
        allowEdit: {type: Boolean, optional: true},
        onSave: {type: Function, optional: true},
        close: Function,
    };

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            barcode: (this.props.barcode || "").trim(),
            selected: [],
            loadingLinks: false,
        });
        this.barcodeRef = useRef("barcodeInput");
        this.onProductsUpdate = this.onProductsUpdate.bind(this);
        this.onBarcodeInput = this.onBarcodeInput.bind(this);
        this.confirm = this.confirm.bind(this);
        this._loadLinkedProducts = this._loadLinkedProducts.bind(this);

        onMounted(() => {
            if (this.props.allowEdit && this.barcodeRef.el) {
                this.barcodeRef.el.focus();
                if (typeof this.barcodeRef.el.select === "function") {
                    this.barcodeRef.el.select();
                }
            }
            this._loadLinkedProducts();
        });
    }

    onBarcodeInput(ev) {
        this.state.barcode = ev.target.value || "";
        this._loadLinkedProducts();
    }

    onProductsUpdate(value) {
        this.state.selected = Array.isArray(value) ? value : [];
    }

    async confirm() {
        const barcode = (this.state.barcode || "").trim();
        if (!barcode) {
            return;
        }
        if (this.props.onSave) {
            await this.props.onSave({
                barcode,
                productIds: this.state.selected.map((row) => row.id),
            });
        }
        this.props.close?.();
    }

    async _loadLinkedProducts() {
        const barcode = (this.state.barcode || "").trim();
        if (!barcode) {
            this.state.selected = [];
            return;
        }
        this.state.loadingLinks = true;
        try {
            const products = await this.orm.call("ab_transfer_pos_api", "pos_barcode_temp_products", [], {barcode});
            this.state.selected = Array.isArray(products) ? products : [];
        } catch {
            this.state.selected = [];
        } finally {
            this.state.loadingLinks = false;
        }
    }

    cancel() {
        this.props.close?.();
    }
}

class AbTransferRequestLoadDialog extends Component {
    static template = "ab_transfer.PosTransferRequestLoadDialog";
    static components = {Dialog};
    static props = {
        fromStoreId: {optional: true},
        toStoreId: {optional: true},
        onSelect: {type: Function},
        close: Function,
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            loading: false,
            loadingSelected: false,
            previewLoading: false,
            requests: [],
            selectedRequestId: null,
            preview: this._emptyPreview(),
        });
        this._previewToken = 0;
        this.loadRequests = this.loadRequests.bind(this);
        this.confirm = this.confirm.bind(this);

        onWillStart(async () => {
            await this.loadRequests();
        });
    }

    async loadRequests() {
        this.state.loading = true;
        try {
            const requests = await this.orm.call("ab_transfer_pos_api", "pos_pending_transfer_requests", [], {
                from_store_id: this.props.fromStoreId || false,
                to_store_id: this.props.toStoreId || false,
                limit: 50,
            });
            this.state.requests = Array.isArray(requests) ? requests : [];
            this.state.selectedRequestId = this.state.requests[0]?.id || null;
            await this._loadSelectedRequestPreview();
        } catch (err) {
            this.state.requests = [];
            this.state.selectedRequestId = null;
            this.state.preview = this._emptyPreview();
            const message = err?.data?.message || err?.message || "Failed to load transfer requests.";
            this.notification.add(message, {type: "danger"});
        } finally {
            this.state.loading = false;
        }
    }

    async selectRequest(request) {
        this.state.selectedRequestId = request?.id || null;
        await this._loadSelectedRequestPreview();
    }

    selectedRequest() {
        return this.state.requests.find((request) => request.id === this.state.selectedRequestId) || null;
    }

    _emptyPreview(request = null, error = "") {
        const products = (request?.products || []).map((product) => ({
            ...product,
            available_qty: 0,
            load_qty: 0,
            availability_status: "unavailable",
            availability_label: "Unavailable",
        }));
        return {
            request,
            requested_by: "",
            error,
            products,
            summary: this._buildPreviewSummary(products),
        };
    }

    _buildPreviewSummary(products) {
        const rows = Array.isArray(products) ? products : [];
        return {
            line_count: rows.length,
            total_requested_qty: rows.reduce((sum, row) => sum + (parseFloat(row.requested_qty || 0) || 0), 0),
            total_available_qty: rows.reduce((sum, row) => sum + (parseFloat(row.available_qty || 0) || 0), 0),
            total_load_qty: rows.reduce((sum, row) => sum + (parseFloat(row.load_qty || 0) || 0), 0),
            fully_available_count: rows.filter((row) => row.availability_status === "full").length,
            partially_available_count: rows.filter((row) => row.availability_status === "partial").length,
            unavailable_count: rows.filter((row) => row.availability_status === "unavailable").length,
        };
    }

    _availabilityStatus(requestedQty, loadQty) {
        const requested = parseFloat(requestedQty || 0) || 0;
        const load = parseFloat(loadQty || 0) || 0;
        if (requested > 0 && load >= requested) {
            return {value: "full", label: "Fully available"};
        }
        if (load > 0) {
            return {value: "partial", label: "Partially available"};
        }
        return {value: "unavailable", label: "Unavailable"};
    }

    async _readRequestedBy(request) {
        if (!request?.id) {
            return "";
        }
        try {
            const [record] = await this.orm.read("ab_transfer_request", [request.id], ["user_id"]);
            const user = record?.user_id;
            return Array.isArray(user) ? user[1] || "" : "";
        } catch {
            return "";
        }
    }

    _buildPreviewFromLoadResult(request, result, requestedBy) {
        const loadedByLineId = new Map();
        for (const line of result?.lines || []) {
            const lineId = line.request_line_id || false;
            if (!lineId) {
                continue;
            }
            const current = loadedByLineId.get(lineId) || {available_qty: 0, load_qty: 0};
            current.available_qty = Math.max(
                current.available_qty,
                parseFloat(line.available_qty || 0) || 0
            );
            current.load_qty += parseFloat(line.qty || 0) || 0;
            loadedByLineId.set(lineId, current);
        }
        const products = (request.products || []).map((product) => {
            const loaded = loadedByLineId.get(product.line_id) || {available_qty: 0, load_qty: 0};
            const status = this._availabilityStatus(product.requested_qty, loaded.load_qty);
            return {
                ...product,
                available_qty: loaded.available_qty,
                load_qty: loaded.load_qty,
                availability_status: status.value,
                availability_label: status.label,
            };
        });
        return {
            request,
            requested_by: requestedBy || "",
            error: "",
            products,
            summary: this._buildPreviewSummary(products),
        };
    }

    async _buildPreviewFromProductDetails(request, requestedBy, error) {
        const products = [];
        for (const product of request?.products || []) {
            let availableQty = 0;
            try {
                const details = await this.orm.call("ab_transfer_pos_api", "pos_product_details", [], {
                    from_store_id: this.props.fromStoreId || false,
                    product_id: product.product_id,
                });
                availableQty = parseFloat(details?.balance || 0) || 0;
            } catch {
                availableQty = 0;
            }
            const requestedQty = parseFloat(product.requested_qty || 0) || 0;
            const loadQty = Math.min(requestedQty, availableQty);
            const status = this._availabilityStatus(requestedQty, loadQty);
            products.push({
                ...product,
                available_qty: availableQty,
                load_qty: loadQty,
                availability_status: status.value,
                availability_label: status.label,
            });
        }
        return {
            request,
            requested_by: requestedBy || "",
            error: error || "",
            products,
            summary: this._buildPreviewSummary(products),
        };
    }

    async _loadSelectedRequestPreview() {
        const request = this.selectedRequest();
        const token = ++this._previewToken;
        if (!request) {
            this.state.preview = this._emptyPreview();
            return;
        }
        this.state.previewLoading = true;
        this.state.preview = this._emptyPreview(request);
        const requestedBy = await this._readRequestedBy(request);
        try {
            const result = await this.orm.call("ab_transfer_pos_api", "pos_load_transfer_request", [], {
                request_id: request.id,
                from_store_id: this.props.fromStoreId || false,
                to_store_id: this.props.toStoreId || false,
            });
            if (token === this._previewToken) {
                this.state.preview = this._buildPreviewFromLoadResult(request, result, requestedBy);
            }
        } catch (err) {
            const message = err?.data?.message || err?.message || "";
            const fallbackPreview = await this._buildPreviewFromProductDetails(request, requestedBy, message);
            if (token === this._previewToken) {
                this.state.preview = fallbackPreview;
            }
        } finally {
            if (token === this._previewToken) {
                this.state.previewLoading = false;
            }
        }
    }

    async confirm() {
        const request = this.selectedRequest();
        if (!request || this.state.loadingSelected) {
            return;
        }
        this.state.loadingSelected = true;
        try {
            await this.props.onSelect(request);
            this.props.close?.();
        } catch (err) {
            const message = err?.data?.message || err?.message || "Failed to load transfer request.";
            this.notification.add(message, {type: "danger"});
        } finally {
            this.state.loadingSelected = false;
        }
    }

    cancel() {
        this.props.close?.();
    }

    formatQty(value) {
        const parsed = parseFloat(value || 0);
        if (!Number.isFinite(parsed)) {
            return "0";
        }
        return parsed.toFixed(3).replace(/(?:\.0+|(\.\d*?)0+)$/, "$1");
    }

    formatDateTime(value) {
        if (!value) {
            return "-";
        }
        try {
            return new Date(value).toLocaleString();
        } catch {
            return value;
        }
    }
}

class AbTransferPosAction extends Component {
    static template = "ab_transfer.PosAction";
    static components = {ABMany2one};

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.dialog = useService("dialog");
        this.notification = useService("notification");
        this.cacheKey = `${CACHE_PREFIX}_${session.user_id || 0}`;
        const viewport = getViewportRect();
        const defaultRect = {
            left: Math.round(viewport.width * 0.05),
            top: Math.round(viewport.height * 0.05),
            width: Math.round(viewport.width * 0.9),
            height: Math.round(viewport.height * 0.9),
        };
        this.state = useState({
            loaded: false,
            defaults: {
                from_store: {id: false, name: "", code: ""},
                allowed_from_store_ids: [],
                user: {id: false, name: "", code: ""},
            },
            drafts: [],
            currentDraftId: null,
            productPicker: false,
            productResults: [],
            productQuery: "",
            loadingProducts: false,
            selectionIndex: -1,
            qtyBuffer: "",
            qtyBufferProductId: null,
            selectedLineId: null,
            submitting: false,
            sidebarCollapsed: true,
            posSettingsSaving: false,
            windowRect: defaultRect,
            windowMinimized: false,
            windowMaximized: true,
            windowClosed: false,
        });
        this._lastWindowRect = {...defaultRect};
        this._dragState = null;
        this._resizeState = null;
        this.searchInputRef = useRef("searchInput");
        this.cardsContainerRef = useRef("cardsContainer");
        this._productSearchTimer = null;
        this._uomFactorCache = new Map();
        this._barcodeActive = false;
        this._barcodeBuffer = "";
        this._lineFocusObserver = null;
        this._lineFocusTimer = null;
        this.onProductPick = this.onProductPick.bind(this);
        this.onProductSearch = this.onProductSearch.bind(this);
        this.searchProducts = this.searchProducts.bind(this);
        this.addProductFromSearch = this.addProductFromSearch.bind(this);
        this.openTransferRequestDialog = this.openTransferRequestDialog.bind(this);
        this.loadTransferRequest = this.loadTransferRequest.bind(this);
        this.onLineUomUpdate = this.onLineUomUpdate.bind(this);
        this.toggleSidebar = this.toggleSidebar.bind(this);
        this.savePosUiSettings = this.savePosUiSettings.bind(this);
        this.windowStyle = this.windowStyle.bind(this);
        this.onWindowDragStart = this.onWindowDragStart.bind(this);
        this.onWindowResizeStart = this.onWindowResizeStart.bind(this);
        this.toggleWindowMinimize = this.toggleWindowMinimize.bind(this);
        this.toggleWindowMaximize = this.toggleWindowMaximize.bind(this);
        this.toggleFullScreen = this.toggleFullScreen.bind(this);
        this.closeWindow = this.closeWindow.bind(this);
        this.onProductSearchKeydown = this.onProductSearchKeydown.bind(this);
        this.onKeydown = this.onKeydown.bind(this);

        this.fromStoreDomain = () => {
            const domain = [["allow_sale", "=", true]];
            const storeIds = this.state.defaults.allowed_from_store_ids || [];
            if (storeIds.length) {
                domain.push(["id", "in", storeIds]);
            }
            return domain;
        };
        this.toStoreDomain = () => [["allow_transfer", "=", true]];
        this.userDomain = () => [];
        this.deliveryEmployeeDomain = () => [];
        this.productDomain = () => [["active", "=", true]];

        onWillStart(async () => {
            await this._loadDefaults();
            this._loadCache();
            if (!this.state.drafts.length) {
                this.createNewDraft();
            } else if (!this.currentDraft) {
                this.state.currentDraftId = this.state.drafts[0].id;
            }
            await this.searchProducts((this.state.productQuery || "").trim());
            this.state.loaded = true;
        });

        onWillUnmount(() => {
            if (this._productSearchTimer) {
                clearTimeout(this._productSearchTimer);
                this._productSearchTimer = null;
            }
            this._clearLineFocusObserver();
        });

        useExternalListener(window, "keydown", this.onKeydown, {capture: true});
    }

    get currentDraft() {
        return this.state.drafts.find((draft) => draft.id === this.state.currentDraftId) || null;
    }

    get selectedLine() {
        const draft = this.currentDraft;
        if (!draft) {
            return null;
        }
        return draft.lines.find((line) => line.id === this.state.selectedLineId) || draft.lines[0] || null;
    }

    get transferTypeOptions() {
        return TRANSFER_TYPE_OPTIONS;
    }

    lineUomValue(line) {
        if (!line?.uom_id) {
            return false;
        }
        return {
            id: line.uom_id,
            display_name: line.uom_name || "",
        };
    }

    async _getUomFactor(uomId) {
        const id = parseInt(uomId, 10);
        if (!Number.isFinite(id) || id <= 0) {
            return 0;
        }
        if (this._uomFactorCache.has(id)) {
            return this._uomFactorCache.get(id) || 0;
        }
        try {
            const [uom] = await this.orm.read("ab_product_uom", [id], ["factor"]);
            const factor = parseFloat(uom?.factor || 0) || 0;
            if (factor > 0) {
                this._uomFactorCache.set(id, factor);
            }
            return factor;
        } catch {
            return 0;
        }
    }

    async _loadDefaults() {
        try {
            this.state.defaults = await this.orm.call("ab_transfer_pos_api", "pos_defaults", [], {});
        } catch {
            this.state.defaults = {
                from_store: {id: false, name: "", code: ""},
                allowed_from_store_ids: [],
                user: {id: false, name: "", code: ""},
            };
        }
    }

    _loadCache() {
        try {
            const raw = window.localStorage.getItem(this.cacheKey) || window.localStorage.getItem(LEGACY_CACHE_KEY);
            if (!raw) {
                return;
            }
            const payload = JSON.parse(raw);
            const drafts = Array.isArray(payload) ? payload : Array.isArray(payload?.drafts) ? payload.drafts : [];
            const user = this.state.defaults.user || {};
            const defaultStore = this.state.defaults.from_store || {};
            const allowedStoreIds = this.state.defaults.allowed_from_store_ids || [];
            this.state.drafts = drafts.map((draft) => ({
                ...draft,
                header: {
                    ...(draft.header || {}),
                    ...(
                        allowedStoreIds.length
                        && draft.header?.from_store_id
                        && !allowedStoreIds.includes(parseInt(draft.header.from_store_id, 10))
                            ? {
                                from_store_id: defaultStore.id || false,
                                from_store_name: defaultStore.name || "",
                            }
                            : {}
                    ),
                    user_id: user.id || false,
                    user_name: user.name || "",
                    employee_delivery_id: false,
                    employee_delivery_name: "",
                    transfer_type: draft.header?.transfer_type || draft.header?.notes_type || "",
                    notes: draft.header?.notes || "",
                    transfer_request_id: draft.header?.transfer_request_id || false,
                    transfer_request_name: draft.header?.transfer_request_name || "",
                },
            }));
            this.state.currentDraftId = this.state.drafts[0]?.id || null;
        } catch {
            this.state.drafts = [];
            this.state.currentDraftId = null;
        }
    }

    _saveCache() {
        window.localStorage.setItem(this.cacheKey, JSON.stringify(this.state.drafts || []));
    }

    _defaultHeader() {
        const fromStore = this.state.defaults.from_store || {};
        const user = this.state.defaults.user || {};
        return {
            from_store_id: fromStore.id || false,
            from_store_name: fromStore.name || "",
            to_store_id: false,
            to_store_name: "",
            user_id: user.id || false,
            user_name: user.name || "",
            employee_delivery_id: false,
            employee_delivery_name: "",
            transfer_type: "",
            notes: "",
            transfer_request_id: false,
            transfer_request_name: "",
        };
    }

    _recomputeDraft(draft) {
        if (!draft) {
            return;
        }
        draft.lines.forEach((line) => {
            line.qty = parseQtyExpression(line.qty_str);
        });
        draft.summary = {
            items_count: draft.lines.length,
            total_qty: draft.lines.reduce((sum, line) => sum + (line.qty || 0), 0),
            total_sell_price: draft.lines.reduce(
                (sum, line) => sum + ((line.qty || 0) * (parseFloat(line.sell_price || 0) || 0)),
                0
            ),
            total_cost: draft.lines.reduce(
                (sum, line) => sum + ((line.qty || 0) * (parseFloat(line.cost || 0) || 0)),
                0
            ),
        };
        draft.updated_at = new Date().toISOString();
    }

    _touchCurrentDraft() {
        const draft = this.currentDraft;
        if (!draft) {
            return;
        }
        this._recomputeDraft(draft);
        this.state.drafts = [...this.state.drafts];
        this._saveCache();
    }

    _createNewDraft() {
        const draft = {
            id: generateId("transfer"),
            local_number: `TR-${new Date().toISOString().slice(11, 19).replace(/:/g, "")}`,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
            header: this._defaultHeader(),
            lines: [],
            summary: {
                items_count: 0,
                total_qty: 0,
                total_sell_price: 0,
                total_cost: 0,
            },
        };
        this.state.drafts = [draft, ...this.state.drafts];
        this.state.currentDraftId = draft.id;
        this.state.selectedLineId = null;
        this.state.productPicker = false;
        this.state.selectionIndex = -1;
        this.state.qtyBuffer = "";
        this.state.qtyBufferProductId = null;
        if (this.state.loaded) {
            this.searchProducts((this.state.productQuery || "").trim());
        }
        this._saveCache();
    }

    createNewDraft() {
        this._createNewDraft();
    }

    selectDraft(draftId) {
        this.state.currentDraftId = draftId;
        const draft = this.currentDraft;
        this.state.selectedLineId = draft?.lines[0]?.id || null;
        this.state.productPicker = false;
        this.state.selectionIndex = -1;
        this.state.qtyBuffer = "";
        this.state.qtyBufferProductId = null;
        this.searchProducts((this.state.productQuery || "").trim());
        this._saveCache();
    }

    removeCurrentDraft() {
        if (!this.currentDraft) {
            return;
        }
        this.state.drafts = this.state.drafts.filter((draft) => draft.id !== this.currentDraft.id);
        this.state.currentDraftId = this.state.drafts[0]?.id || null;
        this.state.selectedLineId = this.currentDraft?.lines[0]?.id || null;
        if (!this.state.drafts.length) {
            this._createNewDraft();
            return;
        }
        this._saveCache();
    }

    replaceCurrentDraftWithNew() {
        if (this.currentDraft) {
            this.state.drafts = this.state.drafts.filter((draft) => draft.id !== this.currentDraft.id);
        }
        this._createNewDraft();
    }

    updateHeaderField(field, value, labelField = null) {
        if (field === "user_id") {
            return;
        }
        const draft = this.currentDraft;
        if (!draft) {
            return;
        }
        const normalized = this._normalizeMany2oneValue(value);
        const previousValue = draft.header[field] || false;
        draft.header[field] = normalized.id || false;
        if (labelField) {
            draft.header[labelField] = normalized.display_name || "";
        }
        if (field === "from_store_id") {
            draft.lines = [];
            draft.header.transfer_request_id = false;
            draft.header.transfer_request_name = "";
            this.state.selectedLineId = null;
            this.state.productPicker = false;
            this.state.selectionIndex = -1;
            this.state.qtyBuffer = "";
            this.state.qtyBufferProductId = null;
            this.searchProducts((this.state.productQuery || "").trim());
        }
        if (field === "to_store_id" && previousValue !== (draft.header[field] || false)) {
            draft.header.transfer_request_id = false;
            draft.header.transfer_request_name = "";
        }
        this._touchCurrentDraft();
    }

    _normalizeMany2oneValue(value) {
        if (!value) {
            return {id: false, display_name: ""};
        }
        if (Array.isArray(value)) {
            const first = value[0];
            if (first && typeof first === "object") {
                return this._normalizeMany2oneValue(first);
            }
            return {
                id: first || false,
                display_name: value[1] || "",
            };
        }
        if (typeof value === "object") {
            return {
                id: value.id || value.resId || false,
                display_name: value.display_name || value.displayName || value.name || "",
            };
        }
        return {id: false, display_name: ""};
    }

    onNotesInput(ev) {
        const draft = this.currentDraft;
        if (!draft) {
            return;
        }
        draft.header.notes = ev.target.value || "";
        this._touchCurrentDraft();
    }

    onTransferTypeChange(ev) {
        const draft = this.currentDraft;
        if (!draft) {
            return;
        }
        draft.header.transfer_type = ev.target.value || "";
        this._touchCurrentDraft();
    }

    async onLineUomUpdate(line, value) {
        if (!line) {
            return;
        }
        const normalized = this._normalizeMany2oneValue(value);
        if (!normalized.id) {
            line.uom_id = false;
            line.uom_name = "";
            line.uom_factor = 0;
        } else {
            line.uom_id = normalized.id;
            line.uom_name = normalized.display_name || "";
            line.uom_factor = await this._getUomFactor(line.uom_id);
        }
        this._touchCurrentDraft();
    }

    lineQtyInStockUom(line) {
        const qty = Number.isFinite(line?.qty) ? line.qty : parseFloat(line?.qty || 0) || 0;
        const factor = Number.isFinite(line?.uom_factor)
            ? line.uom_factor
            : parseFloat(line?.uom_factor || 0) || 0;
        return qty * (factor > 0 ? factor : 1);
    }

    async onProductPick(value) {
        this.state.productPicker = value && value.id ? value : false;
        if (!value?.id) {
            return;
        }
        await this.addProductAndFocus(value);
        this.state.productPicker = false;
    }

    toggleSidebar() {
        this.state.sidebarCollapsed = !this.state.sidebarCollapsed;
    }

    async savePosUiSettings() {
        this.state.posSettingsSaving = true;
        try {
            this._saveCache();
            this.notification.add("Transfer POS settings saved.", {type: "success"});
        } finally {
            this.state.posSettingsSaving = false;
        }
    }

    onProductSearch(ev) {
        this.state.productQuery = ev.target.value || "";
        if (this._productSearchTimer) {
            clearTimeout(this._productSearchTimer);
        }
        const query = this.state.productQuery.trim();
        this._productSearchTimer = setTimeout(async () => {
            await this.searchProducts(query);
        }, 200);
    }

    onProductSearchKeydown(ev) {
        const key = ev.key;
        if (this.state.loadingProducts || this.state.submitting) {
            return;
        }
        if (key === "ArrowDown") {
            const products = this.state.productResults || [];
            if (products.length) {
                ev.preventDefault();
                ev.stopPropagation();
                this._selectNextCard();
            }
            return;
        }
        if (key === "Enter") {
            ev.preventDefault();
            ev.stopPropagation();
            return;
        }
        if (ev.ctrlKey || ev.metaKey || ev.altKey) {
            return;
        }
        if ((key && key.length === 1) || key === "Backspace" || key === "Delete") {
            ev.stopPropagation();
        }
    }

    async searchProducts(query) {
        const draft = this.currentDraft;
        if (!draft) {
            this.state.productResults = [];
            this.state.selectionIndex = -1;
            return;
        }
        this.state.loadingProducts = true;
        try {
            const results = await this.orm.call("ab_transfer_pos_api", "pos_product_search", [], {
                search: query || "",
                from_store_id: draft.header.from_store_id || false,
                limit: 24,
            });
            this.state.productResults = Array.isArray(results) ? results : [];
            this.state.selectionIndex = -1;
            this.state.qtyBuffer = "";
            this.state.qtyBufferProductId = null;
        } catch (err) {
            this.state.productResults = [];
            this.state.selectionIndex = -1;
            this.notification.add(err?.message || "Failed to search products.", {type: "danger"});
        } finally {
            this.state.loadingProducts = false;
        }
    }

    async addProductFromSearch(product) {
        if (!product?.id) {
            return;
        }
        await this.addProductAndFocus(product);
    }

    openTransferRequestDialog() {
        const draft = this.currentDraft;
        if (!draft) {
            return;
        }
        if (!draft.header.from_store_id) {
            this.notification.add("Source store is required before loading a transfer request.", {type: "warning"});
            return;
        }
        if (!draft.header.to_store_id) {
            this.notification.add("Destination store is required before loading a transfer request.", {type: "warning"});
            return;
        }
        if (draft.header.transfer_request_id) {
            this.notification.add("This transfer already has a loaded transfer request.", {type: "warning"});
            return;
        }
        this.dialog.add(AbTransferRequestLoadDialog, {
            fromStoreId: draft.header.from_store_id,
            toStoreId: draft.header.to_store_id,
            onSelect: async (request) => {
                await this.loadTransferRequest(request.id);
            },
        });
    }

    async loadTransferRequest(requestId) {
        const draft = this.currentDraft;
        if (!draft) {
            return;
        }
        const result = await this.orm.call("ab_transfer_pos_api", "pos_load_transfer_request", [], {
            request_id: requestId,
            from_store_id: draft.header.from_store_id || false,
            to_store_id: draft.header.to_store_id || false,
        });
        const request = result?.request || {};
        const loadedLines = (Array.isArray(result?.lines) ? result.lines : []).map((line) => ({
            id: generateId("line"),
            request_line_id: line.request_line_id || false,
            product_id: line.product_id,
            product_name: line.product_name || "",
            product_code: line.product_code || "",
            qty_str: this.formatQty(line.qty || 0),
            qty: parseFloat(line.qty || 0) || 0,
            requested_qty: parseFloat(line.requested_qty || 0) || 0,
            requested_qty_str: this.formatQty(line.requested_qty || 0),
            available_qty: parseFloat(line.available_qty || 0) || 0,
            class_id: line.class_id || 0,
            expiry_date: line.expiry_date || "",
            uom_id: line.uom_id || false,
            uom_name: line.uom_name || "",
            uom_category_id: line.uom_category_id || false,
            uom_factor: parseFloat(line.uom_factor || 0) || 0,
            default_uom_id: line.default_uom_id || line.uom_id || false,
            default_uom_factor: parseFloat(line.default_uom_factor || line.uom_factor || 0) || 1,
            sell_price: parseFloat(line.sell_price || 0) || 0,
            cost: parseFloat(line.cost || 0) || 0,
            purchase_price: parseFloat(line.purchase_price || 0) || 0,
            tax_value: parseFloat(line.tax_value || 0) || 0,
            balance: parseFloat(line.balance || 0) || 0,
            inventory_rows: Array.isArray(line.inventory_rows) ? line.inventory_rows : [],
            inventory_table_html: line.inventory_table_html || "",
        }));
        if (!loadedLines.length) {
            throw new Error("No transfer request lines were loaded.");
        }
        draft.header.transfer_request_id = request.id || requestId;
        draft.header.transfer_request_name = request.display_name || "";
        draft.lines = [...loadedLines, ...draft.lines];
        this.state.selectedLineId = loadedLines[0]?.id || draft.lines[0]?.id || null;
        this._touchCurrentDraft();
        this.notification.add(`${draft.header.transfer_request_name || "Transfer request"} loaded.`, {type: "success"});
        const skipped = Array.isArray(result?.skipped_products) ? result.skipped_products : [];
        if (skipped.length) {
            this.notification.add(`No available stock rows for: ${skipped.join(", ")}`, {type: "warning"});
        }
    }

    async addProductAndFocus(product, qty = 1) {
        if (!product?.id) {
            return null;
        }
        const line = await this.addProduct(product.id, qty);
        if (!line) {
            return null;
        }
        if (this.searchInputRef.el) {
            this.searchInputRef.el.blur();
        }
        if (document.activeElement && document.activeElement !== document.body) {
            document.activeElement.blur?.();
        }
        this._focusLineQty(line);
        return line;
    }

    async addProduct(productId, qty = 1) {
        const draft = this.currentDraft;
        if (!draft?.header.from_store_id || !productId) {
            if (!draft?.header.from_store_id) {
                this.notification.add("Select a source store first.", {type: "warning"});
            }
            return null;
        }
        try {
            const details = await this.orm.call("ab_transfer_pos_api", "pos_product_details", [], {
                from_store_id: draft.header.from_store_id,
                product_id: productId,
            });
            const inventoryRows = Array.isArray(details?.inventory_rows) ? details.inventory_rows : [];
            const parsedQty = parseQtyExpression(qty);
            const lineQty = Number.isFinite(parsedQty) && parsedQty > 0 ? parsedQty : 1;
            const line = {
                id: generateId("line"),
                product_id: details.product_id || productId,
                product_name: details.product_name || "",
                product_code: details.product_code || "",
                qty_str: String(lineQty),
                qty: lineQty,
                class_id: details.class_id || parseInt(inventoryRows[0]?.source_id || 0, 10) || 0,
                expiry_date: details.expiry_date || String(inventoryRows[0]?.exp_date || "").split(" ")[0],
                uom_id: details.uom_id || false,
                uom_name: details.uom_name || "",
                uom_category_id: details.uom_category_id || false,
                uom_factor: parseFloat(details.uom_factor || 0) || 0,
                default_uom_id: details.default_uom_id || details.uom_id || false,
                default_uom_factor: parseFloat(details.default_uom_factor || details.uom_factor || 0) || 1,
                sell_price: parseFloat(details.sell_price || 0) || 0,
                cost: parseFloat(details.cost || 0) || 0,
                purchase_price: parseFloat(details.purchase_price || 0) || 0,
                tax_value: parseFloat(details.tax_value || 0) || 0,
                requested_qty: 0,
                requested_qty_str: "",
                balance: parseFloat(details.balance || 0) || 0,
                inventory_rows: inventoryRows,
                inventory_table_html: details.inventory_table_html || "",
            };
            draft.lines = [line, ...draft.lines];
            this.state.selectedLineId = line.id;
            this._touchCurrentDraft();
            return line;
        } catch (err) {
            this.notification.add(err?.message || "Failed to load product details.", {type: "danger"});
            return null;
        }
    }

    selectLine(lineId) {
        this.state.selectedLineId = lineId;
    }

    removeLine(lineId) {
        const draft = this.currentDraft;
        if (!draft) {
            return;
        }
        draft.lines = draft.lines.filter((line) => line.id !== lineId);
        this.state.selectedLineId = draft.lines[0]?.id || null;
        this._touchCurrentDraft();
    }

    _focusSearchSelectAll() {
        const el = this.searchInputRef.el;
        if (!el) {
            return;
        }
        setTimeout(() => {
            el.focus();
            if (typeof el.select === "function") {
                el.select();
            }
            if (typeof el.setSelectionRange === "function") {
                el.setSelectionRange(0, el.value?.length || 0);
            }
        }, 0);
        this.state.selectionIndex = -1;
        this.state.qtyBuffer = "";
        this.state.qtyBufferProductId = null;
    }

    _selectPreviousCard() {
        const products = this.state.productResults || [];
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
        const products = this.state.productResults || [];
        if (!products.length) {
            return;
        }
        if (this.state.selectionIndex < 0) {
            this._setSelectionIndex(0);
            return;
        }
        this._setSelectionIndex(Math.min(this.state.selectionIndex + 1, products.length - 1));
    }

    _setSelectionIndex(index) {
        const products = this.state.productResults || [];
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
            const card = container?.querySelector?.(`[data-product-id="${product.id}"]`);
            card?.scrollIntoView?.({block: "nearest"});
            card?.focus?.();
        }
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
            const parsed = parseQtyExpression(this.state.qtyBuffer);
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
        const isOp = key === "." || key === "/" || key === "*" || key === "+" || key === "-" || key === "(" || key === ")";
        return isDigit || isOp || key === "Backspace" || key === "Escape";
    }

    _handleQtyInputKey(ev, key, products, isSearchFocused) {
        if (isSearchFocused || this.state.selectionIndex < 0 || !this._isQtyInputKey(key)) {
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
        if (key === "." && (this.state.qtyBufferProductId === product.id ? this.state.qtyBuffer : "").includes(".")) {
            return true;
        }
        if (this.state.qtyBufferProductId !== product.id) {
            this.state.qtyBuffer = "";
            this.state.qtyBufferProductId = product.id;
        }
        this.state.qtyBuffer = `${this.state.qtyBuffer || ""}${key}`;
        return true;
    }

    _onHotkeyArrowDown(ev, {isSearchFocused} = {}) {
        if (isSearchFocused) {
            return;
        }
        ev.preventDefault();
        this._selectNextCard();
    }

    _onHotkeyArrowUp(ev, {isSearchFocused} = {}) {
        if (isSearchFocused) {
            return;
        }
        ev.preventDefault();
        this._selectPreviousCard();
    }

    async _onHotkeyEnter(ev, {isSearchFocused, products} = {}) {
        if (isSearchFocused || this.state.selectionIndex < 0) {
            return;
        }
        ev.preventDefault();
        const product = this._getSelectedProduct(products);
        if (!product) {
            return;
        }
        const qty = this._consumeQtyForProduct(product);
        await this.addProductAndFocus(product, qty);
    }

    _isEditableElement(el) {
        if (!el) {
            return false;
        }
        const tag = el.tagName;
        if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") {
            return true;
        }
        return el.isContentEditable === true;
    }

    _resetBarcodeBuffer() {
        this._barcodeActive = false;
        this._barcodeBuffer = "";
    }

    _handleBarcodeKeydown(ev) {
        const key = ev.key;
        if (key === BARCODE_START_KEY) {
            ev.preventDefault();
            ev.stopPropagation();
            ev.stopImmediatePropagation?.();
            if (document.body.classList.contains("modal-open")) {
                this._resetBarcodeBuffer();
                return true;
            }
            this._barcodeActive = true;
            this._barcodeBuffer = "";
            return true;
        }
        if (!this._barcodeActive) {
            return false;
        }
        ev.preventDefault();
        ev.stopPropagation();
        ev.stopImmediatePropagation?.();
        if (key === BARCODE_END_KEY) {
            const barcode = (this._barcodeBuffer || "").trim();
            this._resetBarcodeBuffer();
            if (barcode) {
                this._handleBarcodeScan(barcode);
            }
            return true;
        }
        if (key === "Escape") {
            this._resetBarcodeBuffer();
            return true;
        }
        if (key && key.length === 1) {
            this._barcodeBuffer += key;
            return true;
        }
        return true;
    }

    async _handleBarcodeScan(barcode) {
        if (this.state.submitting) {
            return;
        }
        const draft = this.currentDraft;
        if (!draft) {
            this.notification.add("Create a transfer before scanning.", {type: "warning"});
            return;
        }
        if (!draft.header.from_store_id) {
            this.notification.add("Select a source store before scanning.", {type: "warning"});
            return;
        }
        this.state.loadingProducts = true;
        try {
            const products = await this._fetchBarcodeProducts(barcode, draft.header.from_store_id);
            this._applyBarcodeResults(barcode, products);
            if (!products.length) {
                this._openBarcodeLinkDialog(barcode);
                return;
            }
            if (products.length === 1) {
                await this.addProductAndFocus(products[0], 1);
            }
        } catch (err) {
            this.notification.add(err?.message || "Barcode scan failed.", {type: "danger"});
        } finally {
            this.state.loadingProducts = false;
        }
    }

    async _fetchBarcodeProducts(barcode, fromStoreId) {
        const products = await this.orm.call("ab_transfer_pos_api", "pos_barcode_products", [], {
            barcode,
            from_store_id: fromStoreId || false,
        });
        return Array.isArray(products) ? products : [];
    }

    _applyBarcodeResults(barcode, products) {
        this.state.productQuery = barcode || "";
        this.state.productResults = Array.isArray(products) ? products : [];
        this.state.selectionIndex = -1;
        this.state.qtyBuffer = "";
        this.state.qtyBufferProductId = null;
    }

    _openBarcodeLinkDialog(barcode) {
        if (!barcode) {
            return;
        }
        this.dialog.add(AbTransferPosBarcodeLinkDialog, {
            barcode,
            allowEdit: false,
            onSave: async ({barcode: linkBarcode, productIds}) => {
                await this._linkBarcodeProducts(linkBarcode, productIds);
            },
        });
    }

    _openBarcodeRegisterDialog() {
        this.dialog.add(AbTransferPosBarcodeLinkDialog, {
            barcode: "",
            allowEdit: true,
            onSave: async ({barcode: linkBarcode, productIds}) => {
                await this._linkBarcodeProducts(linkBarcode, productIds);
            },
        });
    }

    async _linkBarcodeProducts(barcode, productIds) {
        try {
            const result = await this.orm.call("ab_transfer_pos_api", "pos_link_barcode_temp", [], {
                barcode,
                product_ids: productIds,
            });
            const count = Array.isArray(result?.product_ids) ? result.product_ids.length : 0;
            this.notification.add(`Barcode links saved (${count} product(s)).`, {type: "success"});
            const draft = this.currentDraft;
            if (draft?.header.from_store_id) {
                const products = await this._fetchBarcodeProducts(barcode, draft.header.from_store_id);
                this._applyBarcodeResults(barcode, products);
                if (products.length === 1) {
                    await this.addProductAndFocus(products[0], 1);
                }
            }
        } catch (err) {
            this.notification.add(err?.message || "Failed to save barcode links.", {type: "danger"});
        }
    }

    _clearLineFocusObserver() {
        if (this._lineFocusObserver) {
            this._lineFocusObserver.disconnect();
            this._lineFocusObserver = null;
        }
        if (this._lineFocusTimer) {
            clearTimeout(this._lineFocusTimer);
            this._lineFocusTimer = null;
        }
    }

    _focusLineQty(line) {
        const lineId = line?.id;
        const productId = line?.product_id;
        if (!lineId && !productId) {
            return;
        }
        if (lineId) {
            this.state.selectedLineId = lineId;
        }
        this._clearLineFocusObserver();
        const findInput = () => {
            const root = this.el || document.querySelector(".o_ab_transfer_pos_window");
            if (!root) {
                return null;
            }
            let row = null;
            if (lineId) {
                row = root.querySelector(`tr[data-line-id="${lineId}"]`);
            }
            if (!row && productId) {
                row = root.querySelector(`tr[data-product-id="${productId}"]`);
            }
            return row?.querySelector?.('input[data-field="qty_str"]') || null;
        };
        const focusInput = (input) => {
            if (!input) {
                return false;
            }
            const selectAll = () => {
                try {
                    input.select?.();
                    input.setSelectionRange?.(0, input.value?.length || 0);
                } catch {
                    // Ignore selection errors for non-text inputs.
                }
            };
            input.focus();
            selectAll();
            requestAnimationFrame(selectAll);
            setTimeout(selectAll, 0);
            input.scrollIntoView?.({block: "nearest"});
            return true;
        };

        if (focusInput(findInput())) {
            return;
        }

        const observerTarget =
            document.querySelector(".o_ab_transfer_pos_lines_table tbody") || document.body;
        this._lineFocusObserver = new MutationObserver(() => {
            if (focusInput(findInput())) {
                this._clearLineFocusObserver();
            }
        });
        this._lineFocusObserver.observe(observerTarget, {childList: true, subtree: true});
        this._lineFocusTimer = setTimeout(() => {
            this._clearLineFocusObserver();
        }, 2500);
    }

    _getFocusedLine() {
        const active = document.activeElement;
        const row = active?.closest?.(".ab_transfer_pos_line_row");
        const root = this.el || document.querySelector(".o_ab_transfer_pos_window");
        if (!row || (root && !root.contains(row))) {
            return null;
        }
        const lineId = row.dataset.lineId || "";
        const draft = this.currentDraft;
        if (!lineId || !draft) {
            return null;
        }
        return (draft.lines || []).find((line) => String(line.id) === String(lineId)) || null;
    }

    _getLineIndex(line) {
        const draft = this.currentDraft;
        if (!line || !draft) {
            return -1;
        }
        return (draft.lines || []).findIndex((candidate) => String(candidate.id) === String(line.id));
    }

    _getLineFocusTargetAfterRemoval(line) {
        const draft = this.currentDraft;
        const lines = draft?.lines || [];
        const index = this._getLineIndex(line);
        if (index < 0) {
            return null;
        }
        return lines[index - 1] || lines[index + 1] || null;
    }

    _handleRemoveFocusedLineShortcut(ev) {
        if (ev.key !== "Delete" || !ev.ctrlKey || ev.altKey || ev.metaKey) {
            return false;
        }
        const line = this._getFocusedLine();
        if (!line) {
            return false;
        }
        const focusTarget = this._getLineFocusTargetAfterRemoval(line);
        ev.preventDefault();
        ev.stopPropagation();
        ev.stopImmediatePropagation?.();
        this.removeLine(line.id);
        if (focusTarget) {
            this._focusLineQty(focusTarget);
        }
        return true;
    }

    _handleTransferLineArrowNavigation(ev) {
        if (
            (ev.key !== "ArrowUp" && ev.key !== "ArrowDown") ||
            ev.ctrlKey ||
            ev.altKey ||
            ev.metaKey ||
            ev.shiftKey
        ) {
            return false;
        }
        if (document.activeElement?.closest?.(".o_ab_many2one_wrapper")) {
            return false;
        }
        const line = this._getFocusedLine();
        const draft = this.currentDraft;
        if (!line || !draft) {
            return false;
        }
        const lines = draft.lines || [];
        const index = this._getLineIndex(line);
        if (index < 0) {
            return false;
        }
        const nextIndex = ev.key === "ArrowUp" ? index - 1 : index + 1;
        const nextLine = lines[nextIndex] || null;
        ev.preventDefault();
        ev.stopPropagation();
        ev.stopImmediatePropagation?.();
        if (nextLine) {
            this._focusLineQty(nextLine);
        }
        return true;
    }

    onKeydown(ev) {
        if (this._handleBarcodeKeydown(ev)) {
            return;
        }
        if (ev.key === "F2") {
            if (!document.body.classList.contains("modal-open")) {
                ev.preventDefault();
                ev.stopPropagation();
                this._focusSearchSelectAll();
            }
            return;
        }
        if (ev.key === "F9") {
            if (!document.body.classList.contains("modal-open")) {
                ev.preventDefault();
                ev.stopPropagation();
                this._openBarcodeRegisterDialog();
            }
            return;
        }
        if (ev.key === "F10") {
            if (!this.state.submitting && !document.body.classList.contains("modal-open")) {
                ev.preventDefault();
                ev.stopPropagation();
                this.submitCurrentDraft();
            }
            return;
        }
        if (this.state.loadingProducts || this.state.submitting || document.body.classList.contains("modal-open")) {
            return;
        }
        const key = ev.key;
        if (this._handleRemoveFocusedLineShortcut(ev)) {
            return;
        }
        if (this._handleTransferLineArrowNavigation(ev)) {
            return;
        }
        const isSearchFocused = document.activeElement === this.searchInputRef.el;
        if (this._isEditableElement(document.activeElement) && !isSearchFocused) {
            return;
        }
        const products = this.state.productResults || [];
        if (isSearchFocused) {
            return;
        }
        if (this._handleQtyInputKey(ev, key, products, isSearchFocused)) {
            return;
        }
        if (key === "ArrowDown") {
            this._onHotkeyArrowDown(ev, {isSearchFocused, products});
        } else if (key === "ArrowUp") {
            this._onHotkeyArrowUp(ev, {isSearchFocused, products});
        } else if (key === "Enter") {
            this._onHotkeyEnter(ev, {isSearchFocused, products});
        }
    }

    onQtyInput(line, ev) {
        line.qty_str = ev.target.value || "";
        line.qty = parseQtyExpression(line.qty_str);
        this._touchCurrentDraft();
    }

    onSourceChange(line, ev) {
        const index = parseInt(ev.target.value || 0, 10) || 0;
        const selected = Array.isArray(line.inventory_rows) ? line.inventory_rows[index] : null;
        if (!selected) {
            return;
        }
        line.class_id = parseInt(selected.source_id || 0, 10) || 0;
        line.expiry_date = String(selected.exp_date || "").split(" ")[0];
        line.sell_price = parseFloat(selected.price || 0) || 0;
        line.cost = parseFloat(selected.cost || 0) || 0;
        line.purchase_price = parseFloat(selected.pharm_price || 0) || 0;
        line.tax_value = parseFloat(selected.sell_tax || 0) || 0;
        this._touchCurrentDraft();
    }

    sourceIndex(line) {
        if (!Array.isArray(line?.inventory_rows)) {
            return 0;
        }
        const index = line.inventory_rows.findIndex((row) => {
            return parseInt(row.source_id || 0, 10) === parseInt(line.class_id || 0, 10);
        });
        return index >= 0 ? index : 0;
    }

    sourceLabel(row, index) {
        const exp = String(row?.exp_date || "").split(" ")[0] || "-";
        const qty = this.formatQty(row?.qty || 0);
        const price = this.formatQty(row?.price || 0);
        return `#${row?.source_id || 0} | Qty ${qty} | Price ${price}`;
    }

    async submitCurrentDraft() {
        const draft = this.currentDraft;
        if (!draft || this.state.submitting) {
            return;
        }
        if (!draft.header.from_store_id) {
            this.notification.add("Source store is required.", {type: "warning"});
            return;
        }
        if (!draft.header.to_store_id) {
            this.notification.add("Destination store is required.", {type: "warning"});
            return;
        }
        if (!draft.header.user_id) {
            this.notification.add("User is required.", {type: "warning"});
            return;
        }
        if (!draft.header.transfer_type) {
            this.notification.add("Transfer type is required.", {type: "warning"});
            return;
        }
        if (!draft.lines.length) {
            this.notification.add("Add at least one product.", {type: "warning"});
            return;
        }

        this.state.submitting = true;
        try {
            const result = await this.orm.call("ab_transfer_pos_api", "pos_submit", [], {
                header: {
                    from_store_id: draft.header.from_store_id,
                    to_store_id: draft.header.to_store_id,
                    user_id: draft.header.user_id,
                    transfer_type: draft.header.transfer_type || "",
                    notes: draft.header.notes || "",
                    transfer_request_id: draft.header.transfer_request_id || false,
                },
                lines: draft.lines.map((line) => ({
                    product_id: line.product_id,
                    class_id: line.class_id,
                    qty: line.qty || parseQtyExpression(line.qty_str),
                    requested_qty: line.requested_qty || 0,
                    expiry_date: line.expiry_date,
                    uom_id: line.uom_id || false,
                })),
            });
            this.notification.add("Transfer submitted successfully.", {type: "success"});
            this.replaceCurrentDraftWithNew();
            if (result?.type) {
                this.action.doAction(result);
            }
        } catch (err) {
            const message = err?.data?.message || err?.message || "Transfer submit failed.";
            this.notification.add(message, {type: "danger"});
        } finally {
            this.state.submitting = false;
        }
    }

    openHeaderList() {
        this.action.doAction("ab_transfer.ab_transfer_header_action");
    }

    renderHtml(value) {
        return markup(value || "");
    }

    formatQty(value) {
        const parsed = parseFloat(value || 0);
        if (!Number.isFinite(parsed)) {
            return "0";
        }
        return parsed.toFixed(3).replace(/(?:\.0+|(\.\d*?)0+)$/, "$1");
    }

    formatPrice(value) {
        const parsed = parseFloat(value || 0);
        if (!Number.isFinite(parsed)) {
            return "0.00";
        }
        return parsed.toFixed(2);
    }

    productLabel(product) {
        return product?.name || product?.product_card_name || `${product?.code || ""}`.trim() || `#${product?.id}`;
    }

    formatDateTime(value) {
        if (!value) {
            return "-";
        }
        try {
            return new Date(value).toLocaleString();
        } catch {
            return value;
        }
    }

    lineSourceQty(line) {
        const rows = Array.isArray(line?.inventory_rows) ? line.inventory_rows : [];
        const row = rows[this.sourceIndex(line)] || rows[0] || null;
        if (!row) {
            return "0";
        }
        const factor = Number.isFinite(line?.uom_factor)
            ? line.uom_factor
            : parseFloat(line?.uom_factor || 0) || 0;
        const qty = parseFloat(row.qty_in_small_unit ?? row.qty ?? 0) || 0;
        return this.formatQty(factor > 0 ? qty / factor : qty);
    }

    windowStyle() {
        if (this.state.windowMaximized) {
            return "";
        }
        const rect = this.state.windowRect;
        if (!rect) {
            return "";
        }
        if (this.state.windowMinimized) {
            return `left:${rect.left}px; top:${rect.top}px;`;
        }
        return `left:${rect.left}px; top:${rect.top}px; width:${rect.width}px; height:${rect.height}px;`;
    }

    toggleWindowMinimize() {
        if (this.state.windowMinimized) {
            this.state.windowMinimized = false;
            return;
        }
        if (this.state.windowMaximized) {
            this.state.windowMaximized = false;
            this.state.windowRect = {...this._lastWindowRect};
        }
        this.state.windowMinimized = true;
    }

    toggleWindowMaximize() {
        if (this.state.windowMaximized) {
            this.state.windowMaximized = false;
            this.state.windowMinimized = false;
            this.state.windowRect = {...this._lastWindowRect};
            return;
        }
        const rect = this.state.windowRect;
        if (rect) {
            this._lastWindowRect = {...rect};
        }
        this.state.windowMaximized = true;
        this.state.windowMinimized = false;
    }

    async toggleFullScreen() {
        if (typeof document === "undefined") {
            return;
        }
        try {
            if (!document.fullscreenElement) {
                await document.documentElement.requestFullscreen();
            } else {
                await document.exitFullscreen();
            }
        } catch {
            this.notification.add("Fullscreen not available.", {type: "warning"});
        }
    }

    closeWindow() {
        try {
            this.action.doAction({type: "ir.actions.act_window_close"});
        } finally {
            this.state.windowClosed = true;
        }
    }

    onWindowDragStart(ev) {
        if (this.state.windowMaximized) {
            return;
        }
        if (ev.target?.closest?.(".o_ab_sales_pos_window_controls")) {
            return;
        }
        if (ev.button !== 0) {
            return;
        }
        const rect = this.state.windowRect;
        if (!rect) {
            return;
        }
        ev.preventDefault();
        this._dragState = {
            startX: ev.clientX,
            startY: ev.clientY,
            startLeft: rect.left,
            startTop: rect.top,
        };
        const onMove = (moveEv) => {
            if (!this._dragState) {
                return;
            }
            const viewport = getViewportRect();
            const nextLeft = this._dragState.startLeft + (moveEv.clientX - this._dragState.startX);
            const nextTop = this._dragState.startTop + (moveEv.clientY - this._dragState.startY);
            const maxLeft = Math.max(0, viewport.width - rect.width);
            const maxTop = Math.max(0, viewport.height - rect.height);
            this.state.windowRect = {
                ...rect,
                left: Math.min(Math.max(0, nextLeft), maxLeft),
                top: Math.min(Math.max(0, nextTop), maxTop),
            };
            document.body.style.cursor = "move";
        };
        const onUp = () => {
            this._dragState = null;
            if (!this.state.windowMaximized) {
                this._lastWindowRect = {...this.state.windowRect};
            }
            document.body.style.cursor = "";
            window.removeEventListener("pointermove", onMove);
            window.removeEventListener("pointerup", onUp);
            window.removeEventListener("pointercancel", onUp);
        };
        window.addEventListener("pointermove", onMove);
        window.addEventListener("pointerup", onUp);
        window.addEventListener("pointercancel", onUp);
    }

    onWindowResizeStart(ev) {
        if (this.state.windowMaximized || this.state.windowMinimized) {
            return;
        }
        if (ev.button !== 0) {
            return;
        }
        const rect = this.state.windowRect;
        if (!rect) {
            return;
        }
        ev.preventDefault();
        this._resizeState = {
            startX: ev.clientX,
            startY: ev.clientY,
            startWidth: rect.width,
            startHeight: rect.height,
        };
        const onMove = (moveEv) => {
            if (!this._resizeState) {
                return;
            }
            const viewport = getViewportRect();
            const nextWidth = Math.min(
                Math.max(MIN_WINDOW_WIDTH, this._resizeState.startWidth + (moveEv.clientX - this._resizeState.startX)),
                viewport.width - rect.left
            );
            const nextHeight = Math.min(
                Math.max(MIN_WINDOW_HEIGHT, this._resizeState.startHeight + (moveEv.clientY - this._resizeState.startY)),
                viewport.height - rect.top
            );
            this.state.windowRect = {
                ...rect,
                width: nextWidth,
                height: nextHeight,
            };
            document.body.style.cursor = "nwse-resize";
        };
        const onUp = () => {
            this._resizeState = null;
            if (!this.state.windowMaximized) {
                this._lastWindowRect = {...this.state.windowRect};
            }
            document.body.style.cursor = "";
            window.removeEventListener("pointermove", onMove);
            window.removeEventListener("pointerup", onUp);
            window.removeEventListener("pointercancel", onUp);
        };
        window.addEventListener("pointermove", onMove);
        window.addEventListener("pointerup", onUp);
        window.addEventListener("pointercancel", onUp);
    }
}

registry.category("actions").add("ab_transfer.pos", AbTransferPosAction);
