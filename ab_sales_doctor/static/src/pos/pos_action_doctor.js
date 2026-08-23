/** @odoo-module **/

import {Component, useState} from "@odoo/owl";
import {Dialog} from "@web/core/dialog/dialog";
import {_t} from "@web/core/l10n/translation";
import {registry} from "@web/core/registry";
import {patch} from "@web/core/utils/patch";

const PosAction = registry.category("actions").get("ab_sales.pos");
const DOCTOR_CODE_PATTERN = /^[A-Za-z0-9]+$/;

class AbSalesDoctorCreateDialog extends Component {
    static template = "ab_sales_doctor.DoctorCreateDialog";
    static components = {Dialog};
    static props = {
        onSave: Function,
        close: Function,
    };

    setup() {
        this._t = _t;
        this.state = useState({
            name: "",
            code: "",
            phone: "",
            specialty: "",
            message: "",
            submitting: false,
        });
        this.updateField = this.updateField.bind(this);
        this.submit = this.submit.bind(this);
    }

    updateField(field, ev) {
        this.state[field] = ev.target.value || "";
    }

    validate() {
        const name = (this.state.name || "").trim();
        const code = (this.state.code || "").trim();
        const specialty = (this.state.specialty || "").trim();
        if (!name) {
            return _t("Doctor name is required.");
        }
        if (!code) {
            return _t("Doctor code is required.");
        }
        if (!DOCTOR_CODE_PATTERN.test(code)) {
            return _t("Doctor code must contain only English letters and digits.");
        }
        if (!specialty) {
            return _t("Doctor specialty is required.");
        }
        return "";
    }

    async submit() {
        if (this.state.submitting) {
            return;
        }
        const validationMessage = this.validate();
        if (validationMessage) {
            this.state.message = validationMessage;
            return;
        }
        this.state.submitting = true;
        this.state.message = "";
        try {
            await this.props.onSave({
                name: (this.state.name || "").trim(),
                code: (this.state.code || "").trim(),
                phone: this.state.phone,
                specialty: (this.state.specialty || "").trim(),
            });
            this.props.close();
        } catch (err) {
            const data = err?.data || err?.response?.data || {};
            const rpcArgs = data?.arguments;
            this.state.message = (
                (Array.isArray(rpcArgs) && rpcArgs[0])
                || data?.message
                || err?.message
                || _t("No connection available.")
            );
        } finally {
            this.state.submitting = false;
        }
    }
}

