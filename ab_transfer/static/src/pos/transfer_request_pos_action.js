/** @odoo-module **/

import {registry} from "@web/core/registry";
import {Component, onWillStart, onWillUnmount, useState} from "@odoo/owl";
import {useService} from "@web/core/utils/hooks";
import {ABMany2one} from "@ab_widgets/ab_many2one";

const SAFE_QTY_RE = /^[0-9+\-*/().\s]+$/;

const generateRequestNumber = () => {
    const now = new Date();
    const time = now.toISOString().slice(11, 19).replace(/:/g, "");
    return `TRQ-${time}`;
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

class AbTransferRequestPosAction extends Component {
    static template = "ab_transfer.TransferRequestPosAction";
    static components = {ABMany2one};

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({
            loaded: false,
            defaults: {
                from_store: {id: false, name: "", code: ""},
                allowed_from_store_ids: [],
                user: {id: false, name: "", code: ""},
            },
            requestNumber: generateRequestNumber(),
            header: {
                from_store_id: false,
                from_store_name: "",
                to_store_id: false,
                to_store_name: "",
                user_id: false,
                user_name: "",
                notes: "",
            },
            lines: [],
            productQuery: "",
            productResults: [],
            loadingProducts: false,
            submitting: false,
            windowClosed: false,
        });
        this._productSearchTimer = null;
        this.fromStoreDomain = () => {
            const domain = [["allow_sale", "=", true]];
            const storeIds = this.state.defaults.allowed_from_store_ids || [];
            if (storeIds.length) {
                domain.push(["id", "in", storeIds]);
            }
            return domain;
        };
        this.toStoreDomain = () => [["allow_transfer", "=", true]];

        onWillStart(async () => {
            await this._loadDefaults();
            this._resetRequest(false);
            await this.searchProducts("");
            this.state.loaded = true;
        });

        onWillUnmount(() => {
            if (this._productSearchTimer) {
                clearTimeout(this._productSearchTimer);
                this._productSearchTimer = null;
            }
        });
    }

    get summary() {
        return {
            items_count: this.state.lines.length,
            total_qty: this.state.lines.reduce((sum, line) => sum + (parseFloat(line.requested_qty || 0) || 0), 0),
        };
    }

    async _loadDefaults() {
        try {
            this.state.defaults = await this.orm.call("ab_transfer_request_pos_api", "pos_defaults", [], {});
        } catch {
            this.state.defaults = {
                from_store: {id: false, name: "", code: ""},
                allowed_from_store_ids: [],
                user: {id: false, name: "", code: ""},
            };
        }
    }

    _resetRequest(searchAfterReset = true) {
        const fromStore = this.state.defaults.from_store || {};
        const user = this.state.defaults.user || {};
        this.state.requestNumber = generateRequestNumber();
        this.state.header = {
            from_store_id: fromStore.id || false,
            from_store_name: fromStore.name || "",
            to_store_id: false,
            to_store_name: "",
            user_id: user.id || false,
            user_name: user.name || "",
            notes: "",
        };
        this.state.lines = [];
        if (searchAfterReset) {
            this.searchProducts((this.state.productQuery || "").trim());
        }
    }

    createNewRequest() {
        this._resetRequest();
    }

    sourceValue() {
        if (!this.state.header.from_store_id) {
            return false;
        }
        return {
            id: this.state.header.from_store_id,
            display_name: this.state.header.from_store_name || "",
        };
    }

    destinationValue() {
        if (!this.state.header.to_store_id) {
            return false;
        }
        return {
            id: this.state.header.to_store_id,
            display_name: this.state.header.to_store_name || "",
        };
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

    updateSource(value) {
        const normalized = this._normalizeMany2oneValue(value);
        this.state.header.from_store_id = normalized.id || false;
        this.state.header.from_store_name = normalized.display_name || "";
    }

    updateDestination(value) {
        const normalized = this._normalizeMany2oneValue(value);
        const defaultStoreId = this.state.defaults.from_store?.id || false;
        const shouldMirrorRequestingStore =
            !this.state.header.from_store_id
            || (
                defaultStoreId
                && String(this.state.header.from_store_id) === String(defaultStoreId)
            );
        this.state.header.to_store_id = normalized.id || false;
        this.state.header.to_store_name = normalized.display_name || "";
        if (normalized.id && shouldMirrorRequestingStore) {
            this.state.header.from_store_id = normalized.id;
            this.state.header.from_store_name = normalized.display_name || "";
        }
    }

    onNotesInput(ev) {
        this.state.header.notes = ev.target.value || "";
    }

    onProductSearch(ev) {
        this.state.productQuery = ev.target.value || "";
        if (this._productSearchTimer) {
            clearTimeout(this._productSearchTimer);
        }
        this._productSearchTimer = setTimeout(() => {
            this.searchProducts((this.state.productQuery || "").trim());
        }, 200);
    }

    async searchProducts(search) {
        this.state.loadingProducts = true;
        try {
            const results = await this.orm.call("ab_transfer_request_pos_api", "pos_product_search", [], {
                search,
                limit: 30,
            });
            this.state.productResults = Array.isArray(results) ? results : [];
        } catch (err) {
            this.state.productResults = [];
            this.notification.add(err?.message || "Product search failed.", {type: "danger"});
        } finally {
            this.state.loadingProducts = false;
        }
    }

    productLabel(product) {
        return product?.name || product?.product_card_name || `${product?.code || ""}`.trim() || `#${product?.id}`;
    }

    addProduct(product) {
        const productId = parseInt(product?.id || 0, 10);
        if (!productId) {
            return;
        }
        const uomId = product.uom_id || false;
        const existing = this.state.lines.find((line) => {
            return line.product_id === productId && (line.uom_id || false) === (uomId || false);
        });
        if (existing) {
            existing.requested_qty = (parseFloat(existing.requested_qty || 0) || 0) + 1;
            existing.requested_qty_str = this.formatQty(existing.requested_qty);
        } else {
            this.state.lines.push({
                id: `line_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
                product_id: productId,
                product_name: this.productLabel(product),
                product_code: product.code || "",
                requested_qty: 1,
                requested_qty_str: "1",
                uom_id: uomId,
                uom_name: product.uom_name || "",
                uom_category_id: product.uom_category_id || false,
                notes: "",
            });
        }
        this.state.lines = [...this.state.lines];
    }

    removeLine(lineId) {
        this.state.lines = this.state.lines.filter((line) => line.id !== lineId);
    }

    onLineQtyInput(line, ev) {
        line.requested_qty_str = ev.target.value || "";
        line.requested_qty = parseQtyExpression(line.requested_qty_str);
        this.state.lines = [...this.state.lines];
    }

    onLineNotesInput(line, ev) {
        line.notes = ev.target.value || "";
        this.state.lines = [...this.state.lines];
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

    updateLineUom(line, value) {
        const normalized = this._normalizeMany2oneValue(value);
        line.uom_id = normalized.id || false;
        line.uom_name = normalized.display_name || "";
        this.state.lines = [...this.state.lines];
    }

    async submitCurrentRequest() {
        if (this.state.submitting) {
            return;
        }
        if (!this.state.header.from_store_id) {
            this.notification.add("Requesting store is required.", {type: "warning"});
            return;
        }
        if (!this.state.header.to_store_id) {
            this.notification.add("Destination branch is required.", {type: "warning"});
            return;
        }
        if (!this.state.lines.length) {
            this.notification.add("Add at least one product.", {type: "warning"});
            return;
        }

        const lines = this.state.lines.map((line) => ({
            product_id: line.product_id,
            requested_qty: line.requested_qty || parseQtyExpression(line.requested_qty_str),
            uom_id: line.uom_id || false,
            notes: line.notes || "",
        }));
        if (lines.some((line) => !line.product_id || line.requested_qty <= 0)) {
            this.notification.add("Every line must have a product and requested quantity.", {type: "warning"});
            return;
        }

        this.state.submitting = true;
        try {
            const result = await this.orm.call("ab_transfer_request_pos_api", "pos_submit", [], {
                header: {
                    from_store_id: this.state.header.from_store_id,
                    to_store_id: this.state.header.to_store_id,
                    user_id: this.state.header.user_id || false,
                    notes: this.state.header.notes || "",
                },
                lines,
            });
            const name = result?.display_name || "Transfer request";
            this.notification.add(`${name} created.`, {type: "success"});
            this._resetRequest();
        } catch (err) {
            const message = err?.data?.message || err?.message || "Transfer request creation failed.";
            this.notification.add(message, {type: "danger"});
        } finally {
            this.state.submitting = false;
        }
    }

    openRequestList() {
        this.action.doAction("ab_transfer.ab_transfer_request_action");
    }

    closeWindow() {
        try {
            this.action.doAction({type: "ir.actions.act_window_close"});
        } finally {
            this.state.windowClosed = true;
        }
    }

    formatQty(value) {
        const parsed = parseFloat(value || 0);
        if (!Number.isFinite(parsed)) {
            return "0";
        }
        return parsed.toFixed(3).replace(/(?:\.0+|(\.\d*?)0+)$/, "$1");
    }
}

registry.category("actions").add("ab_transfer.request_pos", AbTransferRequestPosAction);
