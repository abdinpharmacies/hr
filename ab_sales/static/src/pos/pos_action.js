/** @odoo-module **/

import {registry} from "@web/core/registry";
import {Component, onMounted, onWillStart, onWillUnmount, useExternalListener, useRef, useState} from "@odoo/owl";
import {Dialog} from "@web/core/dialog/dialog";
import {useService} from "@web/core/utils/hooks";
import {FormViewDialog} from "@web/views/view_dialogs/form_view_dialog";
import {Many2One} from "@web/views/fields/many2one/many2one";
import {session} from "@web/session";
import {ABMany2one} from "@ab_widgets/ab_many2one";
import {bindPrinterActions, printerStateDefaults} from "./pos_printer";
import {AbSalesPosBarcodeLinkDialog} from "./pos_barcode_link";

const CACHE_PREFIX = "ab_sales_pos_cache_v1";
const DEFAULT_QTY = "1";
const SAFE_QTY_RE = /^[0-9+\-*/().\s]+$/;
const MIN_WINDOW_WIDTH = 720;
const MIN_WINDOW_HEIGHT = 520;
const POS_SCALE_BREAKPOINT = 1000;
const POS_SCALE_VALUE = 0.8;
const BARCODE_START_KEY = "F12";
const BARCODE_END_KEY = "Enter";
const POS_UI_SETTINGS_PREFIX = "ab_sales_pos_ui_settings_v1";
const POS_PRODUCT_COL_DEFAULT = 30;
const POS_PRODUCT_COL_MIN = 20;
const POS_PRODUCT_COL_MAX = 80;

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

const _uuidv4 = () => {
    if (typeof crypto !== "undefined") {
        if (typeof crypto.randomUUID === "function") {
            return crypto.randomUUID();
        }
        if (typeof crypto.getRandomValues === "function") {
            const bytes = new Uint8Array(16);
            crypto.getRandomValues(bytes);
            bytes[6] = (bytes[6] & 0x0f) | 0x40;
            bytes[8] = (bytes[8] & 0x3f) | 0x80;
            const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, "0"));
            return `${hex[0]}${hex[1]}${hex[2]}${hex[3]}-${hex[4]}${hex[5]}-${hex[6]}${hex[7]}-${hex[8]}${hex[9]}-${hex[10]}${hex[11]}${hex[12]}${hex[13]}${hex[14]}${hex[15]}`;
        }
    }
    const rand = () => Math.floor((1 + Math.random()) * 0x10000).toString(16).slice(1);
    return `${rand()}${rand()}-${rand()}-${rand()}-${rand()}-${rand()}${rand()}${rand()}`;
};

