/** @odoo-module **/

import {registry} from "@web/core/registry";
import {Component, onMounted, onWillStart, useRef, useState} from "@odoo/owl";
import {useService} from "@web/core/utils/hooks";
import {AbSalesBillWizardPrintDialog} from "./print_dialog";

const openBillWizardPrintWindow = (html, format = "a4", {focus = true} = {}) => {
    const specs = format === "pos_80mm" ? "width=360,height=900" : "width=900,height=720";
    const win = window.open("", "_blank", specs);
    if (!win) {
        return null;
    }
    win.document.open();
    win.document.write(String(html || ""));
    win.document.close();
    if (focus) {
        win.focus();
    }
    return win;
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

class AbSalesBillWizardAction extends Component {
    static template = "ab_sales.BillWizardAction";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.dialog = useService("dialog");
        this._loadPrintOptionsPromise = null;

        this.productSearchInputRef = useRef("productSearchInput");

        this.state = useState({
            filters: {
                productQuery: "",
                customerQuery: "",
                eplusSerial: "",
                dateStart: "",
                dateEnd: "",
            },
            pagination: {
                page: 1,
                perPage: 20,
                pageCount: 1,
                totalCount: 0,
            },
            items: [],
            selectedId: null,
            details: null,
            notesDraft: "",
            isSearch: false,
            loadingList: false,
            loadingDetails: false,
            savingNotes: false,
            openingReturn: false,
            loadingPrintOptions: false,
            printerId: 0,
            printerName: "",
            receiptHeader: "Sales Receipt",
            receiptFooter: "Thank you.",
            availablePrinters: [],
            defaultPrintFormat: "a4",
        });

        this.onFilterInput = this.onFilterInput.bind(this);
        this.onFilterKeydown = this.onFilterKeydown.bind(this);
        this.applyFilters = this.applyFilters.bind(this);
        this.resetFilters = this.resetFilters.bind(this);
        this.goToPreviousPage = this.goToPreviousPage.bind(this);
        this.goToNextPage = this.goToNextPage.bind(this);
        this.loadBills = this.loadBills.bind(this);
        this.selectBill = this.selectBill.bind(this);
        this.loadDetails = this.loadDetails.bind(this);
        this.saveNotes = this.saveNotes.bind(this);
        this.openReturn = this.openReturn.bind(this);
        this.printReceipt = this.printReceipt.bind(this);
        this.previewReceipt = this.previewReceipt.bind(this);
        this.loadPrintOptions = this.loadPrintOptions.bind(this);
        this.discoverServerSharedPrinters = this.discoverServerSharedPrinters.bind(this);
        this.openPrintDialog = this.openPrintDialog.bind(this);
        this.formatMoney = this.formatMoney.bind(this);
        this.formatDateTime = this.formatDateTime.bind(this);

        onWillStart(async () => {
            await this.loadPrintOptions({silent: true});
            await this.loadBills();
        });
        onMounted(() => {
            this.productSearchInputRef.el?.focus?.();
        });
    }

    _searchPayload(page = null) {
        const targetPage = Math.max(1, parseInt(page || this.state.pagination.page || 1, 10) || 1);
        return {
            product_query: (this.state.filters.productQuery || "").trim(),
            customer_query: (this.state.filters.customerQuery || "").trim(),
            eplus_serial: (this.state.filters.eplusSerial || "").trim(),
            date_start: this.state.filters.dateStart || false,
            date_end: this.state.filters.dateEnd || false,
            page: targetPage,
            per_page: 20,
        };
    }

    _getErrorMessage(err, fallbackMessage) {
        const fallback = fallbackMessage || "Unexpected error.";
        const blocked = new Set(["odoo server error", "rpc_error"]);
        const normalize = (msg) => String(msg || "").trim();
        const safe = (msg) => {
            const text = normalize(msg);
            if (!text) {
                return "";
            }
            if (blocked.has(text.toLowerCase())) {
                return "";
            }
            return text;
        };

        const directCandidates = [
            err?.data?.message,
            Array.isArray(err?.data?.arguments) ? err.data.arguments[0] : "",
            err?.cause?.data?.message,
            Array.isArray(err?.cause?.data?.arguments) ? err.cause.data.arguments[0] : "",
            err?.message,
        ];
        for (const candidate of directCandidates) {
            const msg = safe(candidate);
            if (msg) {
                return msg;
            }
        }

        const debug = normalize(err?.data?.debug || err?.cause?.data?.debug || "");
        if (debug) {
            const quotedMatch = debug.match(/(?:UserError|ValidationError)\((['"])([\s\S]*?)\1\)/);
            if (quotedMatch && quotedMatch[2]) {
                const parsed = safe(quotedMatch[2]);
                if (parsed) {
                    return parsed;
                }
            }
            const plainMatch = debug.match(/(?:UserError|ValidationError):\s*([^\n\r]+)/);
            if (plainMatch && plainMatch[1]) {
                const parsed = safe(plainMatch[1]);
                if (parsed) {
                    return parsed;
                }
            }
        }
        return fallback;
    }

    async loadPrintOptions({silent = false} = {}) {
        if (this._loadPrintOptionsPromise) {
            return this._loadPrintOptionsPromise;
        }

        this._loadPrintOptionsPromise = (async () => {
            this.state.loadingPrintOptions = true;
            try {
                const result = await this.orm.call("ab_sales_ui_api", "bill_wizard_get_print_options", [], {});
                const printerRecords = normalizePrinterRecords(result?.available_printer_records);
                this.state.availablePrinters = printerRecords;

                const selectedId = Number.parseInt(result?.printer_id || 0, 10) || 0;
                const selected = findPrinterById(printerRecords, selectedId);
                this.state.printerId = selected ? selected.id : 0;
                this.state.printerName = selected?.label || String(result?.printer_name || "").trim();
                this.state.defaultPrintFormat = selected?.paper_size || (result?.print_format === "pos_80mm" ? "pos_80mm" : "a4");
                this.state.receiptHeader = result?.receipt_header || "Sales Receipt";
                this.state.receiptFooter = result?.receipt_footer || "Thank you.";
                return printerRecords;
            } catch (err) {
                if (!silent) {
                    this.notification.add(this._getErrorMessage(err, "Failed to load printer options."), {type: "warning"});
                }
                return this.state.availablePrinters;
            } finally {
                this.state.loadingPrintOptions = false;
                this._loadPrintOptionsPromise = null;
            }
        })();

        return this._loadPrintOptionsPromise;
    }

    async discoverServerSharedPrinters(startIp, endIp) {
        const startText = String(startIp || "").trim();
        const endText = String(endIp || "").trim();
        if (!startText || !endText) {
            this.notification.add("Start IP and End IP are required.", {type: "warning"});
            return this.state.availablePrinters || [];
        }
        try {
            const result = await this.orm.call("ab_sales_ui_api", "bill_wizard_discover_shared_printers", [], {
                start_ip: startText,
                end_ip: endText,
            });
            const printers = normalizePrinterRecords(result?.available_printer_records);
            if (printers.length) {
                this.state.availablePrinters = printers;
            }
            const selected = findPrinterById(this.state.availablePrinters, this.state.printerId);
            if (selected) {
                this.state.printerName = selected.label;
                this.state.defaultPrintFormat = selected.paper_size;
            }

            const installedCount = parseInt(result?.installed_count || 0, 10) || 0;
            const discoveredCount = parseInt(result?.discovered_count || 0, 10) || 0;
            this.notification.add(
                `Discovery completed. Discovered ${discoveredCount}, installed ${installedCount}.`,
                {type: "success"}
            );
            return this.state.availablePrinters || [];
        } catch (err) {
            this.notification.add(this._getErrorMessage(err, "Printer discovery failed."), {type: "danger"});
            return this.state.availablePrinters || [];
        }
    }

    async loadBills({page = null} = {}) {
        if (this.state.loadingList) {
            return;
        }
        this.state.loadingList = true;
        try {
            const result = await this.orm.call(
                "ab_sales_ui_api",
                "bill_wizard_search",
                [],
                this._searchPayload(page)
            );
            const items = Array.isArray(result?.items) ? result.items : [];
            this.state.items = items;
            this.state.isSearch = !!result?.is_search;
            const pagination = result?.pagination || {};
            this.state.pagination.page = Math.max(1, parseInt(pagination.page || 1, 10) || 1);
            this.state.pagination.perPage = Math.max(1, parseInt(pagination.per_page || 20, 10) || 20);
            this.state.pagination.pageCount = Math.max(1, parseInt(pagination.page_count || 1, 10) || 1);
            this.state.pagination.totalCount = Math.max(0, parseInt(pagination.total_count || 0, 10) || 0);

            const selectedStillExists = items.some((row) => row.id === this.state.selectedId);
            if (!selectedStillExists) {
                this.state.selectedId = items.length ? items[0].id : null;
            }
            if (!this.state.selectedId) {
                this.state.details = null;
                this.state.notesDraft = "";
                return;
            }
            await this.loadDetails(this.state.selectedId);
        } catch (err) {
            this.notification.add(this._getErrorMessage(err, "Failed to load bills."), {type: "danger"});
        } finally {
            this.state.loadingList = false;
        }
    }

    onFilterInput(filterKey, ev) {
        if (!Object.prototype.hasOwnProperty.call(this.state.filters, filterKey)) {
            return;
        }
        this.state.filters[filterKey] = ev.target.value || "";
    }

    onFilterKeydown(ev) {
        if (ev.key !== "Enter") {
            return;
        }
        ev.preventDefault();
        this.applyFilters();
    }

    async applyFilters() {
        await this.loadBills({page: 1});
    }

    async resetFilters() {
        this.state.filters.productQuery = "";
        this.state.filters.customerQuery = "";
        this.state.filters.eplusSerial = "";
        this.state.filters.dateStart = "";
        this.state.filters.dateEnd = "";
        await this.loadBills({page: 1});
    }

    async goToPreviousPage() {
        if (this.state.loadingList) {
            return;
        }
        const current = this.state.pagination.page || 1;
        if (current <= 1) {
            return;
        }
        await this.loadBills({page: current - 1});
    }

    async goToNextPage() {
        if (this.state.loadingList) {
            return;
        }
        const current = this.state.pagination.page || 1;
        const maxPage = this.state.pagination.pageCount || 1;
        if (current >= maxPage) {
            return;
        }
        await this.loadBills({page: current + 1});
    }

    async selectBill(billId) {
        const parsed = parseInt(billId || 0, 10);
        if (!parsed || this.state.selectedId === parsed) {
            return;
        }
        this.state.selectedId = parsed;
        await this.loadDetails(parsed);
    }

    async loadDetails(billId = null) {
        const targetId = parseInt(billId || this.state.selectedId || 0, 10);
        if (!targetId) {
            this.state.details = null;
            this.state.notesDraft = "";
            return;
        }
        this.state.loadingDetails = true;
        try {
            const payload = await this.orm.call("ab_sales_ui_api", "bill_wizard_details", [], {
                header_id: targetId,
            });
            this.state.details = payload || null;
            this.state.notesDraft = payload?.notes || "";
        } catch (err) {
            this.notification.add(this._getErrorMessage(err, "Failed to load bill details."), {type: "danger"});
        } finally {
            this.state.loadingDetails = false;
        }
    }

    async saveNotes() {
        if (!this.state.selectedId || this.state.savingNotes) {
            return;
        }
        this.state.savingNotes = true;
        try {
            const updated = await this.orm.call("ab_sales_ui_api", "bill_wizard_update_notes", [], {
                header_id: this.state.selectedId,
                notes: this.state.notesDraft || "",
            });
            if (this.state.details) {
                this.state.details.notes = updated?.notes || this.state.notesDraft || "";
            }
            for (const row of this.state.items) {
                if (row.id === this.state.selectedId) {
                    row.notes = updated?.notes || this.state.notesDraft || "";
                    break;
                }
            }
            this.notification.add("Notes saved.", {type: "success"});
        } catch (err) {
            this.notification.add(this._getErrorMessage(err, "Failed to save notes."), {type: "danger"});
        } finally {
            this.state.savingNotes = false;
        }
    }

    async openReturn() {
        if (!this.state.selectedId || this.state.openingReturn) {
            return;
        }
        this.state.openingReturn = true;
        try {
            const actionDef = await this.orm.call("ab_sales_ui_api", "bill_wizard_open_return_action", [], {
                header_id: this.state.selectedId,
            });
            if (actionDef) {
                await this.action.doAction(actionDef);
            }
        } catch (err) {
            this.notification.add(this._getErrorMessage(err, "Return action is not available."), {type: "warning"});
        } finally {
            this.state.openingReturn = false;
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

    async _confirmPrintAndPrint(payload) {
        const bill = this.state.details;
        if (!bill) {
            return;
        }
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
            this.notification.add(this._getErrorMessage(err, "Failed to save print preferences."), {type: "danger"});
            return;
        }

        try {
            const result = await this.orm.call("ab_sales_ui_api", "bill_wizard_direct_print", [], {
                header_id: this.state.selectedId,
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
            this.notification.add(this._getErrorMessage(err, "Direct print failed."), {type: "danger"});
        }
    }

    async openPrintDialog() {
        await this.loadPrintOptions({silent: true});
        this.dialog.add(AbSalesBillWizardPrintDialog, {
            printerId: this.state.printerId || 0,
            printerName: this.state.printerName || "",
            printFormat: this.state.defaultPrintFormat || "a4",
            availablePrinters: this.state.availablePrinters || [],
            onRefreshPrinters: async () => this.loadPrintOptions(),
            onPreview: async (payload) => {
                await this.previewReceipt(payload || {});
            },
            onConfirm: async (payload) => {
                await this._confirmPrintAndPrint(payload || {});
            },
        });
    }

    async printReceipt() {
        const bill = this.state.details;
        if (!bill) {
            this.notification.add("Select a bill first.", {type: "warning"});
            return;
        }
        const lines = Array.isArray(bill.lines) ? bill.lines : [];
        if (!lines.length) {
            this.notification.add("No lines to print.", {type: "warning"});
            return;
        }
        await this.openPrintDialog();
    }

    async previewReceipt(payload = {}) {
        const bill = this.state.details;
        if (!bill) {
            this.notification.add("Select a bill first.", {type: "warning"});
            return;
        }
        const lines = Array.isArray(bill.lines) ? bill.lines : [];
        if (!lines.length) {
            this.notification.add("No lines to preview.", {type: "warning"});
            return;
        }
        await this.loadPrintOptions({silent: true});
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
            const result = await this.orm.call("ab_sales_ui_api", "bill_wizard_render_print_html", [], {
                header_id: this.state.selectedId,
                print_format: format,
            });
            const content = String(result?.content || "").trim();
            if (!content) {
                this.notification.add("Nothing to preview.", {type: "warning"});
                return;
            }
            const win = openBillWizardPrintWindow(content, format, {focus: true});
            if (!win) {
                this.notification.add("Popup blocked. Allow popups to print.", {type: "warning"});
            }
        } catch (err) {
            this.notification.add(this._getErrorMessage(err, "Preview failed."), {type: "danger"});
        }
    }

    formatMoney(value) {
        const parsed = parseFloat(value || 0);
        if (!Number.isFinite(parsed)) {
            return "0";
        }
        return parsed.toFixed(2).replace(/(?:\.0+|(\.\d*?)0+)$/, "$1");
    }

    formatDateTime(value) {
        if (!value) {
            return "";
        }
        const dt = new Date(value);
        if (Number.isNaN(dt.getTime())) {
            return String(value);
        }
        return dt.toLocaleString();
    }
}

registry.category("actions").add("ab_sales.bill_wizard", AbSalesBillWizardAction);
