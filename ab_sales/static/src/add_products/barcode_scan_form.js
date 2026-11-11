/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";
import { useChildRef, useService } from "@web/core/utils/hooks";
import { Component, onMounted, useExternalListener, useRef, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { FormViewDialog } from "@web/views/view_dialogs/form_view_dialog";

const BARCODE_START_KEY = "F12";
const BARCODE_END_KEY = "Enter";
const BARCODE_DIALOG_WIDTH = "70vw";

const applyDialogWidth = (modalEl) => {
    const dialogEl = modalEl?.querySelector?.(".modal-dialog");
    if (!dialogEl) {
        return;
    }
    dialogEl.style.width = BARCODE_DIALOG_WIDTH;
    dialogEl.style.maxWidth = BARCODE_DIALOG_WIDTH;
};

class AbSalesBarcodeSelectDialog extends Component {
    static template = "ab_sales.BarcodeSelectDialog";
    static components = { Dialog };
    static props = {
        products: Array,
        onSelect: Function,
        close: Function,
    };

    setup() {
        this.modalRef = useChildRef();
        onMounted(() => {
            applyDialogWidth(this.modalRef.el);
        });
    }

    selectProduct(product) {
        if (this.props.onSelect) {
            this.props.onSelect(product);
        }
        if (this.props.close) {
            this.props.close();
        }
    }
}

class AbSalesBarcodeQtyDialog extends Component {
    static template = "ab_sales.BarcodeQtyDialog";
    static components = { Dialog };
    static props = {
        qty: Number,
        onConfirm: Function,
        onClose: Function,
        product: Object,
        close: Function,
    };

    setup() {
        this.dialog = useService("dialog");
        this.state = useState({
            value: this.props.qty ? String(this.props.qty) : "1",
        });
        this.inputRef = useRef("qtyInput");
        this.modalRef = useChildRef();
        this.formatPrice = this.formatPrice.bind(this);
        this.formatQty = this.formatQty.bind(this);
        this.productLabel = this.productLabel.bind(this);
        this.openStoresBalance = this.openStoresBalance.bind(this);
        onMounted(() => {
            applyDialogWidth(this.modalRef.el);
            const el = this.inputRef.el;
            if (el) {
                el.focus();
                el.select();
            }
        });
    }

    confirm() {
        const parsed = parseFloat(this.state.value);
        if (Number.isFinite(parsed) && parsed > 0 && this.props.onConfirm) {
            this.props.onConfirm(parsed);
        }
        if (this.props.close) {
            this.props.close();
        }
    }

    onInputKeydown(ev) {
        if (ev.key === "Enter") {
            ev.preventDefault();
            this.confirm();
        }
    }

    cancel() {
        if (this.props.onClose) {
            this.props.onClose();
        }
        if (this.props.close) {
            this.props.close();
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
        return fixed.replace(/(?:\.0+|(\.\d*?)0+)$/, "$1");
    }

    productLabel(product) {
        return product?.name || product?.product_card_name || `${product?.code || ""}`.trim() || `#${product?.id}`;
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
}

patch(FormController.prototype, {
    setup() {
        super.setup(...arguments);
        this.abSalesBarcodeNotification = useService("notification");
        this.abSalesBarcodeOrm = useService("orm");
        this.abSalesBarcodeDialog = useService("dialog");
        this._abSalesBarcodeActive = false;
        this._abSalesBarcodeBuffer = "";
        this._abSalesQtyDialogClose = null;
        useExternalListener(
            window,
            "keydown",
            (ev) => {
                this._abSalesBarcodeOnKeydown(ev);
            },
            { capture: true }
        );
    },

    _abSalesBarcodeResetBuffer() {
        this._abSalesBarcodeActive = false;
        this._abSalesBarcodeBuffer = "";
    },

    _abSalesBarcodeOnKeydown(ev) {
        if (this.env?.config?.viewType === "form" && ev.key === "F12") {
            ev.preventDefault();
            ev.stopPropagation();
        }
        if (this.props.resModel !== "ab_sales_header") {
            return;
        }
        if (ev.key === BARCODE_START_KEY) {
            ev.preventDefault();
            ev.stopPropagation();
            ev.stopImmediatePropagation();
            this._abSalesBarcodeActive = true;
            this._abSalesBarcodeBuffer = "";
            return;
        }
        if (!this._abSalesBarcodeActive) {
            return;
        }
        ev.preventDefault();
        ev.stopPropagation();
        ev.stopImmediatePropagation();
        if (ev.key === BARCODE_END_KEY) {
            const barcode = (this._abSalesBarcodeBuffer || "").trim();
            this._abSalesBarcodeResetBuffer();
            if (barcode) {
                this._abSalesBarcodeHandleScan(barcode);
            }
            return;
        }
        if (ev.key === "Escape") {
            this._abSalesBarcodeResetBuffer();
            return;
        }
        if (ev.key && ev.key.length === 1) {
            this._abSalesBarcodeBuffer += ev.key;
            return;
        }
    },

    async _abSalesBarcodeHandleScan(barcode) {
        try {
            if (document.body.classList.contains("modal-open") && !this._abSalesQtyDialogClose) {
                return;
            }
            if (this._abSalesQtyDialogClose) {
                this._abSalesQtyDialogClose();
                this._abSalesQtyDialogClose = null;
            }
            const status = this.model?.root?.data?.status;
            if (status && status !== "prepending") {
                this.abSalesBarcodeNotification.add("Invoice is not editable.", { type: "warning" });
                return;
            }

            const headerId = await this._abSalesBarcodeEnsureSavedHeader();
            if (!headerId) {
                this.abSalesBarcodeNotification.add("Please save the invoice before scanning.", { type: "warning" });
                return;
            }

            const products = await this._abSalesBarcodeFetchProducts(barcode);
            if (!products.length) {
                this.abSalesBarcodeNotification.add(`No product found for barcode ${barcode}.`, { type: "warning" });
                return;
            }
            if (products.length === 1) {
                await this._abSalesBarcodeApplyProduct(products[0].id);
                await this._abSalesBarcodeEnsureEditMode();
                this._abSalesBarcodeEnsureLinesTabActive();
                await this._abSalesBarcodePromptQty(products[0]);
                return;
            }

            this.abSalesBarcodeDialog.add(AbSalesBarcodeSelectDialog, {
                products,
                onSelect: async (product) => {
                    await this._abSalesBarcodeApplyProduct(product.id);
                    await this._abSalesBarcodeEnsureEditMode();
                    this._abSalesBarcodeEnsureLinesTabActive();
                    await this._abSalesBarcodePromptQty(product);
                },
            });
        } catch (err) {
            this.abSalesBarcodeNotification.add(err?.message || "Barcode scan failed.", { type: "danger" });
        }
    },

    async _abSalesBarcodeEnsureSavedHeader() {
        const root = this.model?.root;
        const needsSave = !root?.resId || root?.isDirty;
        if (!needsSave) {
            return root?.resId || null;
        }
        const saved = await this.saveButtonClicked({});
        if (!saved) {
            return null;
        }
        return this.model?.root?.resId || null;
    },

    async _abSalesBarcodeFetchProducts(barcode) {
        const barcodeRows = await this.abSalesBarcodeOrm.searchRead(
            "ab_product_barcode",
            [["name", "=", barcode]],
            ["product_ids"]
        );
        const productIds = new Set();
        for (const row of barcodeRows || []) {
            for (const pid of row.product_ids || []) {
                productIds.add(pid);
            }
        }
        if (!productIds.size) {
            return [];
        }
        const products = await this.abSalesBarcodeOrm.searchRead(
            "ab_product",
            [["id", "in", Array.from(productIds)]],
            ["name", "product_card_name", "code", "eplus_serial", "default_price"]
        );
        const balances = await this._abSalesBarcodeFetchBalances(products);
        return (products || []).map((product) => {
            const code = product.code ? `${product.code} ` : "";
            const name = product.name || product.product_card_name || "";
            const label = `${code}${name}`.trim() || `#${product.id}`;
            const serial = this._abSalesBarcodeParseInt(product.eplus_serial);
            const bal = balances.total.get(serial) || 0.0;
            const pos = balances.pos.get(serial) || 0.0;
            return { ...product, label, balance: bal, pos_balance: pos };
        });
    },

    async _abSalesBarcodeFetchBalances(products) {
        const serials = [];
        for (const product of products || []) {
            const serial = this._abSalesBarcodeParseInt(product.eplus_serial);
            if (serial) {
                serials.push(serial);
            }
        }
        if (!serials.length) {
            return { total: new Map(), pos: new Map() };
        }
        const storeId = this._abSalesBarcodeGetStoreId();
        const totalRows = await this.abSalesBarcodeOrm.searchRead(
            "ab_sales_inventory",
            [
                ["store_id", "=", false],
                ["product_eplus_serial", "in", serials],
            ],
            ["product_eplus_serial", "balance"]
        );
        const posRows = storeId
            ? await this.abSalesBarcodeOrm.searchRead(
                "ab_sales_inventory",
                [
                    ["store_id", "=", storeId],
                    ["product_eplus_serial", "in", serials],
                ],
                ["product_eplus_serial", "balance"]
            )
            : [];

        const total = new Map();
        for (const row of totalRows || []) {
            const serial = this._abSalesBarcodeParseInt(row.product_eplus_serial);
            if (serial) {
                total.set(serial, parseFloat(row.balance || 0.0));
            }
        }
        const pos = new Map();
        for (const row of posRows || []) {
            const serial = this._abSalesBarcodeParseInt(row.product_eplus_serial);
            if (serial) {
                pos.set(serial, parseFloat(row.balance || 0.0));
            }
        }
        return { total, pos };
    },

    _abSalesBarcodeParseInt(value) {
        const parsed = parseInt(value, 10);
        return Number.isFinite(parsed) ? parsed : 0;
    },

    _abSalesBarcodeGetStoreId() {
        const storeValue = this.model?.root?.data?.store_id;
        if (Array.isArray(storeValue)) {
            return storeValue[0] || null;
        }
        if (typeof storeValue === "number") {
            return storeValue;
        }
        return null;
    },

    async _abSalesBarcodeApplyProduct(productId) {
        const headerId = this.model?.root?.resId;
        if (!headerId || !productId) {
            return;
        }
        await this.abSalesBarcodeOrm.call("ab_sales_ui_api", "apply_products", [], {
            header_id: headerId,
            items: [{ product_id: productId, qty: 1 }],
        });
        await this.model.load();
    },

    async _abSalesBarcodePromptQty(product) {
        const line = await this._abSalesBarcodeGetLineForProduct(product?.id);
        if (!line) {
            return;
        }
        const currentQty = this._abSalesBarcodeParseQty(line.qty_str, line.qty);
        this._abSalesQtyDialogClose = this.abSalesBarcodeDialog.add(AbSalesBarcodeQtyDialog, {
            qty: currentQty,
            product: product || null,
            onConfirm: async (newQty) => {
                await this._abSalesBarcodeUpdateLineQty(line.id, newQty);
                await this._abSalesBarcodeEnsureEditMode();
                this._abSalesBarcodeEnsureLinesTabActive();
                await this._abSalesBarcodeFocusQty(line.id);
                this._abSalesQtyDialogClose = null;
            },
            onClose: async () => {
                await this._abSalesBarcodeEnsureEditMode();
                this._abSalesBarcodeEnsureLinesTabActive();
                await this._abSalesBarcodeFocusQty(line.id);
                this._abSalesQtyDialogClose = null;
            },
        });
    },

    _abSalesBarcodeParseQty(primary, fallback) {
        const raw = primary ?? fallback ?? 1;
        const parsed = parseFloat(raw);
        return Number.isFinite(parsed) && parsed > 0 ? parsed : 1;
    },

    async _abSalesBarcodeUpdateLineQty(lineId, qty) {
        if (!lineId) {
            return;
        }
        const qtyValue = this._abSalesBarcodeParseQty(qty, 1);
        await this.abSalesBarcodeOrm.write("ab_sales_line", [lineId], {
            qty_str: String(qtyValue),
        });
        await this.model.load();
    },

    async _abSalesBarcodeGetLineForProduct(productId) {
        const headerId = this.model?.root?.resId;
        if (!headerId || !productId) {
            return null;
        }
        const rows = await this.abSalesBarcodeOrm.searchRead(
            "ab_sales_line",
            [
                ["header_id", "=", headerId],
                ["product_id", "=", productId],
            ],
            ["id", "qty_str", "qty"],
            { limit: 1, order: "id desc" }
        );
        return rows?.[0] || null;
    },

    async _abSalesBarcodeEnsureEditMode() {
        const root = this.model?.root;
        if (!root) {
            return;
        }
        if (root.mode === "edit" || root.isEditing) {
            return;
        }
        if (typeof root.switchMode === "function") {
            await root.switchMode("edit");
            return;
        }
        if (typeof this.editButtonClicked === "function") {
            await this.editButtonClicked();
        }
    },

    _abSalesBarcodeEnsureLinesTabActive() {
        const root = this.el;
        if (!root) {
            return;
        }
        const x2many =
            root.querySelector('.o_field_x2many[name="line_ids"]') ||
            root.querySelector('.o_field_x2many[data-name="line_ids"]') ||
            root.querySelector('[name="line_ids"].o_field_x2many') ||
            root.querySelector('[data-name="line_ids"].o_field_x2many');
        const page = x2many?.closest?.(".tab-pane");
        if (!page) {
            return;
        }
        if (page.classList.contains("active") || page.classList.contains("show")) {
            return;
        }
        const pageId = page.getAttribute("id");
        if (!pageId) {
            return;
        }
        const tab =
            root.querySelector(`a[data-bs-toggle="tab"][href="#${pageId}"]`) ||
            root.querySelector(`a[data-toggle="tab"][href="#${pageId}"]`) ||
            root.querySelector(`a[href="#${pageId}"]`);
        tab?.click?.();
    },

    async _abSalesBarcodeFocusQty(lineId) {
        if (!lineId) {
            return;
        }
        const tryFocus = (attempts) => {
            const root = this.el;
            if (!root) {
                return;
            }
            const row =
                root.querySelector(`tr.o_data_row[data-res-id="${lineId}"]`) ||
                root.querySelector(`tr.o_data_row[data-id="${lineId}"]`) ||
                root.querySelector(`[data-res-id="${lineId}"]`) ||
                root.querySelector(`[data-id="${lineId}"]`);
            if (!row) {
                if (attempts > 0) {
                    setTimeout(() => tryFocus(attempts - 1), 150);
                }
                return;
            }
            row.scrollIntoView?.({ block: "nearest" });
            const cell =
                row.querySelector('td[data-name="qty_str"]') ||
                row.querySelector('[data-name="qty_str"]') ||
                row.querySelector('[name="qty_str"]');
            if (!cell) {
                return;
            }
            let input = cell.querySelector("input,textarea");
            if (!input) {
                cell.dispatchEvent(new MouseEvent("click", { bubbles: true }));
                input =
                    cell.querySelector("input,textarea") ||
                    row.querySelector('[data-name="qty_str"] input, [data-name="qty_str"] textarea') ||
                    row.querySelector('[name="qty_str"] input, [name="qty_str"] textarea');
            }
            input?.focus?.();
            input?.select?.();
        };
        setTimeout(() => tryFocus(15), 0);
    },
});