const generatePosToken = (userId, storeId) => {
    const uid = Number.isFinite(userId) ? userId : parseInt(userId || 0, 10) || 0;
    const sid = Number.isFinite(storeId) ? storeId : parseInt(storeId || 0, 10) || 0;
    return `pos_token_${uid}_${sid}_${_uuidv4()}`;
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



class AbSalesPosStoreDialog extends Component {
    static template = "ab_sales.PosStoreDialog";
    static components = {Dialog, Many2One};
    static props = {
        stores: Array,
        defaultStoreCode: {type: String, optional: true},
        domain: {type: Array, optional: true},
        onSelect: Function,
        close: Function,
    };

    setup() {
        this.state = useState({store: false});
        this.onStoreUpdate = this.onStoreUpdate.bind(this);
        const defaultCode = (this.props.defaultStoreCode || "").trim();
        if (defaultCode) {
            const store = (this.props.stores || []).find((row) => row.code === defaultCode);
            if (store) {
                this.state.store = {
                    id: store.id,
                    display_name: store.name || store.code || "",
                };
            }
        }
        this.storeDomain = this.storeDomain.bind(this);
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
        const storeId = this.state.store?.id;
        if (Number.isFinite(storeId) && this.props.onSelect) {
            this.props.onSelect(parseInt(storeId, 10));
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

class AbSalesPosSubmitDialog extends Component {
    static template = "ab_sales.PosSubmitDialog";
    static components = {Dialog, Many2One};
    static props = {
        bill: Object,
        preferredBillName: {type: String, optional: true},
        preferredBillAddress: {type: String, optional: true},
        onSubmit: Function,
        onDraft: {type: Function, optional: true},
        onCustomerApply: {type: Function, optional: true},
        close: Function,
    };

    setup() {
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        const header = this.props.bill?.header || {};
        const preferredBillName = (this.props.preferredBillName || "").trim();
        const preferredBillAddress = (this.props.preferredBillAddress || "").trim();
        const billCustomerName = preferredBillName || header.bill_customer_name || header.customer_name || "";
        const billCustomerPhone =
            header.bill_customer_phone || header.customer_phone || header.customer_mobile || "";
        const billCustomerAddress =
            preferredBillAddress || header.bill_customer_address || header.invoice_address || header.customer_address || "";
        const employeeId = parseInt(header.employee_id || header.eplus_employee_id || 0, 10);
        const employeeName = (header.employee_name || header.eplus_employee_name || "").trim();
        this.state = useState({
            invoice_address: billCustomerAddress || "",
            new_customer_name: header.new_customer_name || "",
            new_customer_phone: header.new_customer_phone || "",
            new_customer_address: header.new_customer_address || "",
            bill_customer_name: billCustomerName,
            bill_customer_phone: billCustomerPhone,
            bill_customer_address: billCustomerAddress,
            customer_insurance_name: header.customer_insurance_name || "",
            customer_insurance_number: header.customer_insurance_number || "",
            description: header.description || "",
            eplus_employee: Number.isFinite(employeeId) && employeeId > 0
                ? {id: employeeId, display_name: employeeName || ""}
                : false,
            errors: {},
            message: "",
            submitting: false,
            hasCustomer: !!header.customer_id,
        });
        this.descriptionRef = useRef("billDescription");
        this.onBillCustomerNameInput = this.onBillCustomerNameInput.bind(this);
        this.onBillCustomerPhoneInput = this.onBillCustomerPhoneInput.bind(this);
        this.onBillCustomerAddressInput = this.onBillCustomerAddressInput.bind(this);
        this.onNewCustomerNameInput = this.onNewCustomerNameInput.bind(this);
        this.onNewCustomerPhoneInput = this.onNewCustomerPhoneInput.bind(this);
        this.onNewCustomerAddressInput = this.onNewCustomerAddressInput.bind(this);
        this.openCustomerLookup = this.openCustomerLookup.bind(this);
        this.onInsuranceNameInput = this.onInsuranceNameInput.bind(this);
        this.onInsuranceNumberInput = this.onInsuranceNumberInput.bind(this);
        this.onDescriptionInput = this.onDescriptionInput.bind(this);
        this.employeeDomain = this.employeeDomain.bind(this);
        this.onEmployeeUpdate = this.onEmployeeUpdate.bind(this);
        this.submit = this.submit.bind(this);
        this._onKeydown = this._onKeydown.bind(this);

        useExternalListener(window, "keydown", this._onKeydown, {capture: true});
        onWillStart(async () => {
            if (this.state.eplus_employee?.id) {
                return;
            }
            try {
                const employee = await this.orm.call(
                    "ab_sales_pos_api",
                    "pos_default_employee",
                    [],
                    {}
                );
                if (employee?.id) {
                    this.state.eplus_employee = {
                        id: employee.id,
                        display_name: employee.name || employee.display_name || "",
                    };
                }
            } catch {
                this.state.eplus_employee = false;
            }
        });

        onMounted(() => {
            const target = this.descriptionRef.el;
            if (target) {
                target.focus();
                if (typeof target.select === "function") {
                    target.select();
                }
            }
        });
    }

    _onKeydown(ev) {
        if (ev.key !== "F10") {
            return;
        }
        ev.preventDefault();
        ev.stopPropagation();
        this.submit();
    }

    onBillCustomerNameInput(ev) {
        this.state.bill_customer_name = ev.target.value || "";
    }

    onBillCustomerPhoneInput(ev) {
        this.state.bill_customer_phone = ev.target.value || "";
    }

    onBillCustomerAddressInput(ev) {
        const value = ev.target.value || "";
        this.state.bill_customer_address = value;
        this.state.invoice_address = value;
    }

    onNewCustomerNameInput(ev) {
        this.state.new_customer_name = ev.target.value || "";
    }

    onNewCustomerPhoneInput(ev) {
        this.state.new_customer_phone = ev.target.value || "";
    }

    onNewCustomerAddressInput(ev) {
        this.state.new_customer_address = ev.target.value || "";
    }

    openCustomerLookup() {
        this.dialog.add(AbSalesPosCustomerLookupDialog, {
            defaultPhone: this.state.new_customer_phone,
            defaultName: this.state.new_customer_name,
            defaultAddress: this.state.new_customer_address,
            onSelect: (customer) => {
                if (!customer) {
                    return;
                }
                if (this.props.onCustomerApply) {
                    this.props.onCustomerApply(customer);
                }
                this.state.bill_customer_name = customer.name || "";
                this.state.bill_customer_phone = customer.work_phone || customer.mobile_phone || "";
                this.state.bill_customer_address = customer.address || "";
                this.state.invoice_address = this.state.bill_customer_address || "";
                this.state.hasCustomer = true;
                this.state.new_customer_name = "";
                this.state.new_customer_phone = "";
                this.state.new_customer_address = "";
                this.state.message = "Customer selected.";
            },
        });
    }

    onInsuranceNameInput(ev) {
        this.state.customer_insurance_name = ev.target.value || "";
    }

    onInsuranceNumberInput(ev) {
        this.state.customer_insurance_number = ev.target.value || "";
    }

    onDescriptionInput(ev) {
        this.state.description = ev.target.value || "";
    }

    employeeDomain() {
        const uid = parseInt(session.user_id || 0, 10) || 0;
        if (uid) {
            return [
                "|",
                ["user_id", "=", uid],
                "&",
                ["user_id", "!=", false],
                ["costcenter_id.eplus_serial", "!=", false],
            ];
        }
        return [
            ["user_id", "!=", false],
            ["costcenter_id.eplus_serial", "!=", false],
        ];
    }

    onEmployeeUpdate(value) {
        if (value && value.id) {
            this.state.eplus_employee = value;
            return;
        }
        this.state.eplus_employee = false;
    }

    _validate() {
        const header = this.props.bill?.header || {};
        const errors = {};
        const hasCustomer = !!header.customer_id;
        const hasContract = !!header.contract_id;
        const newName = (this.state.new_customer_name || "").trim();
        const newPhone = (this.state.new_customer_phone || "").trim();
        const newAddress = (this.state.new_customer_address || "").trim();
        const hasAnyNew = !!(newName || newPhone || newAddress);

        if (!hasCustomer && hasAnyNew) {
            if (!newName) {
                errors.new_customer_name = true;
            }
            if (!newPhone) {
                errors.new_customer_phone = true;
            }
            if (!newAddress) {
                errors.new_customer_address = true;
            }
        }
        if (hasContract) {
            if (!(this.state.customer_insurance_name || "").trim()) {
                errors.customer_insurance_name = true;
            }
            if (!(this.state.customer_insurance_number || "").trim()) {
                errors.customer_insurance_number = true;
            }
        }
        this.state.errors = errors;
        this.state.message = Object.keys(errors).length
            ? "Please fill the required fields."
            : "";
        return !Object.keys(errors).length;
    }

    async submit() {
        if (this.state.submitting) {
            return;
        }
        const header = this.props.bill?.header || {};
        const hasCustomer = this.state.hasCustomer || !!header.customer_id;
        const newPhone = (this.state.new_customer_phone || "").trim();
        if (!hasCustomer && newPhone) {
            this.openCustomerLookup();
            return;
        }
        if (!this._validate()) {
            return;
        }
        this.state.submitting = true;
        try {
            if (this.props.onSubmit) {
                await this.props.onSubmit(this._payload());
            }
            if (this.props.close) {
                this.props.close();
            }
        } finally {
            this.state.submitting = false;
        }
    }

    cancel() {
        if (this.props.onDraft) {
            this.props.onDraft(this._payload());
        }
        if (this.props.close) {
            this.props.close();
        }
    }

    _payload() {
        return {
            invoice_address: this.state.invoice_address,
            new_customer_name: this.state.new_customer_name,
            new_customer_phone: this.state.new_customer_phone,
            new_customer_address: this.state.new_customer_address,
            bill_customer_name: this.state.bill_customer_name,
            bill_customer_phone: this.state.bill_customer_phone,
            bill_customer_address: this.state.bill_customer_address,
            customer_insurance_name: this.state.customer_insurance_name,
            customer_insurance_number: this.state.customer_insurance_number,
            description: this.state.description,
            employee_id: this.state.eplus_employee?.id || false,
            employee_name: this.state.eplus_employee?.display_name || "",
        };
    }
}

class AbSalesPosCustomerLookupDialog extends Component {
    static template = "ab_sales.PosCustomerLookupDialog";
    static components = {Dialog, Many2One};
    static props = {
        domain: {type: Array, optional: true},
        defaultPhone: {type: String, optional: true},
        defaultName: {type: String, optional: true},
        defaultAddress: {type: String, optional: true},
        onSelect: {type: Function, optional: true},
        close: Function,
    };

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            mode: "search",
            phone: (this.props.defaultPhone || "").trim(),
            name: (this.props.defaultName || "").trim(),
            address: (this.props.defaultAddress || "").trim(),
            branch: false,
            customer: null,
            message: "",
            loading: false,
            errors: {},
            pendingBconnect: false,
        });

        this.phoneRef = useRef("customerPhone");

        this.branchDomain = this.branchDomain.bind(this);
        this.onBranchUpdate = this.onBranchUpdate.bind(this);
        this.onPhoneInput = this.onPhoneInput.bind(this);
        this.onPhoneKeydown = this.onPhoneKeydown.bind(this);
        this.onNameInput = this.onNameInput.bind(this);
        this.onAddressInput = this.onAddressInput.bind(this);
        this.search = this.search.bind(this);
        this.create = this.create.bind(this);
        this.useCustomer = this.useCustomer.bind(this);
        this.close = this.close.bind(this);

        onMounted(() => {
            if (this.phoneRef.el) {
                this.phoneRef.el.focus();
                if (typeof this.phoneRef.el.select === "function") {
                    this.phoneRef.el.select();
                }
            }
            if ((this.state.phone || "").trim()) {
                this.search();
            }
        });
    }

    branchDomain() {
        return this.props.domain || [["allow_sale", "=", true]];
    }

    onBranchUpdate(value) {
        if (value && value.id) {
            this.state.branch = value;
        } else {
            this.state.branch = false;
        }
        if (this.state.errors.branch) {
            this.state.errors = {...this.state.errors, branch: false};
        }
        if (value && value.id && this.state.pendingBconnect && this.state.phone && !this.state.loading) {
            this.search();
        }
    }

    _branchId() {
        const branchId = parseInt(this.state.branch?.id, 10);
        if (!Number.isFinite(branchId)) {
            return null;
        }
        return branchId;
    }

    onPhoneInput(ev) {
        this.state.phone = ev.target.value || "";
    }

    onPhoneKeydown(ev) {
        if (ev.key !== "Enter") {
            return;
        }
        ev.preventDefault();
        ev.stopPropagation();
        this.search();
    }

    _getRpcErrorMessage(err, fallback) {
        const fallbackMessage = fallback || "Request failed.";
        if (!err) {
            return fallbackMessage;
        }
        const data = err.data || err?.response?.data || {};
        const rpcArgs = data?.["arguments"];
        return (
            data?.message ||
            (Array.isArray(rpcArgs) && rpcArgs[0]) ||
            err.message ||
            fallbackMessage
        );
    }

    onNameInput(ev) {
        this.state.name = ev.target.value || "";
    }

    onAddressInput(ev) {
        this.state.address = ev.target.value || "";
    }

    async search() {
        if (this.state.loading) {
            return;
        }
        const phone = (this.state.phone || "").trim();
        if (!phone) {
            this.state.errors = {phone: true};
            this.state.message = "Enter a phone number.";
            return;
        }
        const branchId = this._branchId();
        this.state.loading = true;
        this.state.errors = {};
        this.state.message = "";
        this.state.pendingBconnect = false;
        try {
            const result = await this.orm.call("ab_sales_pos_api", "pos_customer_lookup", [], {
                phone,
                store_id: branchId,
            });
            if (result?.status === "found" && result.customer) {
                this.state.customer = result.customer;
                this.state.mode = "found";
                this.state.name = result.customer.name || "";
                this.state.address = result.customer.address || "";
            } else if (result?.status === "need_store") {
                this.state.mode = "search";
                this.state.customer = null;
                this.state.message = result?.message || "Select a branch to search BConnect.";
                this.state.errors = {branch: true};
                this.state.pendingBconnect = true;
            } else if (result?.status === "not_found") {
                this.state.mode = "create";
                this.state.customer = null;
                this.state.message = "Customer not found. Enter details to create.";
            } else {
                this.state.message = result?.message || "No customer found.";
            }
        } catch (err) {
            this.state.message = this._getRpcErrorMessage(err, "Lookup failed.");
        } finally {
            this.state.loading = false;
        }
    }

    async create() {
        if (this.state.loading) {
            return;
        }
        const phone = (this.state.phone || "").trim();
        const name = (this.state.name || "").trim();
        const address = (this.state.address || "").trim();
        const errors = {};
        const branchId = this._branchId();
        if (!branchId) {
            errors.branch = true;
        }
        if (!name) {
            errors.name = true;
        }
        if (!phone) {
            errors.phone = true;
        }
        if (!address) {
            errors.address = true;
        }
        if (Object.keys(errors).length) {
            this.state.errors = errors;
            this.state.message = errors.branch && Object.keys(errors).length === 1
                ? "Select a branch."
                : "Please fill the required fields.";
            return;
        }
        this.state.loading = true;
        this.state.errors = {};
        this.state.message = "";
        try {
            const result = await this.orm.call("ab_sales_pos_api", "pos_customer_create", [], {
                phone,
                name,
                address,
                store_id: branchId,
            });
            if (result?.customer) {
                this.state.customer = result.customer;
                this.state.mode = "found";
                this.state.message = result?.status === "created"
                    ? "Customer created in BConnect."
                    : "Customer already exists in BConnect.";
            } else {
                this.state.message = result?.message || "Customer creation failed.";
            }
        } catch (err) {
            this.state.message = this._getRpcErrorMessage(err, "Customer creation failed.");
        } finally {
            this.state.loading = false;
        }
    }

    useCustomer() {
        if (this.props.onSelect && this.state.customer) {
            this.props.onSelect(this.state.customer);
        }
        this.close();
    }

    close() {
        if (this.props.close) {
            this.props.close();
        }
    }
}

class AbSalesPosDuplicateTokenDialog extends Component {
    static template = "ab_sales.PosDuplicateTokenDialog";
    static components = {Dialog};
    static props = {
        existing: Object,
        message: {type: String, optional: true},
        onCreateNewToken: Function,
        close: Function,
    };

    setup() {
        this.state = useState({submitting: false});
        this.submitNewToken = this.submitNewToken.bind(this);
        this.formatMoney2 = this.formatMoney2.bind(this);
        this.formatQty = this.formatQty.bind(this);
        this.formatDateTime = this.formatDateTime.bind(this);
    }

    get existing() {
        return this.props.existing || {};
    }

    formatMoney2(value) {
        const numberValue = typeof value === "number" ? value : parseFloat(value ?? 0);
        if (!Number.isFinite(numberValue)) {
            return "0.00";
        }
        return numberValue.toFixed(2);
    }

    formatQty(value) {
        const numberValue = typeof value === "number" ? value : parseFloat(value ?? 0);
        if (!Number.isFinite(numberValue)) {
            return "0";
        }
        const fixed = numberValue.toFixed(2);
        return fixed.replace(/(?:\.0+|(\.\d*?)0+)$/, "$1");
    }

    formatDateTime(value) {
        if (!value) {
            return "-";
        }
        try {
            const dt = new Date(value);
            return `${dt.toLocaleDateString()} ${dt.toLocaleTimeString()}`;
        } catch {
            return value;
        }
    }

    async submitNewToken() {
        if (this.state.submitting) {
            return;
        }
        this.state.submitting = true;
        try {
            if (this.props.onCreateNewToken) {
                await this.props.onCreateNewToken();
            }
            if (this.props.close) {
                this.props.close();
            }
        } finally {
            this.state.submitting = false;
        }
    }

    cancel() {
        if (this.props.close) {
            this.props.close();
        }
    }
}

class AbSalesPosValidationDialog extends Component {
    static template = "ab_sales.PosValidationDialog";
    static components = {Dialog};
    static props = {
        title: {type: String, optional: true},
        message: {type: String, optional: true},
        close: Function,
    };

    close() {
        if (this.props.close) {
            this.props.close();
        }
    }
}

class AbSalesPosAllInvoicesDialog extends Component {
    static template = "ab_sales.PosAllInvoicesDialog";
    static components = {Dialog};
    static props = {
        invoices: {type: Array, optional: true},
        onAddAll: Function,
        close: Function,
    };

    setup() {
        this.state = useState({
            searchQuery: "",
            appliedQuery: "",
            selectedInvoiceId: null,
        });
        this.onSearchInput = this.onSearchInput.bind(this);
        this.searchInvoices = this.searchInvoices.bind(this);
        this.clearSearch = this.clearSearch.bind(this);
        this.selectInvoice = this.selectInvoice.bind(this);
        this.addAll = this.addAll.bind(this);
        this.close = this.close.bind(this);
    }

    formatMoney2(value) {
        const numberValue = typeof value === "number" ? value : parseFloat(value ?? 0);
        if (!Number.isFinite(numberValue)) {
            return "0.00";
        }
        return numberValue.toFixed(2);
    }

    formatDateTime(value) {
        if (!value) {
            return "-";
        }
        try {
            const dt = new Date(value);
            return `${dt.toLocaleDateString()} ${dt.toLocaleTimeString()}`;
        } catch {
            return value;
        }
    }

    get invoices() {
        const rows = Array.isArray(this.props.invoices) ? [...this.props.invoices] : [];
        rows.sort((a, b) => {
            const aTime = new Date(a?.date || 0).getTime() || 0;
            const bTime = new Date(b?.date || 0).getTime() || 0;
            return bTime - aTime;
        });
        return rows;
    }

    get filteredInvoices() {
        const query = (this.state.appliedQuery || "").trim().toLowerCase();
        const rows = this.invoices;
        if (!query) {
            return rows;
        }
        return rows.filter((inv) =>
            (inv?.lines || []).some((line) =>
                String(line?.product_name || "").toLowerCase().includes(query)
            )
        );
    }

    get selectedInvoice() {
        const rows = this.filteredInvoices;
        if (!rows.length) {
            return null;
        }
        const selectedId = parseInt(this.state.selectedInvoiceId || 0, 10);
        if (selectedId) {
            const found = rows.find((inv) => inv.id === selectedId);
            if (found) {
                return found;
            }
        }
        return rows[0];
    }

    formatQty(value) {
        const numberValue = typeof value === "number" ? value : parseFloat(value ?? 0);
        if (!Number.isFinite(numberValue)) {
            return "0";
        }
        const fixed = numberValue.toFixed(2);
        return fixed.replace(/(?:\.0+|(\.\d*?)0+)$/, "$1");
    }

    onSearchInput(ev) {
        this.state.searchQuery = ev?.target?.value || "";
    }

    searchInvoices() {
        this.state.appliedQuery = (this.state.searchQuery || "").trim();
        const first = this.filteredInvoices[0];
        this.state.selectedInvoiceId = first ? first.id : null;
    }

    clearSearch() {
        this.state.searchQuery = "";
        this.state.appliedQuery = "";
        const first = this.filteredInvoices[0];
        this.state.selectedInvoiceId = first ? first.id : null;
    }

    selectInvoice(invoice) {
        if (!invoice?.id) {
            return;
        }
        this.state.selectedInvoiceId = invoice.id;
    }

    addAll(invoice) {
        if (this.props.onAddAll) {
            this.props.onAddAll(invoice || {});
        }
    }

    close() {
        if (this.props.close) {
            this.props.close();
        }
    }
}

class AbSalesPosAction extends Component {
    static template = "ab_sales.PosAction";
    static components = {
        Dialog,
        ABMany2one,
        AbSalesPosSubmitDialog,
        AbSalesPosCustomerLookupDialog,
        AbSalesPosBarcodeLinkDialog,
        AbSalesPosAllInvoicesDialog,
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.dialog = useService("dialog");
        this.action = useService("action");

        this.cacheKey = `${CACHE_PREFIX}_${session.user_id || 0}`;
        this.posUiSettingsKey = `${POS_UI_SETTINGS_PREFIX}_${session.user_id || 0}`;
        const initialPosUiSettings = this._loadPosUiSettingsLocal();
        const initialProductColumnPercentRaw = Number(initialPosUiSettings.productColumnPercent);
        const initialProductColumnPercent = Number.isFinite(initialProductColumnPercentRaw)
            ? Math.max(POS_PRODUCT_COL_MIN, Math.min(POS_PRODUCT_COL_MAX, initialProductColumnPercentRaw))
            : POS_PRODUCT_COL_DEFAULT;
        const viewport = getViewportRect();
        const defaultRect = {
            left: Math.round(viewport.width * 0.05),
            top: Math.round(viewport.height * 0.05),
            width: Math.round(viewport.width * 0.9),
            height: Math.round(viewport.height * 0.9),
        };

        this.state = useState({
            bills: [],
            selectedId: null,
            stores: [],
            storeById: {},
            allowedStoreCodes: [],
            defaultStoreCode: "",
            storeQuery: "",
            storeResults: [],
            productResults: [],
            productQuery: "",
            productHasBalanceOnly: !!initialPosUiSettings.productHasBalanceOnly,
            productHasPosBalanceOnly: !!initialPosUiSettings.productHasPosBalanceOnly,
            productColumnPercent: initialProductColumnPercent,
            posSettingsSaving: false,
            selectionIndex: -1,
            qtyBuffer: "",
            qtyBufferProductId: null,
            customerResults: [],
            customerQuery: "",
            customerInsights: null,
            loadingCustomerInsights: false,
            storeOnline: null,
            showStoreDetails: false,
            showCustomerDetails: false,
            showBillDetails: false,
            sidebarCollapsed: true,
            loadingProducts: false,
            loadingCustomers: false,
            lastCustomerInput: "",
            lastCustomerInputFallback: "",
            submitting: false,
            windowRect: defaultRect,
            windowMinimized: false,
            windowMaximized: true,
            windowClosed: false,
            ...printerStateDefaults(),
        });

        this._lastWindowRect = {...defaultRect};
        this._dragState = null;
        this._resizeState = null;

        this.searchInputRef = useRef("searchInput");
        this.cardsContainerRef = useRef("cardsContainer");
        this.productGridRef = useRef("productGrid");
        this.customerM2ORef = useRef("customerM2O");

        this._productSearchTimer = null;
        this._customerSearchTimer = null;
        this._promoTimer = null;
        this._promoRequestId = 0;
        this._promoDisabled = false;
        this._posBalanceRequestId = 0;
        this._customerInsightsRequestId = 0;
        this._posBalanceTimer = null;
        this._linePosBalanceRequestId = 0;
        this._linePosBalanceTimer = null;
        this._storeStatusRequestId = 0;
        this._viewportCheckTimer = null;
        this._lastViewport = {width: 0, height: 0, ratio: 1};
        this._barcodeActive = false;
        this._barcodeBuffer = "";
        this._lineFocusObserver = null;
        this._lineFocusTimer = null;
        this._uomFactorCache = new Map();
        this._posUiSettingsExtra = {};

        bindPrinterActions(this, {parseQtyExpression});

        this.addProduct = this.addProduct.bind(this);
        this.addProductAndFocus = this.addProductAndFocus.bind(this);
        this.storeValue = this.storeValue.bind(this);
        this.storeDomain = this.storeDomain.bind(this);
        this.customerValue = this.customerValue.bind(this);
        this.onStoreM2OUpdate = this.onStoreM2OUpdate.bind(this);
        this.onCustomerM2OUpdate = this.onCustomerM2OUpdate.bind(this);
        this.selectBill = this.selectBill.bind(this);
        this.removeBill = this.removeBill.bind(this);
        this.removeCurrentBill = this.removeCurrentBill.bind(this);
        this.openNewBillDialog = this.openNewBillDialog.bind(this);
        this.openCustomerLookup = this.openCustomerLookup.bind(this);
        this.applyCustomerLookup = this.applyCustomerLookup.bind(this);
        this.onCustomerInput = this.onCustomerInput.bind(this);
        this.captureCustomerInput = this.captureCustomerInput.bind(this);
        this.onCustomerPointerDown = this.onCustomerPointerDown.bind(this);
        this.updateHeaderField = this.updateHeaderField.bind(this);
        this._openSubmitDialog = this._openSubmitDialog.bind(this);
        this._applySubmitDialog = this._applySubmitDialog.bind(this);
        this._openDuplicateTokenDialog = this._openDuplicateTokenDialog.bind(this);
        this._submitBillInternal = this._submitBillInternal.bind(this);
        this._buildSubmitHeader = this._buildSubmitHeader.bind(this);
        this.toggleStoreDetails = this.toggleStoreDetails.bind(this);
        this.toggleCustomerDetails = this.toggleCustomerDetails.bind(this);
        this.toggleBillDetails = this.toggleBillDetails.bind(this);
        this.toggleSidebar = this.toggleSidebar.bind(this);
        this.setCustomerMode = this.setCustomerMode.bind(this);
        this.onProductSearch = this.onProductSearch.bind(this);
        this.onProductSearchKeydown = this.onProductSearchKeydown.bind(this);
        this.onProductHasBalanceChange = this.onProductHasBalanceChange.bind(this);
        this.onProductHasPosBalanceChange = this.onProductHasPosBalanceChange.bind(this);
        this.updateLineQty = this.updateLineQty.bind(this);
        this.updateLineSellPrice = this.updateLineSellPrice.bind(this);
        this.updateLineTargetPrice = this.updateLineTargetPrice.bind(this);
        this.loadLineDetails = this.loadLineDetails.bind(this);
        this.removeLine = this.removeLine.bind(this);
        this.submitCurrentBill = this.submitCurrentBill.bind(this);
        this.openBillWizard = this.openBillWizard.bind(this);
        this.openStoresBalance = this.openStoresBalance.bind(this);
        this.scheduleLinePosBalanceRefresh = this.scheduleLinePosBalanceRefresh.bind(this);
        this._refreshPosBalancesForLines = this._refreshPosBalancesForLines.bind(this);
        this.refreshLinePosBalance = this.refreshLinePosBalance.bind(this);
        this.onAvailablePriceSelect = this.onAvailablePriceSelect.bind(this);
        this._openBarcodeLinkDialog = this._openBarcodeLinkDialog.bind(this);
        this._openBarcodeRegisterDialog = this._openBarcodeRegisterDialog.bind(this);
        this._linkBarcodeProducts = this._linkBarcodeProducts.bind(this);
        this.formatPrice = this.formatPrice.bind(this);
        this.formatQty = this.formatQty.bind(this);
        this.formatMoney2 = this.formatMoney2.bind(this);
        this.lineUomValue = this.lineUomValue.bind(this);
        this.onLineUomUpdate = this.onLineUomUpdate.bind(this);
        this._extractUomInfo = this._extractUomInfo.bind(this);
        this._getUomFactor = this._getUomFactor.bind(this);
        this._syncAvailablePricesForUom = this._syncAvailablePricesForUom.bind(this);
        this.productLabel = this.productLabel.bind(this);
        this.onResizeStart = this.onResizeStart.bind(this);
        this.onSidebarResizeStart = this.onSidebarResizeStart.bind(this);
        this.onKeydown = this.onKeydown.bind(this);
        this.onWindowDragStart = this.onWindowDragStart.bind(this);
        this.onWindowResizeStart = this.onWindowResizeStart.bind(this);
        this.toggleWindowMinimize = this.toggleWindowMinimize.bind(this);
        this.toggleWindowMaximize = this.toggleWindowMaximize.bind(this);
        this.toggleFullScreen = this.toggleFullScreen.bind(this);
        this.closeWindow = this.closeWindow.bind(this);
        this.windowStyle = this.windowStyle.bind(this);
        this._applyPosScale = this._applyPosScale.bind(this);
        this.refreshPromotions = this.refreshPromotions.bind(this);
        this.schedulePromoRefresh = this.schedulePromoRefresh.bind(this);
        this.selectPromotion = this.selectPromotion.bind(this);
        this.clearPromotion = this.clearPromotion.bind(this);
        this._extractPhoneCandidate = this._extractPhoneCandidate.bind(this);
        this.schedulePosBalanceRefresh = this.schedulePosBalanceRefresh.bind(this);
        this._refreshPosBalancesForResults = this._refreshPosBalancesForResults.bind(this);
        this.refreshStoreStatus = this.refreshStoreStatus.bind(this);
        this.refreshCustomerInsights = this.refreshCustomerInsights.bind(this);
        this.openCustomerInvoicesDialog = this.openCustomerInvoicesDialog.bind(this);
        this.addLastInvoiceItems = this.addLastInvoiceItems.bind(this);
        this.copyLastAddress = this.copyLastAddress.bind(this);
        this.activeCustomerPhone = this.activeCustomerPhone.bind(this);
        this.pinnedResultsCount = this.pinnedResultsCount.bind(this);
        this.savePosUiSettings = this.savePosUiSettings.bind(this);
        this.loadPosUiSettings = this.loadPosUiSettings.bind(this);
        this._defaultPosUiSettings = this._defaultPosUiSettings.bind(this);
        this._normalizePosUiSettings = this._normalizePosUiSettings.bind(this);
        this._loadPosUiSettingsLocal = this._loadPosUiSettingsLocal.bind(this);
        this._savePosUiSettingsLocal = this._savePosUiSettingsLocal.bind(this);
        this._currentPosUiSettings = this._currentPosUiSettings.bind(this);
        this._applyPosUiSettings = this._applyPosUiSettings.bind(this);
        this._clampProductColumnPercent = this._clampProductColumnPercent.bind(this);
        this._readProductColumnPercent = this._readProductColumnPercent.bind(this);
        this._applyProductColumnPercent = this._applyProductColumnPercent.bind(this);

        this.shortcutHandlers = new Map([
            ["ArrowDown", this._onHotkeyArrowDown.bind(this)],
            ["ArrowUp", this._onHotkeyArrowUp.bind(this)],
            ["Enter", this._onHotkeyEnter.bind(this)],
        ]);

        useExternalListener(window, "keydown", (ev) => this.onKeydown(ev), {capture: true});
        useExternalListener(window, "resize", () => this._syncWindowToViewport());
        if (window.visualViewport) {
            useExternalListener(window.visualViewport, "resize", () => this._syncWindowToViewport());
        }

        onWillStart(async () => {
            await this.loadStores();
            await this.loadPrinterSettings();
            this.loadCache();
            await this.loadPosUiSettings();
        });

        onMounted(() => {
            if (!this.state.selectedId && this.state.bills.length) {
                this.state.selectedId = this.state.bills[0].id;
            }
            this._syncInputsForBill(this.currentBill);
            this.refreshPromotions(this.currentBill);
            this.scheduleLinePosBalanceRefresh(this.currentBill);
            this.refreshStoreStatus(this.currentBill?.header?.store_id);
            this.refreshCustomerInsights(this.currentBill);
            this.searchProducts((this.state.productQuery || "").trim());
            this._syncWindowToViewport();
            this._applyPosScale();
            this._applyProductColumnPercent(this.state.productColumnPercent);
            requestAnimationFrame(() => this._applyPosScale());
            setTimeout(() => this._applyPosScale(), 150);
            const rect = getViewportRect();
            this._lastViewport = {
                width: rect.width,
                height: rect.height,
                ratio: window.devicePixelRatio || 1,
            };
            this._viewportCheckTimer = setInterval(() => {
                const next = getViewportRect();
                const ratio = window.devicePixelRatio || 1;
                if (
                    next.width !== this._lastViewport.width ||
                    next.height !== this._lastViewport.height ||
                    ratio !== this._lastViewport.ratio
                ) {
                    this._lastViewport = {width: next.width, height: next.height, ratio};
                    this._syncWindowToViewport();
                }
            }, 250);
        });

        onWillUnmount(() => {
            if (this._viewportCheckTimer) {
                clearInterval(this._viewportCheckTimer);
                this._viewportCheckTimer = null;
            }
            if (this._posBalanceTimer) {
                clearTimeout(this._posBalanceTimer);
                this._posBalanceTimer = null;
            }
            if (this._linePosBalanceTimer) {
                clearTimeout(this._linePosBalanceTimer);
                this._linePosBalanceTimer = null;
            }
        });
    }

    get currentBill() {
        return this.state.bills.find((b) => b.id === this.state.selectedId) || null;
    }

    loadCache() {
        try {
            const raw = localStorage.getItem(this.cacheKey);
            const bills = raw ? JSON.parse(raw) : [];
            if (Array.isArray(bills)) {
                this.state.bills = bills.map((b) => this._normalizeBill(b));
            }
        } catch {
            this.state.bills = [];
        }
    }

    _defaultPosUiSettings() {
        return {
            productHasBalanceOnly: true,
            productHasPosBalanceOnly: true,
            productColumnPercent: POS_PRODUCT_COL_DEFAULT,
        };
    }

    _clampProductColumnPercent(value) {
        const pct = Number(value);
        if (!Number.isFinite(pct)) {
            return POS_PRODUCT_COL_DEFAULT;
        }
        return Math.max(POS_PRODUCT_COL_MIN, Math.min(POS_PRODUCT_COL_MAX, pct));
    }

    _readProductColumnPercent() {
        const rootEl = this.el || this.productGridRef?.el;
        let raw = rootEl?.style?.getPropertyValue?.("--pos-product-col") || "";
        if (!raw && typeof window !== "undefined" && rootEl) {
            raw = window.getComputedStyle(rootEl).getPropertyValue("--pos-product-col") || "";
        }
        const parsed = parseFloat(String(raw || "").replace("%", "").trim());
        if (Number.isFinite(parsed)) {
            return this._clampProductColumnPercent(parsed);
        }
        return this._clampProductColumnPercent(this.state.productColumnPercent);
    }

    _applyProductColumnPercent(value) {
        const pct = this._clampProductColumnPercent(value);
        const rootEl = this.el || this.productGridRef?.el;
        if (rootEl?.style?.setProperty) {
            rootEl.style.setProperty("--pos-product-col", `${pct}%`);
        }
        return pct;
    }

    _normalizePosUiSettings(payload) {
        const defaults = this._defaultPosUiSettings();
        const raw = payload && typeof payload === "object" ? payload : {};
        return {
            ...raw,
            productHasBalanceOnly:
                typeof raw.productHasBalanceOnly === "boolean"
                    ? raw.productHasBalanceOnly
                    : defaults.productHasBalanceOnly,
            productHasPosBalanceOnly:
                typeof raw.productHasPosBalanceOnly === "boolean"
                    ? raw.productHasPosBalanceOnly
                    : defaults.productHasPosBalanceOnly,
            productColumnPercent: this._clampProductColumnPercent(
                Number.isFinite(Number(raw.productColumnPercent))
                    ? Number(raw.productColumnPercent)
                    : defaults.productColumnPercent
            ),
        };
    }

    _loadPosUiSettingsLocal() {
        try {
            const raw = localStorage.getItem(this.posUiSettingsKey);
            if (!raw) {
                return this._defaultPosUiSettings();
            }
            return this._normalizePosUiSettings(JSON.parse(raw));
        } catch {
            return this._defaultPosUiSettings();
        }
    }

    _savePosUiSettingsLocal(payload) {
        try {
            const settings = this._normalizePosUiSettings(payload);
            localStorage.setItem(this.posUiSettingsKey, JSON.stringify(settings));
        } catch {
            // Ignore localStorage write failures.
        }
    }

    _currentPosUiSettings() {
        return this._normalizePosUiSettings({
            ...this._posUiSettingsExtra,
            productHasBalanceOnly: !!this.state.productHasBalanceOnly,
            productHasPosBalanceOnly: !!this.state.productHasPosBalanceOnly,
            productColumnPercent: this._readProductColumnPercent(),
        });
    }

    _applyPosUiSettings(payload, persistLocal = true) {
        const raw = payload && typeof payload === "object" ? payload : {};
        const settings = this._normalizePosUiSettings(raw);
        const extras = {};
        for (const [key, value] of Object.entries(raw)) {
            if (key === "productHasBalanceOnly" || key === "productHasPosBalanceOnly") {
                continue;
            }
            extras[key] = value;
        }
        this._posUiSettingsExtra = extras;
        this.state.productHasBalanceOnly = !!settings.productHasBalanceOnly;
        this.state.productHasPosBalanceOnly = !!settings.productHasPosBalanceOnly;
        this.state.productColumnPercent = this._applyProductColumnPercent(settings.productColumnPercent);
        if (persistLocal) {
            this._savePosUiSettingsLocal(settings);
        }
        return settings;
    }

    async loadPosUiSettings() {
        let settings = null;
        try {
            const result = await this.orm.call("ab_sales_ui_api", "get_pos_ui_settings", [], {});
            settings = result?.settings || result || null;
        } catch {
            settings = null;
        }
        if (!settings) {
            settings = this._loadPosUiSettingsLocal();
        }
        this._applyPosUiSettings(settings, true);
    }

    async savePosUiSettings() {
        if (this.state.posSettingsSaving) {
            return;
        }
        this.state.posSettingsSaving = true;
        const payload = this._currentPosUiSettings();
        try {
            const result = await this.orm.call("ab_sales_ui_api", "save_pos_ui_settings", [], {
                settings: payload,
            });
            this._applyPosUiSettings(result?.settings || payload, true);
            this.notification.add("Settings saved.", {type: "success"});
        } catch (err) {
            this.notification.add(err?.message || "Failed to save settings.", {type: "danger"});
        } finally {
            this.state.posSettingsSaving = false;
        }
    }

    _syncInputsForBill(bill) {
        if (!bill) {
            this.state.storeQuery = "";
            this.state.customerQuery = "";
            this.state.storeResults = [];
            this.state.customerResults = [];
            return;
        }
        this.state.storeQuery = bill.header.store_name || "";
        if (bill.header.customer_mode === "new") {
            this.state.customerQuery = "";
        } else {
            this.state.customerQuery = bill.header.customer_name || "";
        }
        this.state.storeResults = [];
        this.state.customerResults = [];
    }

    persistCache() {
        const payload = JSON.stringify(this.state.bills || []);
        localStorage.setItem(this.cacheKey, payload);
    }

    async loadStores() {
        let allowedCodes = [];
        let defaultCode = "";
        try {
            const settings = await this.orm.call("ab_sales_ui_api", "get_sales_store_settings", [], {});
            allowedCodes = Array.isArray(settings?.allowed_store_codes)
                ? settings.allowed_store_codes
                : [];
            defaultCode = (settings?.default_store_code || "").trim();
        } catch {
            allowedCodes = [];
            defaultCode = "";
        }
        const domain = [["allow_sale", "=", true]];
        if (allowedCodes.length) {
            domain.push(["code", "in", allowedCodes]);
        }
        const stores = await this.orm.searchRead("ab_store", domain, ["name", "code", "ip1"]);
        this.state.stores = stores || [];
        this.state.allowedStoreCodes = allowedCodes;
        const byId = {};
        for (const store of this.state.stores) {
            byId[store.id] = store;
        }
        this.state.storeById = byId;
        if (defaultCode) {
            this.state.defaultStoreCode = defaultCode;
        } else if (allowedCodes.length === 1) {
            this.state.defaultStoreCode = allowedCodes[0];
        } else {
            this.state.defaultStoreCode = "";
        }
    }

    openNewBillDialog() {
        if (!this.state.stores.length) {
            this.notification.add("No stores available.", {type: "warning"});
            return;
        }
        this.dialog.add(AbSalesPosStoreDialog, {
            stores: this.state.stores,
            defaultStoreCode: this.state.defaultStoreCode,
            domain: this.storeDomain(),
            onSelect: (storeId) => this.createNewBill(storeId),
        });
    }

    openCustomerLookup() {
        const bill = this.currentBill;
        if (!bill) {
            return;
        }
        const typedValue = this.state.lastCustomerInputFallback || this.state.lastCustomerInput || "";
        const typedPhone = this._extractPhoneCandidate(typedValue);
        const fallbackPhone = this._extractPhoneCandidate(
            bill.header.customer_mobile || bill.header.customer_phone || ""
        );
        const defaultPhone = typedPhone || fallbackPhone || "";
        this.dialog.add(AbSalesPosCustomerLookupDialog, {
            defaultPhone,
            domain: this.storeDomain(),
            onSelect: (customer) => this.applyCustomerLookup(customer),
        });
    }

    async applyCustomerLookup(customer) {
        if (!customer || !customer.id) {
            return;
        }
        this.selectCustomer(customer);
        await this.onCustomerM2OUpdate({
            id: customer.id,
            display_name: customer.name || customer.code || "",
        });
    }

    onCustomerInput(ev) {
        const target = ev?.target;
        if (!target || target.tagName !== "INPUT") {
            return;
        }
        const value = target.value || "";
        this.state.lastCustomerInput = value;
        if (/\d/.test(value)) {
            this.state.lastCustomerInputFallback = value;
        }
    }

    captureCustomerInput() {
        const inputEl = this.customerM2ORef.el?.querySelector?.("input");
        if (inputEl) {
            const value = inputEl.value || "";
            this.state.lastCustomerInput = value;
            if (/\d/.test(value)) {
                this.state.lastCustomerInputFallback = value;
            }
        }
    }

    onCustomerPointerDown(ev) {
        const target = ev?.target;
        if (!target || !target.closest) {
            return;
        }
        if (target.closest(".o_ab_many2one_clear")) {
            this.state.lastCustomerInput = "";
            this.state.lastCustomerInputFallback = "";
        }
    }

    _extractPhoneCandidate(value) {
        let digits = String(value || "").replace(/\D/g, "");
        if (!digits) {
            return "";
        }
        if (digits.startsWith("0020") && digits.length >= 14) {
            digits = `0${digits.slice(4)}`;
        } else if (digits.startsWith("20") && digits.length >= 12) {
            digits = `0${digits.slice(2)}`;
        } else if (digits.length === 10 && digits.startsWith("1")) {
            digits = `0${digits}`;
        }
        if (digits.length > 11 && digits.startsWith("0")) {
            digits = digits.slice(-11);
        }
        if (digits.length !== 11 || !digits.startsWith("01")) {
            return "";
        }
        return digits;
    }

    activeCustomerPhone(billArg = null) {
        const bill = billArg || this.currentBill;
        if (!bill?.header) {
            return "";
        }
        return this._extractPhoneCandidate(
            bill.header.bill_customer_phone || bill.header.customer_phone || bill.header.customer_mobile || ""
        );
    }

    pinnedResultsCount() {
        return (this.state.productResults || []).filter((row) => !!row?.is_pinned).length;
    }

    async refreshCustomerInsights(billArg = null) {
        const bill = billArg || this.currentBill;
        const requestId = ++this._customerInsightsRequestId;
        if (!bill?.header?.store_id) {
            this.state.customerInsights = null;
            this.state.loadingCustomerInsights = false;
            return;
        }
        const phone = this.activeCustomerPhone(bill);
        if (!phone) {
            this.state.customerInsights = null;
            this.state.loadingCustomerInsights = false;
            return;
        }
        this.state.loadingCustomerInsights = true;
        try {
            const result = await this.orm.call("ab_sales_ui_api", "pos_customer_insights", [], {
                customer_phone: phone,
            });
            if (requestId !== this._customerInsightsRequestId) {
                return;
            }
            this.state.customerInsights = result || null;
        } catch {
            if (requestId !== this._customerInsightsRequestId) {
                return;
            }
            this.state.customerInsights = null;
        } finally {
            if (requestId === this._customerInsightsRequestId) {
                this.state.loadingCustomerInsights = false;
            }
        }
    }

    async copyLastAddress() {
        const text = this.state.customerInsights?.customer?.last_address || "";
        if (!text) {
            this.notification.add("No address to copy.", {type: "warning"});
            return;
        }
        try {
            if (navigator?.clipboard?.writeText) {
                await navigator.clipboard.writeText(text);
            }
            this.notification.add("Address copied.", {type: "success"});
        } catch {
            this.notification.add("Copy failed.", {type: "danger"});
        }
    }

    async openCustomerInvoicesDialog() {
        const bill = this.currentBill;
        const phone = this.activeCustomerPhone(bill);
        if (!phone) {
            this.notification.add("Select a customer with phone number first.", {type: "warning"});
            return;
        }
        try {
            const invoices = await this.orm.call("ab_sales_ui_api", "pos_customer_invoices", [], {
                customer_phone: phone,
                limit: 20,
            });
            if (!Array.isArray(invoices) || !invoices.length) {
                this.notification.add("No invoices found for this customer.", {type: "warning"});
                return;
            }
            this.dialog.add(AbSalesPosAllInvoicesDialog, {
                invoices,
                onAddAll: (payload) => this.addLastInvoiceItems(payload),
            });
        } catch (err) {
            this.notification.add(err?.message || "Failed to load invoices.", {type: "danger"});
        }
    }

    addLastInvoiceItems(invoice) {
        const lines = invoice?.lines || [];
        if (!lines.length) {
            this.notification.add("No items in selected invoice.", {type: "warning"});
            return;
        }
        let addedLines = 0;
        let firstLine = null;
        for (const row of lines) {
            const productId = parseInt(row?.product_id || 0, 10);
            const qty = parseFloat(row?.qty || 0) || 0;
            if (!productId || qty <= 0) {
                continue;
            }
            const line = this.addProduct(
                {
                    id: productId,
                    name: row.product_name || "",
                    code: row.product_code || "",
                    default_price: parseFloat(row.sell_price || 0) || 0,
                },
                qty
            );
            if (!firstLine && line) {
                firstLine = line;
            }
            addedLines += 1;
        }
        if (!addedLines) {
            this.notification.add("No valid items to add.", {type: "warning"});
            return;
        }
        if (firstLine) {
            this._focusLineQty(firstLine);
        }
        this.notification.add(`Added ${addedLines} item(s) from selected invoice.`, {type: "success"});
    }

    storeDomain() {
        const domain = [["allow_sale", "=", true]];
        if (this.state.allowedStoreCodes.length) {
            domain.push(["code", "in", this.state.allowedStoreCodes]);
        }
        return domain;
    }

    createNewBill(storeId) {
        const store = this.state.storeById[storeId];
        if (!store) {
            this.notification.add("Select a valid store.", {type: "warning"});
            return;
        }
        const bill = {
            id: generateId("bill"),
            local_number: `${Date.now()}`,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
            header: {
                store_id: store.id,
                store_name: store.name,
                store_code: store.code,
                store_ip: store.ip1,
                description: "",
                customer_id: null,
                customer_name: "",
                customer_address: "",
                customer_mobile: "",
                customer_phone: "",
                customer_code: "",
                invoice_address: "",
                bill_customer_name: "",
                bill_customer_phone: "",
                bill_customer_address: "",
                pos_client_token: generatePosToken(session.user_id, store.id),
                new_customer_name: "",
                new_customer_phone: "",
                new_customer_address: "",
                customer_insurance_name: "",
                customer_insurance_number: "",
                employee_id: false,
                employee_name: "",
                customer_mode: "current",
            },
            lines: [],
            number_of_products: 0,
            total_price: 0,
            total_net_amount: 0,
            promo: this._defaultPromo(),
        };
        this.state.bills.unshift(bill);
        this.state.selectedId = bill.id;
        this._syncInputsForBill(bill);
        this.persistCache();
        this.refreshStoreStatus(bill.header.store_id);
        this.refreshCustomerInsights(bill);
        this.searchProducts((this.state.productQuery || "").trim());
    }

    _defaultPromo() {
        return {
            available: [],
            applied_id: null,
            applied_name: "",
            selected_id: null,
            selected_name: "",
            manual_clear: false,
            total_net_amount: 0,
            message: "",
            discount_amount: 0,
            total_after: 0,
            loading: false,
        };
    }

    _normalizePromo(promo) {
        const normalized = this._defaultPromo();
        const raw = promo || {};
        normalized.available = Array.isArray(raw.available) ? raw.available : [];
        const appliedId = parseInt(raw.applied_id, 10);
        const selectedId = parseInt(raw.selected_id, 10);
        normalized.applied_id = Number.isFinite(appliedId) ? appliedId : null;
        normalized.applied_name = raw.applied_name || "";
        normalized.selected_id = Number.isFinite(selectedId) ? selectedId : null;
        normalized.selected_name = raw.selected_name || "";
        normalized.manual_clear = !!raw.manual_clear;
        normalized.total_net_amount = parseFloat(raw.total_net_amount || 0) || 0;
        normalized.message = raw.message || "";
        normalized.discount_amount = parseFloat(raw.discount_amount || 0) || 0;
        normalized.total_after = parseFloat(raw.total_after || 0) || 0;
        return normalized;
    }

    _normalizeBill(bill) {
        const normalized = bill || {};
        normalized.header = normalized.header || {};
        normalized.lines = Array.isArray(normalized.lines) ? normalized.lines : [];
        normalized.promo = this._normalizePromo(normalized.promo);
        normalized.header.customer_mode = normalized.header.customer_mode || "current";
        normalized.header.description = normalized.header.description || "";
        normalized.header.invoice_address = normalized.header.invoice_address || "";
        normalized.header.new_customer_name = normalized.header.new_customer_name || "";
        normalized.header.new_customer_phone = normalized.header.new_customer_phone || "";
        normalized.header.new_customer_address = normalized.header.new_customer_address || "";
        normalized.header.bill_customer_name = normalized.header.bill_customer_name || "";
        normalized.header.bill_customer_phone = normalized.header.bill_customer_phone || "";
        normalized.header.bill_customer_address = normalized.header.bill_customer_address || "";
        normalized.header.customer_insurance_name = normalized.header.customer_insurance_name || "";
        normalized.header.customer_insurance_number = normalized.header.customer_insurance_number || "";
        normalized.header.employee_id = normalized.header.employee_id || normalized.header.eplus_employee_id || false;
        normalized.header.employee_name = normalized.header.employee_name || normalized.header.eplus_employee_name || "";
        normalized.header.customer_name = normalized.header.customer_name || "";
        normalized.header.customer_address = normalized.header.customer_address || "";
        normalized.header.customer_mobile = normalized.header.customer_mobile || "";
        normalized.header.customer_phone = normalized.header.customer_phone || "";
        normalized.header.customer_code = normalized.header.customer_code || "";
        normalized.header.pos_client_token =
            normalized.header.pos_client_token || generatePosToken(session.user_id, normalized.header.store_id);
        normalized.updated_at = normalized.updated_at || new Date().toISOString();
        normalized.local_number = normalized.local_number || String(Date.now());
        normalized.id = normalized.id || generateId("bill");
        for (const line of normalized.lines) {
            line.id = line.id || generateId("line");
            line.qty_str = line.qty_str || DEFAULT_QTY;
            line.sell_price = Number.isFinite(line.sell_price) ? line.sell_price : parseFloat(line.sell_price || 0) || 0;
            line.sell_price_str = line.sell_price_str !== undefined && line.sell_price_str !== null
                ? String(line.sell_price_str)
                : String(line.sell_price || 0);
            line.cost = Number.isFinite(line.cost) ? line.cost : parseFloat(line.cost || 0) || 0;
            line.target_sell_price =
                Number.isFinite(line.target_sell_price) ? line.target_sell_price : parseFloat(line.target_sell_price || 0) || 0;
            line.balance = Number.isFinite(line.balance) ? line.balance : parseFloat(line.balance || 0) || 0;
            line.balance_total = Number.isFinite(line.balance_total)
                ? line.balance_total
                : Number.isFinite(line.balance)
                    ? line.balance
                    : parseFloat(line.balance || 0) || 0;
            line.pos_balance = Number.isFinite(line.pos_balance)
                ? line.pos_balance
                : parseFloat(line.pos_balance || 0) || 0;
            line.available_prices = Array.isArray(line.available_prices) ? line.available_prices : [];
            line.available_prices_base = Array.isArray(line.available_prices_base)
                ? line.available_prices_base
                : line.available_prices;
            line.available_prices_html = "";
            line.inventory_table_html = line.inventory_table_html || "";
            line.show_details = !!line.show_details;
            line.loading_details = false;
            if (Array.isArray(line.uom_id)) {
                line.uom_name = line.uom_id[1] || line.uom_name || "";
                line.uom_id = line.uom_id[0] || null;
            }
            if (Array.isArray(line.uom_category_id)) {
                line.uom_category_id = line.uom_category_id[0] || null;
            }
            line.uom_id = line.uom_id || null;
            line.uom_name = line.uom_name || "";
            line.uom_category_id = line.uom_category_id || null;
            line.uom_factor = Number.isFinite(line.uom_factor) ? line.uom_factor : parseFloat(line.uom_factor || 0) || 0;
            line.default_uom_id = line.default_uom_id || line.uom_id || null;
            line.default_uom_factor = Number.isFinite(line.default_uom_factor)
                ? line.default_uom_factor
                : parseFloat(line.default_uom_factor || 0) || line.uom_factor || 1;
            if (line.default_uom_id && line.default_uom_factor > 0) {
                this._uomFactorCache.set(line.default_uom_id, line.default_uom_factor);
            }
            line.default_sell_price = Number.isFinite(line.default_sell_price)
                ? line.default_sell_price
                : parseFloat(line.default_sell_price || 0) || line.sell_price || 0;
            line.base_sell_price = Number.isFinite(line.base_sell_price)
                ? line.base_sell_price
                : parseFloat(line.base_sell_price || 0) || line.default_sell_price || line.sell_price || 0;
            this._syncAvailablePricesForUom(line);
            this._recomputeLine(line);
        }
        this._recomputeBill(normalized, {persist: false});
        return normalized;
    }

    selectBill(billId) {
        this.state.selectedId = billId;
        this._syncInputsForBill(this.currentBill);
        this.refreshPromotions(this.currentBill);
        this.scheduleLinePosBalanceRefresh(this.currentBill);
        this.refreshStoreStatus(this.currentBill?.header?.store_id);
        this.refreshCustomerInsights(this.currentBill);
        this.searchProducts((this.state.productQuery || "").trim());
    }

    removeBill(billId) {
        this.state.bills = this.state.bills.filter((b) => b.id !== billId);
        if (this.state.selectedId === billId) {
            this.state.selectedId = this.state.bills.length ? this.state.bills[0].id : null;
        }
        this._syncInputsForBill(this.currentBill);
        this.refreshPromotions(this.currentBill);
        this.refreshCustomerInsights(this.currentBill);
        this.searchProducts((this.state.productQuery || "").trim());
        this.persistCache();
    }

    removeCurrentBill() {
        if (!this.currentBill) {
            return;
        }
        this.removeBill(this.currentBill.id);
    }

    updateHeaderField(field, value) {
        const bill = this.currentBill;
        if (!bill) {
            return;
        }
        bill.header[field] = value;
        bill.updated_at = new Date().toISOString();
        this.persistCache();
        this.refreshCustomerInsights(bill);
        this.searchProducts((this.state.productQuery || "").trim());
    }

    _openSubmitDialog(bill) {
        if (!bill) {
            return;
        }
        this.dialog.add(AbSalesPosSubmitDialog, {
            bill,
            preferredBillName: this.state.customerInsights?.customer?.name || "",
            preferredBillAddress: this.state.customerInsights?.customer?.last_address || "",
            onSubmit: async (payload) => {
                await this._applySubmitDialog(bill, payload);
                await this._submitBillInternal(bill);
            },
            onDraft: (payload) => {
                this._applySubmitDialog(bill, payload);
            },
            onCustomerApply: (customer) => this.applyCustomerLookup(customer),
        });
    }

    _openDuplicateTokenDialog(bill, payload) {
        if (!bill) {
            return;
        }
        const existing = payload?.existing_header || {};
        const message = payload?.message || "An invoice already exists with the same token.";
        this.dialog.add(AbSalesPosDuplicateTokenDialog, {
            existing,
            message,
            onCreateNewToken: async () => {
                const storeId = bill.header?.store_id || existing?.store?.id;
                bill.header.pos_client_token = generatePosToken(session.user_id, storeId);
                bill.updated_at = new Date().toISOString();
                this.persistCache();
                await this._submitBillInternal(bill);
            },
        });
    }

    _openSubmitErrorDialog(message, title) {
        this.dialog.add(AbSalesPosValidationDialog, {
            title: title || "Submit failed",
            message: message || "Submit failed.",
        });
    }

    _applySubmitDialog(bill, payload) {
        if (!bill) {
            return;
        }
        const header = bill.header || {};
        const hasCustomer = !!header.customer_id;
        const billCustomerName = (payload?.bill_customer_name || "").trim();
        const billCustomerPhone = (payload?.bill_customer_phone || "").trim();
        const billCustomerAddress = (payload?.bill_customer_address || "").trim();

        if (hasCustomer) {
            header.customer_mode = "current";
            header.bill_customer_name = billCustomerName;
            header.bill_customer_phone = billCustomerPhone;
            header.bill_customer_address = billCustomerAddress;
            header.invoice_address = billCustomerAddress || (payload?.invoice_address || "").trim();
            header.new_customer_name = "";
            header.new_customer_phone = "";
            header.new_customer_address = "";
        } else {
            header.customer_mode = "new";
            const newName = (payload?.new_customer_name || "").trim();
            const newPhone = (payload?.new_customer_phone || "").trim();
            const newAddress = (payload?.new_customer_address || "").trim();
            header.new_customer_name = newName;
            header.new_customer_phone = newPhone;
            header.new_customer_address = newAddress;
            header.bill_customer_name = newName;
            header.bill_customer_phone = newPhone;
            header.bill_customer_address = newAddress;
            header.invoice_address = newAddress;
        }

        header.customer_insurance_name = (payload?.customer_insurance_name || "").trim();
        header.customer_insurance_number = (payload?.customer_insurance_number || "").trim();
        header.description = (payload?.description || "").trim();
        const employeeId = parseInt(payload?.employee_id || 0, 10);
        header.employee_id = Number.isFinite(employeeId) && employeeId > 0 ? employeeId : false;
        header.employee_name = (payload?.employee_name || "").trim();

        bill.updated_at = new Date().toISOString();
        this.persistCache();
    }

    _buildSubmitHeader(bill) {
        const header = {
            store_id: bill.header.store_id,
            description: bill.header.description,
            customer_id: bill.header.customer_id,
            invoice_address: bill.header.invoice_address,
            new_customer_name: bill.header.new_customer_name,
            new_customer_phone: bill.header.new_customer_phone,
            new_customer_address: bill.header.new_customer_address,
            bill_customer_name: bill.header.bill_customer_name,
            bill_customer_phone: bill.header.bill_customer_phone,
            bill_customer_address: bill.header.bill_customer_address,
            customer_insurance_name: bill.header.customer_insurance_name,
            customer_insurance_number: bill.header.customer_insurance_number,
            pos_client_token: bill.header.pos_client_token,
        };
        const employeeId = parseInt(bill.header.employee_id || 0, 10);
        if (Number.isFinite(employeeId) && employeeId > 0) {
            header.employee_id = employeeId;
        }
        return header;
    }

    storeValue() {
        const bill = this.currentBill;
        if (!bill?.header?.store_id) {
            return false;
        }
        return {
            id: bill.header.store_id,
            display_name: bill.header.store_name || "",
        };
    }

    customerValue() {
        const bill = this.currentBill;
        if (!bill || bill.header.customer_mode !== "current" || !bill.header.customer_id) {
            return false;
        }
        return {
            id: bill.header.customer_id,
            display_name: bill.header.customer_name || "",
        };
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

    async onLineUomUpdate(line, value) {
        const bill = this.currentBill;
        if (!bill || !line) {
            return;
        }
        if (!value || !value.id) {
            line.uom_id = null;
            line.uom_name = "";
        } else {
            line.uom_id = value.id;
            line.uom_name = value.display_name || "";
        }
        if (line.uom_id) {
            const selectedFactor = await this._getUomFactor(line.uom_id);
            const defaultUomId = line.default_uom_id || line.uom_id;
            const defaultFactor = defaultUomId ? await this._getUomFactor(defaultUomId) : 0;
            if (defaultFactor > 0) {
                line.default_uom_factor = defaultFactor;
            }
            if (selectedFactor > 0) {
                line.uom_factor = selectedFactor;
            }
            if (selectedFactor > 0 && defaultFactor > 0) {
                const ratio = selectedFactor / defaultFactor;
                const basePrice =
                    parseFloat(line.base_sell_price || 0) ||
                    parseFloat(line.default_sell_price || 0) ||
                    parseFloat(line.sell_price || 0) ||
                    0;
                if (!line.base_sell_price && basePrice > 0) {
                    line.base_sell_price = basePrice;
                }
                line.sell_price = basePrice * ratio;
            }
        }
        this._syncAvailablePricesForUom(line);
        this._recomputeLine(line);
        this._recomputeBill(this.currentBill);
        this.schedulePromoRefresh(this.currentBill);
        bill.updated_at = new Date().toISOString();
        this.persistCache();
    }

    async onStoreM2OUpdate(value) {
        const bill = this.currentBill;
        if (!bill) {
            return;
        }
        if (!value || !value.id) {
            bill.header.store_id = null;
            bill.header.store_name = "";
            bill.header.store_code = "";
            bill.header.store_ip = "";
        } else {
            const store = this.state.storeById[value.id];
            bill.header.store_id = value.id;
            bill.header.store_name = store?.name || value.display_name || "";
            bill.header.store_code = store?.code || "";
            bill.header.store_ip = store?.ip1 || "";
        }
        bill.updated_at = new Date().toISOString();
        this.persistCache();
        this.schedulePromoRefresh(bill);
        await this.refreshLineInventories(bill);
        if (this.state.productResults && this.state.productResults.length) {
            this.schedulePosBalanceRefresh(this.state.productResults, bill.header.store_id);
        }
        this.refreshStoreStatus(bill.header.store_id);
        this.refreshCustomerInsights(bill);
        this.searchProducts((this.state.productQuery || "").trim());
    }

    async onCustomerM2OUpdate(value) {
        const bill = this.currentBill;
        if (!bill) {
            return;
        }
        if (!value || !value.id) {
            bill.header.customer_id = null;
            bill.header.customer_name = "";
            bill.header.customer_address = "";
            bill.header.customer_mobile = "";
            bill.header.customer_phone = "";
            bill.header.customer_code = "";
            bill.header.invoice_address = "";
            bill.header.bill_customer_name = "";
            bill.header.bill_customer_phone = "";
            bill.header.bill_customer_address = "";
            bill.updated_at = new Date().toISOString();
            this.persistCache();
            this.refreshCustomerInsights(bill);
            this.searchProducts((this.state.productQuery || "").trim());
            return;
        }
        this.state.lastCustomerInput = "";
        this.state.lastCustomerInputFallback = "";
        try {
            const [cust] = await this.orm.read("ab_customer", [value.id], [
                "name",
                "code",
                "mobile_phone",
                "work_phone",
                "address",
            ]);
            bill.header.customer_id = value.id;
            bill.header.customer_name = cust?.name || value.display_name || "";
            bill.header.customer_address = cust?.address || "";
            bill.header.customer_mobile = cust?.mobile_phone || "";
            bill.header.customer_phone = cust?.work_phone || "";
            bill.header.customer_code = cust?.code || "";
            bill.header.invoice_address = cust?.address || "";
            bill.header.bill_customer_name = bill.header.customer_name || "";
            bill.header.bill_customer_phone =
                bill.header.customer_phone || bill.header.customer_mobile || "";
            bill.header.bill_customer_address = bill.header.invoice_address || "";
            bill.header.customer_mode = "current";
        } catch (err) {
            this.notification.add(err?.message || "Failed to load customer.", {type: "danger"});
        }
        bill.updated_at = new Date().toISOString();
        this.persistCache();
        this.refreshCustomerInsights(bill);
        this.searchProducts((this.state.productQuery || "").trim());
    }

    toggleStoreDetails() {
        this.state.showStoreDetails = !this.state.showStoreDetails;
    }

    toggleCustomerDetails() {
        this.state.showCustomerDetails = !this.state.showCustomerDetails;
    }

    toggleBillDetails() {
        this.state.showBillDetails = !this.state.showBillDetails;
    }

    toggleSidebar() {
        this.state.sidebarCollapsed = !this.state.sidebarCollapsed;
    }

    setCustomerMode(mode) {
        const bill = this.currentBill;
        if (!bill) {
            return;
        }
        bill.header.customer_mode = mode;
        if (mode === "current") {
            bill.header.new_customer_name = "";
            bill.header.new_customer_phone = "";
            bill.header.new_customer_address = "";
            this.state.customerQuery = bill.header.customer_name || "";
        } else {
            bill.header.customer_id = null;
            bill.header.customer_name = "";
            bill.header.customer_address = "";
            bill.header.customer_mobile = "";
            bill.header.customer_phone = "";
            bill.header.customer_code = "";
            bill.header.invoice_address = "";
            bill.header.bill_customer_name = "";
            bill.header.bill_customer_phone = "";
            bill.header.bill_customer_address = "";
            this.state.customerQuery = "";
        }
        this.state.customerResults = [];
        bill.updated_at = new Date().toISOString();
        this.persistCache();
        this.refreshCustomerInsights(bill);
        this.searchProducts((this.state.productQuery || "").trim());
    }

    onCustomerSearch(ev) {
        this.state.customerQuery = ev.target.value || "";
        if (this._customerSearchTimer) {
            clearTimeout(this._customerSearchTimer);
        }
        const query = this.state.customerQuery.trim();
        if (!query) {
            this.state.customerResults = [];
            return;
        }
        this._customerSearchTimer = setTimeout(async () => {
            await this.searchCustomers(query);
        }, 200);
    }

    async searchCustomers(query) {
        this.state.loadingCustomers = true;
        try {
            const domain = [
                "|",
                "|",
                ["name", "ilike", query],
                ["mobile_phone", "ilike", query],
                ["work_phone", "ilike", query],
            ];
            this.state.customerResults = await this.orm.searchRead("ab_customer", domain, [
                "name",
                "code",
                "mobile_phone",
                "work_phone",
                "address",
            ]);
        } catch (err) {
            this.notification.add(err?.message || "Failed to search customers.", {type: "danger"});
        } finally {
            this.state.loadingCustomers = false;
        }
    }

    selectCustomer(cust) {
        const bill = this.currentBill;
        if (!bill || !cust) {
            return;
        }
        this.state.lastCustomerInput = "";
        this.state.lastCustomerInputFallback = "";
        bill.header.customer_id = cust.id;
        bill.header.customer_name = cust.name || "";
        bill.header.customer_address = cust.address || "";
        bill.header.customer_mobile = cust.mobile_phone || "";
        bill.header.customer_phone = cust.work_phone || "";
        bill.header.customer_code = cust.code || "";
        bill.header.invoice_address = cust.address || "";
        bill.header.bill_customer_name = bill.header.customer_name || "";
        bill.header.bill_customer_phone = bill.header.customer_phone || bill.header.customer_mobile || "";
        bill.header.bill_customer_address = bill.header.invoice_address || "";
        bill.header.customer_mode = "current";
        this.state.customerResults = [];
        this.state.customerQuery = cust.name || "";
        bill.updated_at = new Date().toISOString();
        this.persistCache();
        this.refreshCustomerInsights(bill);
        this.searchProducts((this.state.productQuery || "").trim());
    }

    onProductHasBalanceChange(ev) {
        this.state.productHasBalanceOnly = !!ev.target.checked;
        this._savePosUiSettingsLocal(this._currentPosUiSettings());
        this.searchProducts(this.state.productQuery.trim());
    }

    onProductHasPosBalanceChange(ev) {
        this.state.productHasPosBalanceOnly = !!ev.target.checked;
        this._savePosUiSettingsLocal(this._currentPosUiSettings());
        this.searchProducts(this.state.productQuery.trim());
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
        const bill = this.currentBill;
        if (!bill) {
            this.state.productResults = [];
            this.state.selectionIndex = -1;
            return;
        }
        const storeId = bill?.header?.store_id || null;
        const customerPhone = this.activeCustomerPhone(bill);
        this.state.loadingProducts = true;
        try {
            const ctx = storeId ? {pos_store_id: storeId} : {};
            this.state.productResults = await this.orm.call(
                "ab_sales_ui_api",
                "search_products",
                [],
                {
                    query,
                    limit: 24,
                    has_balance: this.state.productHasBalanceOnly,
                    has_pos_balance: this.state.productHasPosBalanceOnly,
                    store_id: storeId,
                    customer_phone: customerPhone,
                    context: ctx,
                }
            );
            this.state.selectionIndex = -1;
            this.state.qtyBuffer = "";
            this.state.qtyBufferProductId = null;
            this.schedulePosBalanceRefresh(this.state.productResults, storeId);
        } catch (err) {
            this.notification.add(err?.message || "Failed to search products.", {type: "danger"});
        } finally {
            this.state.loadingProducts = false;
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
        }, 400);
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
                const list = this.state.productResults || [];
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

    scheduleLinePosBalanceRefresh(bill) {
        if (this._linePosBalanceTimer) {
            clearTimeout(this._linePosBalanceTimer);
        }
        const requestId = ++this._linePosBalanceRequestId;
        this._linePosBalanceTimer = setTimeout(() => {
            this._linePosBalanceTimer = null;
            this._refreshPosBalancesForLines(bill || this.currentBill, requestId);
        }, 400);
    }

    _refreshPosBalancesForLines(bill, requestId) {
        const target = bill || this.currentBill;
        const storeId = target?.header?.store_id;
        if (!storeId || !target || !Array.isArray(target.lines) || !target.lines.length) {
            return;
        }
        const productIds = target.lines
            .map((row) => row?.product_id)
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
                if (requestId !== this._linePosBalanceRequestId) {
                    return;
                }
                if (!balances || typeof balances !== "object") {
                    return;
                }
                for (const line of target.lines) {
                    const balance = balances[line.product_id];
                    if (balance === undefined) {
                        continue;
                    }
                    const val = parseFloat(balance || 0) || 0;
                    line.pos_balance = val;
                }
            })
            .catch(() => {});
    }

    refreshLinePosBalance(line) {
        const bill = this.currentBill;
        const storeId = bill?.header?.store_id;
        const productId = line?.product_id;
        if (!storeId || !productId) {
            return;
        }
        this.orm
            .call("ab_sales_pos_api", "pos_refresh_pos_balances", [], {
                store_id: storeId,
                product_ids: [productId],
            })
            .then((balances) => {
                if (!balances || typeof balances !== "object") {
                    return;
                }
                const balance = balances[productId];
                if (balance === undefined) {
                    return;
                }
                line.pos_balance = parseFloat(balance || 0) || 0;
            })
            .catch(() => {});
    }

    refreshStoreStatus(storeId) {
        if (!storeId) {
            this.state.storeOnline = null;
            return;
        }
        const requestId = ++this._storeStatusRequestId;
        this.state.storeOnline = null;
        this.orm
            .call("ab_sales_ui_api", "pos_store_status", [], {store_id: storeId})
            .then((status) => {
                if (requestId !== this._storeStatusRequestId) {
                    return;
                }
                this.state.storeOnline = !!status;
            })
            .catch(() => {
                if (requestId !== this._storeStatusRequestId) {
                    return;
                }
                this.state.storeOnline = false;
            });
    }

    _extractUomInfo(product) {
        let uomId = null;
        let uomName = "";
        let uomFactor = parseFloat(product?.uom_factor || product?.default_uom_factor || 0) || 0;
        const rawUom = product?.uom_id;
        if (Array.isArray(rawUom)) {
            uomId = rawUom[0] || null;
            uomName = rawUom[1] || "";
        } else if (rawUom && typeof rawUom === "object") {
            uomId = rawUom.id || null;
            uomName = rawUom.display_name || rawUom.name || "";
        } else if (Number.isFinite(rawUom)) {
            uomId = rawUom;
        }

        let uomCategoryId = null;
        const rawCategory = product?.uom_category_id;
        if (Array.isArray(rawCategory)) {
            uomCategoryId = rawCategory[0] || null;
        } else if (rawCategory && typeof rawCategory === "object") {
            uomCategoryId = rawCategory.id || null;
        } else if (Number.isFinite(rawCategory)) {
            uomCategoryId = rawCategory;
        }

        if (uomId && uomFactor > 0) {
            this._uomFactorCache.set(uomId, uomFactor);
        }
        return {uomId, uomName, uomCategoryId, uomFactor};
    }

    _syncAvailablePricesForUom(line) {
        if (!line) {
            return;
        }
        const baseList = Array.isArray(line.available_prices_base)
            ? line.available_prices_base
            : Array.isArray(line.available_prices)
                ? line.available_prices
                : [];
        const defaultFactor = parseFloat(line.default_uom_factor || 0) || 0;
        const selectedFactor = parseFloat(line.uom_factor || 0) || 0;
        let ratio = 1;
        if (defaultFactor > 0 && selectedFactor > 0) {
            ratio = selectedFactor / defaultFactor;
        }
            line.available_prices = baseList.map((row) => {
                const price = parseFloat(row?.price || 0) || 0;
                return {
                ...row,
                price: price * ratio,
            };
        });
    }

    addProduct(product, qty = 1) {
        const bill = this.currentBill;
        if (!bill || !product?.id) {
            return null;
        }
        const existing = bill.lines.find((l) => l.product_id === product.id);
        if (existing) {
            const currentQty = parseQtyExpression(existing.qty_str);
            existing.qty_str = String((currentQty || 0) + qty);
            this._recomputeLine(existing);
            this._recomputeBill(bill);
            this.schedulePromoRefresh(bill);
            this.scheduleLinePosBalanceRefresh(bill);
            return existing;
        } else {
            const {uomId, uomName, uomCategoryId, uomFactor} = this._extractUomInfo(product);
            const defaultPrice = product.default_price || 0;
            const line = {
                id: generateId("line"),
                product_id: product.id,
                product_name: product.name || product.product_card_name || "",
                product_code: product.code || "",
                qty_str: String(qty),
                qty,
                sell_price: defaultPrice,
                sell_price_str: String(defaultPrice),
                balance: product.balance || 0,
                balance_total: product.balance || 0,
                pos_balance: product.pos_balance || 0,
                cost: 0,
                target_sell_price: 0,
                net_amount: defaultPrice * qty,
                available_prices: [],
                available_prices_base: [],
                inventory_table_html: "",
                show_details: false,
                loading_details: false,
                uom_id: uomId,
                uom_name: uomName,
                uom_category_id: uomCategoryId,
                uom_factor: uomFactor || 0,
                default_uom_id: uomId,
                default_uom_factor: uomFactor || 1,
                default_sell_price: defaultPrice,
                base_sell_price: defaultPrice,
            };
            bill.lines.push(line);
            this.loadLineDetails(line);
            this._recomputeBill(bill);
            this.schedulePromoRefresh(bill);
            this.scheduleLinePosBalanceRefresh(bill);
            return line;
        }
    }

    addProductAndFocus(product, qty = 1) {
        const line = this.addProduct(product, qty);
        if (this.searchInputRef.el) {
            this.searchInputRef.el.blur();
        }
        if (document.activeElement && document.activeElement !== document.body) {
            document.activeElement.blur?.();
        }
        this._focusLineQty(line);
        setTimeout(() => {
            const active = document.activeElement;
            if (active?.matches?.('input[data-field="qty_str"]')) {
                try {
                    active.focus();
                    if (typeof active.select === "function") {
                        active.select();
                    }
                    if (typeof active.setSelectionRange === "function") {
                        active.setSelectionRange(0, active.value?.length || 0);
                    }
                } catch {
                    // Ignore selection errors for non-text inputs.
                }
            }
        }, 60);
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

    _onHotkeyEnter(ev, {isSearchFocused, products} = {}) {
        if (isSearchFocused) {
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
        this.addProductAndFocus(product, qty);

        const container = this.cardsContainerRef.el;
        const card = container?.querySelector?.(`[data-product-id="${product.id}"]`);
        card?.focus?.();
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
            if (container && product) {
                const card = container.querySelector(`[data-product-id="${product.id}"]`);
                card?.scrollIntoView?.({block: "nearest"});
                card?.focus?.();
            }
        }
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
            ev.stopImmediatePropagation();
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
        ev.stopImmediatePropagation();
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
        const bill = this.currentBill;
        if (!bill) {
            this.notification.add("Create a bill before scanning.", {type: "warning"});
            return;
        }
        this.state.loadingProducts = true;
        try {
            const storeId = bill.header?.store_id || false;
            const products = await this._fetchBarcodeProducts(barcode, storeId);
            this._applyBarcodeResults(barcode, products);
            if (!products.length) {
                this._openBarcodeLinkDialog(barcode);
                return;
            }
            if (products.length === 1) {
                this.addProductAndFocus(products[0], 1);
            }
        } catch (err) {
            this.notification.add(err?.message || "Barcode scan failed.", {type: "danger"});
        } finally {
            this.state.loadingProducts = false;
        }
    }

    async _fetchBarcodeProducts(barcode, storeId) {
        const products = await this.orm.call("ab_sales_pos_api", "pos_barcode_products", [], {
            barcode,
            store_id: storeId || false,
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
        this.dialog.add(AbSalesPosBarcodeLinkDialog, {
            barcode,
            allowEdit: false,
            onSave: async ({barcode: linkBarcode, productIds}) => {
                await this._linkBarcodeProducts(linkBarcode, productIds);
            },
        });
    }

    _openBarcodeRegisterDialog() {
        this.dialog.add(AbSalesPosBarcodeLinkDialog, {
            barcode: "",
            allowEdit: true,
            onSave: async ({barcode: linkBarcode, productIds}) => {
                await this._linkBarcodeProducts(linkBarcode, productIds);
            },
        });
    }

    async _linkBarcodeProducts(barcode, productIds) {
        try {
            const result = await this.orm.call("ab_sales_pos_api", "pos_link_barcode_temp", [], {
                barcode,
                product_ids: productIds,
            });
            const count = Array.isArray(result?.product_ids) ? result.product_ids.length : 0;
            this.notification.add(`Barcode links saved (${count} product(s)).`, {type: "success"});
            const bill = this.currentBill;
            if (bill) {
                const storeId = bill.header?.store_id || false;
                const products = await this._fetchBarcodeProducts(barcode, storeId);
                this._applyBarcodeResults(barcode, products);
                if (products.length === 1) {
                    this.addProductAndFocus(products[0], 1);
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
        this._clearLineFocusObserver();
        const findInput = () => {
            const root = this.el || document.querySelector(".o_ab_sales_pos_window");
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
                    if (typeof input.select === "function") {
                        input.select();
                    }
                    if (typeof input.setSelectionRange === "function") {
                        input.setSelectionRange(0, input.value?.length || 0);
                    }
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

        const immediate = findInput();
        if (focusInput(immediate)) {
            return;
        }

        const observerTarget =
            document.querySelector(".o_ab_sales_pos_lines_table tbody") || document.body;
        this._lineFocusObserver = new MutationObserver(() => {
            const next = findInput();
            if (focusInput(next)) {
                this._clearLineFocusObserver();
            }
        });
        this._lineFocusObserver.observe(observerTarget, {childList: true, subtree: true});
        this._lineFocusTimer = setTimeout(() => {
            this._clearLineFocusObserver();
        }, 2500);
    }

    onKeydown(ev) {
        if (this._handleBarcodeKeydown(ev)) {
            return;
        }
        if (ev.key === "F2") {
            if (!document.body.classList.contains("modal-open")) {
                ev.preventDefault();
                ev.stopPropagation();
                const input = this.searchInputRef.el;
                if (input) {
                    input.focus();
                    if (typeof input.select === "function") {
                        input.select();
                    }
                    if (typeof input.setSelectionRange === "function") {
                        input.setSelectionRange(0, input.value?.length || 0);
                    }
                }
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
                this.submitCurrentBill();
            }
            return;
        }
        if (this.state.loadingProducts || this.state.submitting) {
            return;
        }
        if (document.body.classList.contains("modal-open")) {
            return;
        }
        const key = ev.key;
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

        const handler = this.shortcutHandlers.get(key);
        if (!handler) {
            return;
        }
        handler(ev, {isSearchFocused, products});
    }

    updateLineQty(line, value) {
        line.qty_str = value;
        this._recomputeLine(line);
        this._recomputeBill(this.currentBill);
        this.schedulePromoRefresh(this.currentBill);
    }

    updateLineSellPrice(line, value) {
        line.sell_price_str = value;
        const price = parseFloat(value || 0) || 0;
        line.sell_price = price;
        if (line.default_uom_id && line.uom_id === line.default_uom_id) {
            line.base_sell_price = price;
        }
        this._recomputeLine(line);
        this._recomputeBill(this.currentBill);
        this.schedulePromoRefresh(this.currentBill);
    }

    updateLineTargetPrice(line, value) {
        line.target_sell_price = parseFloat(value || 0) || 0;
        this._recomputeBill(this.currentBill);
    }

    onAvailablePriceSelect(line, priceValue) {
        const price = parseFloat(priceValue || "");
        if (!Number.isFinite(price)) {
            return;
        }
        line.sell_price = price;
        line.sell_price_str = String(price);
        if (line.default_uom_id && line.uom_id === line.default_uom_id) {
            line.base_sell_price = price;
        }
        this._recomputeLine(line);
        this._recomputeBill(this.currentBill);
    }

    removeLine(line) {
        const bill = this.currentBill;
        if (!bill) {
            return;
        }
        bill.lines = bill.lines.filter((l) => l.id !== line.id);
        this.scheduleLinePosBalanceRefresh(bill);
        this._recomputeBill(bill);
        this.schedulePromoRefresh(bill);
    }

    schedulePromoRefresh(bill) {
        if (this._promoDisabled) {
            return;
        }
        const target = bill || this.currentBill;
        if (!target) {
            return;
        }
        if (this._promoTimer) {
            clearTimeout(this._promoTimer);
        }
        this._promoTimer = setTimeout(() => {
            this.refreshPromotions(target);
        }, 350);
    }

    _resetPromotions(bill) {
        if (!bill) {
            return;
        }
        bill.promo = this._defaultPromo();
        bill.total_net_amount = bill.total_price || 0;
        this.persistCache();
    }

    _promoPayloadLines(bill) {
        const lines = bill?.lines || [];
        return lines
            .filter((line) => line.product_id)
            .map((line) => ({
                product_id: line.product_id,
                qty_str: line.qty_str || DEFAULT_QTY,
                sell_price: line.sell_price,
                uom_id: line.uom_id || false,
            }));
    }

    _findPromoName(promos, promoId) {
        if (!promoId) {
            return "";
        }
        const match = (promos || []).find((promo) => promo.id === promoId);
        return match?.display_name || match?.name || "";
    }

    async refreshPromotions(bill) {
        if (this._promoDisabled) {
            return;
        }
        const target = bill || this.currentBill;
        if (!target) {
            return;
        }
        if (!target.promo) {
            target.promo = this._defaultPromo();
        }
        this._promoTimer = null;
        const storeId = target.header?.store_id;
        const payloadLines = this._promoPayloadLines(target);
        if (!storeId || !payloadLines.length) {
            this._resetPromotions(target);
            return;
        }
        const requestId = ++this._promoRequestId;
        target.promo.loading = true;
        this.persistCache();
        try {
            const result = await this.orm.call("ab_sales_pos_api", "pos_promotions", [], {
                store_id: storeId,
                lines: payloadLines,
                applied_program_id: target.promo.selected_id || false,
                manual_clear: !!target.promo.manual_clear,
            });
            if (requestId !== this._promoRequestId) {
                return;
            }
            target.promo.available = Array.isArray(result?.available_programs) ? result.available_programs : [];
            const appliedId = parseInt(result?.applied_program_id, 10);
            const selectedId = parseInt(result?.selected_program_id, 10);
            target.promo.applied_id = Number.isFinite(appliedId) ? appliedId : null;
            target.promo.applied_name =
                result?.applied_program_name || this._findPromoName(target.promo.available, target.promo.applied_id);
            target.promo.selected_id = Number.isFinite(selectedId) ? selectedId : null;
            target.promo.selected_name =
                result?.selected_program_name || this._findPromoName(target.promo.available, target.promo.selected_id);
            target.promo.message = result?.promo_message || "";
            target.promo.discount_amount = parseFloat(result?.promo_discount_amount || 0) || 0;
            target.promo.total_after = parseFloat(result?.amount_total_after_promo || 0) || 0;
            const totalNetAmount = parseFloat(result?.total_net_amount);
            if (Number.isFinite(totalNetAmount)) {
                target.promo.total_net_amount = totalNetAmount;
                target.total_net_amount = totalNetAmount;
            } else {
                target.promo.total_net_amount = target.total_price || 0;
                target.total_net_amount = target.total_price || 0;
            }
        } catch (err) {
            const message = err?.message || "";
            if (message.includes("does not exist")) {
                this._promoDisabled = true;
                this._resetPromotions(target);
            } else {
                this.notification.add(message || "Failed to load promotions.", {type: "warning"});
            }
        } finally {
            if (requestId === this._promoRequestId) {
                target.promo.loading = false;
                this.persistCache();
            }
        }
    }

    selectPromotion(program) {
        const bill = this.currentBill;
        if (!bill || !program) {
            return;
        }
        const programId = parseInt(program.id, 10);
        if (!Number.isFinite(programId)) {
            return;
        }
        if (bill.promo.selected_id === programId) {
            bill.promo.selected_id = null;
            bill.promo.selected_name = "";
        } else {
            bill.promo.selected_id = programId;
            bill.promo.selected_name = program.display_name || program.name || "";
        }
        bill.promo.manual_clear = false;
        if (bill.promo.applied_id !== bill.promo.selected_id) {
            bill.promo.applied_id = null;
            bill.promo.applied_name = "";
        }
        bill.updated_at = new Date().toISOString();
        this.persistCache();
        this.refreshPromotions(bill);
    }

    clearPromotion() {
        const bill = this.currentBill;
        if (!bill) {
            return;
        }
        bill.promo.applied_id = null;
        bill.promo.applied_name = "";
        bill.promo.selected_id = null;
        bill.promo.selected_name = "";
        bill.promo.manual_clear = true;
        bill.updated_at = new Date().toISOString();
        this.persistCache();
        this.refreshPromotions(bill);
    }

    async refreshLineInventories(bill) {
        const target = bill || this.currentBill;
        const storeId = target?.header?.store_id;
        const lines = target?.lines || [];
        if (!storeId || !lines.length) {
            return;
        }
        for (const line of lines) {
            if (!line?.product_id) {
                continue;
            }
            await this.loadLineDetails(line, {silent: true});
        }
        this.scheduleLinePosBalanceRefresh(target);
    }

    async loadLineDetails(line, options = {}) {
        const bill = this.currentBill;
        const storeId = bill?.header?.store_id;
        if (!storeId || !line?.product_id) {
            return;
        }
        line.loading_details = true;
        try {
            const details = await this.orm.call("ab_sales_pos_api", "pos_product_details", [], {
                store_id: storeId,
                product_id: line.product_id,
            });
            line.balance = details.balance || 0;
            const totalBalance = Number.isFinite(details?.total_balance)
                ? details.total_balance
                : parseFloat(details?.total_balance || NaN);
            if (Number.isFinite(totalBalance)) {
                line.balance_total = totalBalance;
            } else if (!Number.isFinite(line.balance_total)) {
                line.balance_total = line.balance;
            }
            const posBalance = Number.isFinite(details?.pos_balance)
                ? details.pos_balance
                : parseFloat(details?.pos_balance || NaN);
            if (Number.isFinite(posBalance)) {
                line.pos_balance = posBalance;
            }
            line.cost = details.cost || 0;
            const defaultUomId = details.default_uom_id || details.uom_id || null;
            const defaultUomFactor = parseFloat(details.default_uom_factor || details.uom_factor || 0) || 0;
            if (defaultUomId && defaultUomFactor > 0) {
                this._uomFactorCache.set(defaultUomId, defaultUomFactor);
            }
            line.default_uom_id = line.default_uom_id || defaultUomId;
            if (defaultUomFactor > 0) {
                line.default_uom_factor = defaultUomFactor;
            } else if (!line.default_uom_factor) {
                line.default_uom_factor = 1;
            }
            if (line.default_uom_id && line.default_uom_factor > 0) {
                this._uomFactorCache.set(line.default_uom_id, line.default_uom_factor);
            }
            const shouldSyncPrice = !line.uom_id || line.uom_id === defaultUomId || !line.base_sell_price;
            if (shouldSyncPrice && Number.isFinite(details.sell_price)) {
                line.sell_price = details.sell_price;
                line.sell_price_str = String(details.sell_price);
            }
            if (Number.isFinite(details.default_price)) {
                line.default_sell_price = details.default_price;
            }
            if (!line.base_sell_price) {
                line.base_sell_price = line.default_sell_price || line.sell_price || 0;
            }
            line.available_prices_base = Array.isArray(details.available_prices) ? details.available_prices : [];
            line.inventory_table_html = details.inventory_table_html || "";
            if (details.uom_id) {
                if (!line.uom_id || line.uom_id === details.uom_id) {
                    line.uom_id = details.uom_id;
                    line.uom_name = details.uom_name || line.uom_name || "";
                }
                if (details.uom_factor) {
                    const uomFactor = parseFloat(details.uom_factor || 0) || 0;
                    this._uomFactorCache.set(details.uom_id, uomFactor);
                    if (uomFactor > 0 && line.uom_id === details.uom_id) {
                        line.uom_factor = uomFactor;
                    }
                }
            }
            if (details.uom_category_id && !line.uom_category_id) {
                line.uom_category_id = details.uom_category_id;
            }
            this._syncAvailablePricesForUom(line);
            this._recomputeLine(line);
            this._recomputeBill(this.currentBill);
            this.schedulePromoRefresh(this.currentBill);
        } catch (err) {
            if (!options?.silent) {
                this.notification.add(err?.message || "Failed to load line details.", {type: "danger"});
            }
        } finally {
            line.loading_details = false;
        }
    }

    _recomputeLine(line) {
        line.qty = parseQtyExpression(line.qty_str);
        line.net_amount = (line.qty || 0) * (line.sell_price || 0);
    }

    _recomputeBill(bill, {persist = true} = {}) {
        if (!bill) {
            return;
        }
        let total = 0;
        for (const line of bill.lines) {
            total += line.net_amount || 0;
        }
        bill.number_of_products = bill.lines.length;
        bill.total_price = total;
        bill.total_net_amount = total;
        bill.updated_at = new Date().toISOString();
        if (persist) {
            this.persistCache();
        }
    }

    formatPrice(value) {
        return this._formatCompactNumber(value, 2);
    }

    formatQty(value) {
        return this._formatCompactNumber(value, 2);
    }

    formatMoney2(value) {
        const numberValue = typeof value === "number" ? value : parseFloat(value ?? 0);
        if (!Number.isFinite(numberValue)) {
            return "0.00";
        }
        return numberValue.toFixed(2);
    }

    _formatCompactNumber(value, decimals = 2) {
        const numberValue = typeof value === "number" ? value : parseFloat(value ?? 0);
        if (!Number.isFinite(numberValue)) {
            return "0";
        }
        const fixed = numberValue.toFixed(decimals);
        return fixed.replace(/(?:\.0+|(\.\d*?)0+)$/, "$1");
    }

    formatDateTime(value) {
        if (!value) {
            return "-";
        }
        try {
            const dt = new Date(value);
            return `${dt.toLocaleDateString()} ${dt.toLocaleTimeString()}`;
        } catch {
            return value;
        }
    }

    _getRpcErrorMessage(err) {
        if (!err) {
            return "Submit failed.";
        }
        const data = err.data || err?.response?.data || {};
        const rpcArgs = data?.["arguments"];
        return (
            (Array.isArray(rpcArgs) && rpcArgs[0]) ||
            data?.message ||
            err.message ||
            "Submit failed."
        );
    }

    productLabel(product) {
        return product.name || product.product_card_name || `${product.code || ""}`.trim() || `#${product.id}`;
    }

    openStoresBalance(product) {
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

    async openBillWizard() {
        this.action.doAction({
            type: "ir.actions.client",
            name: "Bill Wizard",
            tag: "ab_sales.bill_wizard",
        });
    }

    async submitCurrentBill() {
        const bill = this.currentBill;
        if (!bill || this.state.submitting) {
            return;
        }
        if (document.body.classList.contains("modal-open")) {
            return;
        }
        this._openSubmitDialog(bill);
    }

    async _submitBillInternal(bill) {
        if (!bill) {
            return;
        }
        if (this.state.submitting) {
            return;
        }
        this.state.submitting = true;
        const storeId = bill.header?.store_id;
        try {
            const header = this._buildSubmitHeader(bill);
            const lines = bill.lines.map((line) => ({
                product_id: line.product_id,
                qty_str: line.qty_str || DEFAULT_QTY,
                sell_price: line.sell_price,
                target_sell_price: line.target_sell_price,
                uom_id: line.uom_id || false,
            }));
            const result = await this.orm.call("ab_sales_pos_api", "pos_submit", [], {
                header,
                lines,
                applied_program_id: bill.promo?.applied_id || false,
                on_existing_token: "warn",
            });
            if (result?.duplicate_token) {
                this._openDuplicateTokenDialog(bill, result);
                return;
            }
            if (result?.type === "ir.actions.act_window") {
                const headerId = result.pos_header_id;
                if (!result.views) {
                    const mode = (result.view_mode || "form").split(",")[0];
                    result.views = [[result.view_id || false, mode]];
                }
                this.action.doAction(result, {
                    onClose: async () => {
                        if (!headerId) {
                            return;
                        }
                        const rows = await this.orm.read("ab_sales_header", [headerId], ["status"]);
                        const status = rows?.[0]?.status;
                        if (status && status !== "prepending") {
                            this.removeBill(bill.id);
                            if (storeId) {
                                this.createNewBill(storeId);
                                if (this.state.productResults && this.state.productResults.length) {
                                    this.schedulePosBalanceRefresh(this.state.productResults, storeId);
                                }
                            }
                        }
                    },
                });
                return;
            }
            this.notification.add(
                `Submitted invoice #${result?.eplus_serial || result?.id || ""}`,
                {type: "success"}
            );
            this.removeBill(bill.id);
            if (storeId) {
                this.createNewBill(storeId);
                if (this.state.productResults && this.state.productResults.length) {
                    this.schedulePosBalanceRefresh(this.state.productResults, storeId);
                }
            }
        } catch (err) {
            const message = this._getRpcErrorMessage(err);
            const data = err?.data || err?.response?.data || {};
            const errorName = data?.name || "";
            const title = errorName.includes("ValidationError")
                ? "Validation Error"
                : errorName.includes("UserError")
                    ? "Warning"
                    : "Submit failed";
            this._openSubmitErrorDialog(message, title);
        } finally {
            this.state.submitting = false;
        }
    }

    onResizeStart(ev) {
        const grid = this.productGridRef.el;
        if (!grid) {
            return;
        }
        ev.preventDefault();
        const rect = grid.getBoundingClientRect();
        const minPct = POS_PRODUCT_COL_MIN;
        const maxPct = POS_PRODUCT_COL_MAX;
        const rootEl = this.el || grid;
        const onMove = (moveEv) => {
            const clientX = moveEv.clientX;
            if (!clientX) {
                return;
            }
            const min = (minPct / 100) * rect.width;
            const max = (maxPct / 100) * rect.width;
            let offset = clientX - rect.left;
            if (offset < min) {
                offset = min;
            }
            if (offset > max) {
                offset = max;
            }
            const pct = (offset / rect.width) * 100;
            rootEl.style.setProperty("--pos-product-col", `${pct}%`);
            document.body.style.cursor = "col-resize";
        };
        const onUp = () => {
            window.removeEventListener("pointermove", onMove);
            window.removeEventListener("pointerup", onUp);
            window.removeEventListener("pointercancel", onUp);
            document.body.style.cursor = "";
            this.state.productColumnPercent = this._readProductColumnPercent();
            this._savePosUiSettingsLocal(this._currentPosUiSettings());
        };
        window.addEventListener("pointermove", onMove);
        window.addEventListener("pointerup", onUp);
        window.addEventListener("pointercancel", onUp);
    }

    onSidebarResizeStart(ev) {
        if (this.state.sidebarCollapsed) {
            return;
        }
        const sidebar = this.el?.querySelector?.(".o_ab_sales_pos_sidebar");
        const rootEl = this.el?.querySelector?.(".o_ab_sales_pos_app") || this.el;
        if (!sidebar || !rootEl) {
            return;
        }
        ev.preventDefault();
        const rect = sidebar.getBoundingClientRect();
        const startX = ev.clientX;
        const startWidth = rect.width;
        const minWidth = 220;
        const maxWidth = 420;
        const onMove = (moveEv) => {
            const clientX = moveEv.clientX;
            if (!clientX) {
                return;
            }
            let nextWidth = startWidth + (clientX - startX);
            if (nextWidth < minWidth) {
                nextWidth = minWidth;
            }
            if (nextWidth > maxWidth) {
                nextWidth = maxWidth;
            }
            rootEl.style.setProperty("--pos-sidebar-width", `${Math.round(nextWidth)}px`);
            document.body.style.cursor = "col-resize";
        };
        const onUp = () => {
            window.removeEventListener("pointermove", onMove);
            window.removeEventListener("pointerup", onUp);
            window.removeEventListener("pointercancel", onUp);
            document.body.style.cursor = "";
        };
        window.addEventListener("pointermove", onMove);
        window.addEventListener("pointerup", onUp);
        window.addEventListener("pointercancel", onUp);
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

    _syncWindowToViewport() {
        const viewport = getViewportRect();
        if (this.state.windowMaximized) {
            this.state.windowRect = {
                left: 0,
                top: 0,
                width: viewport.width,
                height: viewport.height,
            };
        }
        this._applyPosScale();
    }

    _applyPosScale() {
        const elements = document.querySelectorAll(
            ".o_ab_sales_pos_header_row, .o_ab_sales_pos_layout, .o_ab_sales_pos_topbar"
        );
        elements.forEach((el) => {
            if (window.innerWidth <= POS_SCALE_BREAKPOINT) {
                el.style.transform = `scale(${POS_SCALE_VALUE})`;
                el.style.transformOrigin = "top left";
            } else {
                el.style.transform = "scale(1)";
                el.style.transformOrigin = "";
            }
        });
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

registry.category("actions").add("ab_sales.pos", AbSalesPosAction);
