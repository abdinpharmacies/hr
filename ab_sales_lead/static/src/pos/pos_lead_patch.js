/** @odoo-module **/

import {Component, useState} from "@odoo/owl";
import {Dialog} from "@web/core/dialog/dialog";
import {registry} from "@web/core/registry";
import {patch} from "@web/core/utils/patch";
import {useService} from "@web/core/utils/hooks";

class AbSalesLeadPosDialog extends Component {
    static template = "ab_sales_lead.PosLeadDialog";
    static components = {Dialog};
    static props = {
        product: Object,
        bill: {type: Object, optional: true},
        productQuery: {type: String, optional: true},
        productLabel: Function,
        formatQty: Function,
        onSaved: {type: Function, optional: true},
        close: Function,
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        const header = this.props.bill?.header || {};
        this.state = useState({
            leadType: "lost_sales",
            quantity: "1",
            customerName: header.bill_customer_name || header.customer_name || header.new_customer_name || "",
            customerPhone:
                header.bill_customer_phone ||
                header.customer_phone ||
                header.customer_mobile ||
                header.new_customer_phone ||
                "",
            customerAddress:
                header.bill_customer_address ||
                header.invoice_address ||
                header.customer_address ||
                header.new_customer_address ||
                "",
            lostReason: "not_available",
            neededDate: "",
            contactPreference: "phone",
            notes: "",
            reportLoading: false,
            reportLoaded: false,
            reportRows: [],
            reportTotals: {},
            reportMessage: "",
            reportStoreFilter: "",
            errors: {},
            saving: false,
        });
        this.setLeadType = this.setLeadType.bind(this);
        this.onFieldInput = this.onFieldInput.bind(this);
        this.loadItemReport = this.loadItemReport.bind(this);
        this.save = this.save.bind(this);
        this.cancel = this.cancel.bind(this);
    }

    setLeadType(type) {
        this.state.leadType = type;
        this.state.errors = {};
        if (type === "item_report") {
            this.loadItemReport();
        }
    }

    onFieldInput(field, value) {
        this.state[field] = value;
        if (this.state.errors[field]) {
            this.state.errors = {...this.state.errors, [field]: false};
        }
    }

    productTitle() {
        return this.props.productLabel(this.props.product);
    }

    reportRows() {
        const filter = (this.state.reportStoreFilter || "").trim().toLowerCase();
        const rows = this.state.reportRows || [];
        if (!filter) {
            return rows;
        }
        return rows.filter((row) => {
            const storeName = (row.store_name || "").toLowerCase();
            const storeCode = (row.store_code || "").toLowerCase();
            return storeName.includes(filter) || storeCode.includes(filter);
        });
    }

    async loadItemReport() {
        if (this.state.reportLoading || this.state.reportLoaded) {
            return;
        }
        const productId = this.props.product?.id;
        if (!productId) {
            return;
        }
        this.state.reportLoading = true;
        this.state.reportMessage = "";
        try {
            const result = await this.orm.call("ab_sales_lead", "pos_item_report", [], {
                product_id: productId,
            });
            this.state.reportRows = result?.rows || [];
            this.state.reportTotals = {
                total_balance: result?.total_balance || 0,
                total_last_30_days_sales: result?.total_last_30_days_sales || 0,
                date_from: result?.date_from || "",
                date_to: result?.date_to || "",
            };
            this.state.reportMessage = result?.message || "";
            this.state.reportLoaded = true;
        } catch (err) {
            this.state.reportMessage = err?.message || "Item report failed to load.";
            this.notification.add(this.state.reportMessage, {type: "danger"});
        } finally {
            this.state.reportLoading = false;
        }
    }

    _validate() {
        const errors = {};
        const quantity = parseFloat(this.state.quantity || 0);
        if (!Number.isFinite(quantity) || quantity <= 0) {
            errors.quantity = "Quantity is required.";
        }
        if (this.state.leadType === "special_order" && !(this.state.customerPhone || "").trim()) {
            errors.customerPhone = "Customer phone is required.";
        }
        if (
            this.state.leadType === "lost_sales" &&
            !(this.state.lostReason || "").trim() &&
            !(this.state.notes || "").trim()
        ) {
            errors.lostReason = "Select a lost reason or add a note.";
        }
        this.state.errors = errors;
        return !Object.values(errors).some(Boolean);
    }

    _payload() {
        const product = this.props.product || {};
        const header = this.props.bill?.header || {};
        return {
            lead_type: this.state.leadType,
            product_id: product.id,
            product_name: this.productTitle(),
            product_code: product.code || "",
            store_id: header.store_id || false,
            customer_id: header.customer_id || false,
            customer_name: (this.state.customerName || "").trim(),
            customer_phone: (this.state.customerPhone || "").trim(),
            customer_address: (this.state.customerAddress || "").trim(),
            quantity: parseFloat(this.state.quantity || 0) || 0,
            default_price: parseFloat(product.default_price || 0) || 0,
            total_balance: parseFloat(product.balance || 0) || 0,
            pos_balance: parseFloat(product.pos_balance || 0) || 0,
            pos_search_query: this.props.productQuery || "",
            pos_client_token: header.pos_client_token || "",
            lost_reason: this.state.leadType === "lost_sales" ? this.state.lostReason || false : false,
            needed_date: this.state.leadType === "special_order" ? this.state.neededDate || false : false,
            contact_preference: this.state.contactPreference || "phone",
            notes: (this.state.notes || "").trim(),
        };
    }

    async save() {
        if (this.state.saving || !this._validate()) {
            return;
        }
        this.state.saving = true;
        try {
            const result = await this.orm.call("ab_sales_lead", "pos_create_lead", [], {
                payload: this._payload(),
            });
            this.notification.add(result?.message || "Sales lead saved.", {type: "success"});
            if (this.props.onSaved) {
                this.props.onSaved(result);
            }
            this.props.close();
        } catch (err) {
            this.notification.add(err?.message || "Failed to save sales lead.", {type: "danger"});
        } finally {
            this.state.saving = false;
        }
    }

    cancel() {
        this.props.close();
    }
}

const PosAction = registry.category("actions").get("ab_sales.pos");

if (PosAction) {
    patch(PosAction.prototype, {
        setup() {
            super.setup(...arguments);
            this.openSalesLeadDialog = this.openSalesLeadDialog.bind(this);
        },

        openSalesLeadDialog(product) {
            if (!product?.id) {
                return;
            }
            this.dialog.add(AbSalesLeadPosDialog, {
                product,
                bill: this.currentBill,
                productQuery: this.state.productQuery || "",
                productLabel: this.productLabel,
                formatQty: this.formatQty,
            });
        },
    });
}