if (PosAction) {
    patch(PosAction.prototype, {
        setup() {
            super.setup(...arguments);
            this._t = _t;
            this.doctorValue = this.doctorValue.bind(this);
            this.doctorPlaceholder = this.doctorPlaceholder.bind(this);
            this.onDoctorPrescriptionToggle = this.onDoctorPrescriptionToggle.bind(this);
            this.onDoctorM2OUpdate = this.onDoctorM2OUpdate.bind(this);
            this.openDoctorCreateDialog = this.openDoctorCreateDialog.bind(this);
            this.onLineDoctorPrescriptionChange = this.onLineDoctorPrescriptionChange.bind(this);
            this._mergeDoctorPrescriptionProducts = this._mergeDoctorPrescriptionProducts.bind(this);
            this._mergeDoctorProductRows = this._mergeDoctorProductRows.bind(this);
            this._abSalesDoctorProductRequestId = 0;
        },

        _normalizeBill(bill) {
            const normalized = super._normalizeBill(...arguments);
            if (!normalized?.header) {
                return normalized;
            }
            normalized.header.is_doctor_prescription = !!normalized.header.is_doctor_prescription;
            normalized.header.doctor_id = normalized.header.doctor_id || null;
            normalized.header.doctor_name = normalized.header.doctor_name || "";
            for (const line of normalized.lines || []) {
                if (!Object.prototype.hasOwnProperty.call(line, "is_doctor_prescription_product")) {
                    line.is_doctor_prescription_product = false;
                } else {
                    line.is_doctor_prescription_product = !!line.is_doctor_prescription_product;
                }
            }
            return normalized;
        },

        createNewBill(storeId) {
            const result = super.createNewBill(...arguments);
            const bill = this.currentBill;
            if (bill?.header) {
                bill.header.is_doctor_prescription = !!bill.header.is_doctor_prescription;
                bill.header.doctor_id = bill.header.doctor_id || null;
                bill.header.doctor_name = bill.header.doctor_name || "";
                bill.updated_at = new Date().toISOString();
                this.persistCache();
            }
            return result;
        },

        doctorValue() {
            const bill = this.currentBill;
            if (!bill?.header?.doctor_id) {
                return false;
            }
            return {
                id: bill.header.doctor_id,
                display_name: bill.header.doctor_name || "",
            };
        },

        doctorPlaceholder() {
            return _t("Doctor...");
        },

        onDoctorPrescriptionToggle(ev) {
            const bill = this.currentBill;
            if (!bill?.header) {
                return;
            }
            const enabled = !!ev.target.checked;
            bill.header.is_doctor_prescription = enabled;
            if (!enabled) {
                bill.header.doctor_id = null;
                bill.header.doctor_name = "";
                for (const line of bill.lines || []) {
                    line.is_doctor_prescription_product = false;
                }
            }
            bill.updated_at = new Date().toISOString();
            this.persistCache();
            this.searchProducts((this.state.productQuery || "").trim());
        },

        onDoctorM2OUpdate(value) {
            const bill = this.currentBill;
            if (!bill?.header) {
                return;
            }
            if (value && value.id) {
                bill.header.doctor_id = value.id;
                bill.header.doctor_name = value.display_name || value.name || "";
            } else {
                bill.header.doctor_id = null;
                bill.header.doctor_name = "";
            }
            bill.updated_at = new Date().toISOString();
            this.persistCache();
            this.searchProducts((this.state.productQuery || "").trim());
        },

        openDoctorCreateDialog() {
            const bill = this.currentBill;
            if (!bill?.header?.is_doctor_prescription) {
                return;
            }
            this.dialog.add(AbSalesDoctorCreateDialog, {
                onSave: async (values) => {
                    const doctor = await this.orm.call(
                        "ab_sales_pos_api",
                        "pos_create_main_doctor",
                        [],
                        {values}
                    );
                    if (!doctor?.id) {
                        throw new Error(_t("Doctor was not replicated to this branch."));
                    }
                    bill.header.doctor_id = doctor.id;
                    bill.header.doctor_name = doctor.display_name || values.name || "";
                    bill.updated_at = new Date().toISOString();
                    this.persistCache();
                    this.notification.add(_t("Doctor added from main."), {type: "success"});
                    await this.searchProducts((this.state.productQuery || "").trim());
                },
            });
        },

        onLineDoctorPrescriptionChange(line, ev) {
            if (!line) {
                return;
            }
            line.is_doctor_prescription_product = !!ev.target.checked;
            const bill = this.currentBill;
            if (bill) {
                bill.updated_at = new Date().toISOString();
            }
            this.persistCache();
        },

        addProduct(product, qty = 1) {
            const bill = this.currentBill;
            const productId = parseInt(product?.id || 0, 10) || 0;
            const existingLine = bill && productId
                ? (bill.lines || []).find((line) => parseInt(line?.product_id || 0, 10) === productId)
                : null;
            const line = super.addProduct(...arguments);
            if (line && !existingLine) {
                line.is_doctor_prescription_product = !!(
                    bill?.header?.is_doctor_prescription
                    && product?.is_doctor_prescription_product
                );
                this.persistCache();
            } else if (line && !Object.prototype.hasOwnProperty.call(line, "is_doctor_prescription_product")) {
                line.is_doctor_prescription_product = false;
                this.persistCache();
            }
            return line;
        },

        _buildSubmitHeader(bill) {
            const header = super._buildSubmitHeader(...arguments);
            header.is_doctor_prescription = !!bill?.header?.is_doctor_prescription;
            header.doctor_id = bill?.header?.doctor_id || false;
            return header;
        },

        async submitCurrentBill() {
            const bill = this.currentBill;
            if (
                bill?.header?.is_doctor_prescription
                && !bill.header.doctor_id
            ) {
                this.notification.add(_t("Select a doctor for this prescription bill."), {type: "danger"});
                return;
            }
            if (
                bill?.header?.is_doctor_prescription
                && !(bill.lines || []).some((line) => line.is_doctor_prescription_product)
            ) {
                this.notification.add(_t("Mark at least one line as a prescription product."), {type: "danger"});
                return;
            }
            return super.submitCurrentBill(...arguments);
        },

        async _submitBillInternal(bill) {
            if (!bill) {
                return super._submitBillInternal(...arguments);
            }
            const originalOrm = this.orm;
            const wrappedOrm = Object.create(originalOrm);
            wrappedOrm.call = (model, method, args = [], kwargs = {}) => {
                let nextKwargs = kwargs || {};
                if (model === "ab_sales_pos_api" && method === "pos_submit") {
                    const sourceLines = Array.isArray(bill.lines) ? bill.lines : [];
                    const flagsByProduct = new Map();
                    for (const line of sourceLines) {
                        const productId = parseInt(line?.product_id || 0, 10) || 0;
                        if (productId) {
                            flagsByProduct.set(productId, !!line.is_doctor_prescription_product);
                        }
                    }
                    nextKwargs = {...nextKwargs};
                    if (Array.isArray(nextKwargs.lines)) {
                        nextKwargs.lines = nextKwargs.lines.map((line) => {
                            const productId = parseInt(line?.product_id || 0, 10) || 0;
                            return {
                                ...line,
                                is_doctor_prescription_product: !!flagsByProduct.get(productId),
                            };
                        });
                    }
                }
                return originalOrm.call.call(originalOrm, model, method, args, nextKwargs);
            };

            this.orm = wrappedOrm;
            try {
                return await super._submitBillInternal(...arguments);
            } finally {
                this.orm = originalOrm;
            }
        },

        async searchProducts(query) {
            await super.searchProducts(...arguments);
            await this._mergeDoctorPrescriptionProducts(String(query || "").trim());
        },

        async _mergeDoctorPrescriptionProducts(query) {
            const bill = this.currentBill;
            const doctorId = parseInt(bill?.header?.doctor_id || 0, 10) || 0;
            if (!bill?.header?.is_doctor_prescription || !doctorId) {
                return;
            }
            const requestId = ++this._abSalesDoctorProductRequestId;
            const storeId = bill.header.store_id || null;
            try {
                const doctorRows = await this.orm.call(
                    "ab_sales_ui_api",
                    "doctor_prescription_products",
                    [],
                    {
                        doctor_id: doctorId,
                        query,
                        limit: 24,
                        store_id: storeId,
                    }
                );
                if (requestId !== this._abSalesDoctorProductRequestId) {
                    return;
                }
                const currentBill = this.currentBill;
                if (
                    !currentBill
                    || currentBill.id !== bill.id
                    || !currentBill.header.is_doctor_prescription
                    || parseInt(currentBill.header.doctor_id || 0, 10) !== doctorId
                    || (this.state.productQuery || "").trim() !== query
                ) {
                    return;
                }
                this.state.productResults = this._mergeDoctorProductRows(
                    Array.isArray(doctorRows) ? doctorRows : [],
                    this.state.productResults || [],
                    24
                );
                this.state.selectionIndex = -1;
                this.schedulePosBalanceRefresh(this.state.productResults, storeId);
            } catch (err) {
                this.notification.add(err?.message || _t("Failed to load doctor products."), {type: "warning"});
            }
        },

        _mergeDoctorProductRows(doctorRows, existingRows, limit = 24) {
            const merged = [];
            const seen = new Set();
            const pushRow = (row, isDoctorRow = false) => {
                const productId = parseInt(row?.id || 0, 10) || 0;
                if (!productId || seen.has(productId) || merged.length >= limit) {
                    return;
                }
                seen.add(productId);
                merged.push({
                    ...row,
                    is_doctor_prescription_product: isDoctorRow || !!row.is_doctor_prescription_product,
                    is_pinned: isDoctorRow ? true : !!row.is_pinned,
                    rank_source: isDoctorRow ? "doctor_prescription" : (row.rank_source || ""),
                });
            };

            for (const row of doctorRows || []) {
                pushRow(row, true);
            }
            for (const row of existingRows || []) {
                pushRow(row, false);
            }
            return merged;
        },
    });
}
