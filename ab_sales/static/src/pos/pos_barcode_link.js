/** @odoo-module **/

import {Component, onMounted, useRef, useState} from "@odoo/owl";
import {Dialog} from "@web/core/dialog/dialog";
import {ABMany2many} from "@ab_widgets/ab_many2many";
import {useService} from "@web/core/utils/hooks";

export class AbSalesPosBarcodeLinkDialog extends Component {
    static template = "ab_sales.PosBarcodeLinkDialog";
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
        if (this.props.close) {
            this.props.close();
        }
    }

    async _loadLinkedProducts() {
        const barcode = (this.state.barcode || "").trim();
        if (!barcode) {
            this.state.selected = [];
            return;
        }
        this.state.loadingLinks = true;
        try {
            const products = await this.orm.call("ab_sales_pos_api", "pos_barcode_temp_products", [], {barcode});
            this.state.selected = Array.isArray(products) ? products : [];
        } catch {
            this.state.selected = [];
        } finally {
            this.state.loadingLinks = false;
        }
    }

    cancel() {
        if (this.props.close) {
            this.props.close();
        }
    }
}
