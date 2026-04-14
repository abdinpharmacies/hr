/** @odoo-module **/

import {Component, useState} from "@odoo/owl";
import {Dialog} from "@web/core/dialog/dialog";
import {AbSalesBillWizardPrintDialog} from "../bill_wizard/print_dialog";

const DEFAULT_PRINT_FORMAT = "a4";

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

const toFiniteNumber = (value, fallback = 0) => {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : fallback;
};

const firstText = (...values) => {
    for (const value of values) {
        const text = String(value || "").trim();
        if (text) {
            return text;
        }
    }
    return "";
};

const getRpcErrorMessage = (err, fallback = "Failed to print receipt.") => {
    const data = err?.data || err?.response?.data || {};
    const args = data?.arguments;
    return data?.message || (Array.isArray(args) && args[0]) || err?.message || fallback;
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

const buildBillWizardPayload = (bill, parseQtyExpression) => {
    const header = bill?.header || {};
    const promo = bill?.promo || {};
    const customerMode = header.customer_mode === "new" ? "new" : "current";
    const customerName = customerMode === "new"
        ? firstText(header.new_customer_name)
        : firstText(header.bill_customer_name, header.customer_name);
    const customerPhone = customerMode === "new"
        ? firstText(header.new_customer_phone)
        : firstText(header.bill_customer_phone, header.customer_mobile, header.customer_phone);
    const customerAddress = customerMode === "new"
        ? firstText(header.new_customer_address)
        : firstText(header.bill_customer_address, header.invoice_address, header.customer_address);

    const lines = (Array.isArray(bill?.lines) ? bill.lines : [])
        .map((line) => {
            const qtyRaw = Number(line?.qty);
            const qty = Number.isFinite(qtyRaw)
                ? qtyRaw
                : toFiniteNumber(parseQtyExpression ? parseQtyExpression(line?.qty_str) : line?.qty_str, 0);
            const price = toFiniteNumber(line?.sell_price, 0);
            const netRaw = Number(line?.net_amount);
            const netAmount = Number.isFinite(netRaw) ? netRaw : qty * price;
            return {
                product_name: line?.product_name || "",
                product_code: line?.product_code || "",
                qty: qty,
                qty_str: String(line?.qty_str || qty || "0"),
                sell_price: price,
                net_amount: netAmount,
                sold_without_balance: !!line?.products_not_exist,
            };
        })
        .filter((line) => line.product_name || line.product_code || line.qty || line.sell_price || line.net_amount);

    return {
        document_type: "sale",
        header: {
            id: bill?.id || "",
            invoice_number: bill?.local_number || "",
            eplus_serial: bill?.local_number || "",
            create_date: bill?.updated_at || bill?.created_at || new Date().toISOString(),
            store_name: header.store_name || "",
            bill_customer_name: firstText(header.bill_customer_name, customerName),
            bill_customer_phone: firstText(header.bill_customer_phone, customerPhone),
            bill_customer_address: firstText(header.bill_customer_address, customerAddress),
            customer_name: firstText(header.customer_name, customerName),
            customer_phone: firstText(header.customer_phone, header.customer_mobile, customerPhone),
            customer_mobile: firstText(header.customer_mobile, header.customer_phone, customerPhone),
            customer_address: firstText(header.customer_address, customerAddress),
            invoice_address: firstText(header.invoice_address, customerAddress),
            new_customer_name: header.new_customer_name || "",
            new_customer_phone: header.new_customer_phone || "",
            new_customer_address: header.new_customer_address || "",
            employee_name: firstText(header.employee_name),
            applied_program_name: firstText(promo.applied_name, promo.selected_name),
            selected_program_name: firstText(promo.selected_name),
            promo_discount_amount: toFiniteNumber(promo.discount_amount, 0),
            total_price: toFiniteNumber(bill?.total_price, 0),
            total_net_amount: toFiniteNumber(bill?.total_net_amount, 0),
        },
        lines: lines,
    };
};

class AbSalesPosPrinterDialog extends Component {
    static template = "ab_sales.PosPrinterDialog";
    static components = {Dialog};
    static props = {
        printerName: {type: String, optional: true},
        receiptHeader: {type: String, optional: true},
        receiptFooter: {type: String, optional: true},
        onSave: Function,
        close: Function,
    };

    setup() {
        this.state = useState({
            printerName: this.props.printerName || "",
            receiptHeader: this.props.receiptHeader || "",
            receiptFooter: this.props.receiptFooter || "",
        });
        this.onInput = this.onInput.bind(this);
        this.onHeaderInput = this.onHeaderInput.bind(this);
        this.onFooterInput = this.onFooterInput.bind(this);
    }

    onInput(ev) {
        this.state.printerName = ev.target.value || "";
    }

    onHeaderInput(ev) {
        this.state.receiptHeader = ev.target.value || "";
    }

    onFooterInput(ev) {
        this.state.receiptFooter = ev.target.value || "";
    }

    async save() {
        if (this.props.onSave) {
            await this.props.onSave({
                printerName: this.state.printerName,
                receiptHeader: this.state.receiptHeader,
                receiptFooter: this.state.receiptFooter,
            });
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

export const printerStateDefaults = () => ({
    printerId: 0,
    printerName: "",
    receiptHeader: "",
    receiptFooter: "",
    availablePrinters: [],
    defaultPrintFormat: "a4",
});

export const bindPrinterActions = (ctx, {parseQtyExpression}) => {
    ctx._loadPrintOptions = async ({silent = false} = {}) => {
        try {
            const result = await ctx.orm.call("ab_sales_ui_api", "bill_wizard_get_print_options", [], {});
            const printerRecords = normalizePrinterRecords(result?.available_printer_records);
            ctx.state.availablePrinters = printerRecords;
            const selectedId = Number.parseInt(result?.printer_id || 0, 10) || 0;
            const selected = findPrinterById(printerRecords, selectedId);
            ctx.state.printerId = selected ? selected.id : 0;
            ctx.state.printerName = selected?.label || String(result?.printer_name || "").trim();
            ctx.state.defaultPrintFormat = selected?.paper_size || (result?.print_format === "pos_80mm" ? "pos_80mm" : "a4");
            ctx.state.receiptHeader = result?.receipt_header || "Sales Receipt";
            ctx.state.receiptFooter = result?.receipt_footer || "Thank you.";
            return printerRecords;
        } catch (err) {
            if (!silent) {
                ctx.notification.add(getRpcErrorMessage(err, "Failed to load printer options."), {type: "warning"});
            }
            return ctx.state.availablePrinters || [];
        }
    };

    ctx._discoverServerSharedPrinters = async (startIp, endIp) => {
        const startText = String(startIp || "").trim();
        const endText = String(endIp || "").trim();
        if (!startText || !endText) {
            ctx.notification.add("Start IP and End IP are required.", {type: "warning"});
            return ctx.state.availablePrinters || [];
        }
        try {
            const result = await ctx.orm.call("ab_sales_ui_api", "bill_wizard_discover_shared_printers", [], {
                start_ip: startText,
                end_ip: endText,
            });
            const printers = normalizePrinterRecords(result?.available_printer_records);
            if (printers.length) {
                ctx.state.availablePrinters = printers;
            }
            const selected = findPrinterById(ctx.state.availablePrinters, ctx.state.printerId);
            if (selected) {
                ctx.state.printerName = selected.label;
                ctx.state.defaultPrintFormat = selected.paper_size;
            }
            const installedCount = parseInt(result?.installed_count || 0, 10) || 0;
            const discoveredCount = parseInt(result?.discovered_count || 0, 10) || 0;
            ctx.notification.add(
                `Discovery completed. Discovered ${discoveredCount}, installed ${installedCount}.`,
                {type: "success"}
            );
            return ctx.state.availablePrinters || [];
        } catch (err) {
            ctx.notification.add(getRpcErrorMessage(err, "Printer discovery failed."), {type: "danger"});
            return ctx.state.availablePrinters || [];
        }
    };

    ctx._saveBillWizardPrintPreferences = async (payload = {}) => {
        const selectedId = Number.parseInt(
            payload?.printerId !== undefined ? payload.printerId : (ctx.state.printerId || 0),
            10
        ) || 0;
        const selectedRecord = findPrinterById(ctx.state.availablePrinters, selectedId) || payload?.printer || null;
        const selectedPrinter = selectedRecord?.label || String(
            payload?.printerName !== undefined ? payload.printerName : (ctx.state.printerName || "")
        ).trim();
        const selectedFormat = selectedRecord?.paper_size || (payload?.printFormat === "pos_80mm" ? "pos_80mm" : "a4");
        const result = await ctx.orm.call("ab_sales_ui_api", "bill_wizard_set_print_preferences", [], {
            printer_id: selectedId,
            printer_name: selectedPrinter,
            print_format: selectedFormat,
        });
        ctx.state.printerId = Number.parseInt(result?.printer_id || selectedId || 0, 10) || 0;
        const canonical = findPrinterById(ctx.state.availablePrinters, ctx.state.printerId);
        ctx.state.printerName = canonical?.label || (result?.printer_name || selectedPrinter || "").trim();
        ctx.state.defaultPrintFormat = canonical?.paper_size || (result?.print_format === "pos_80mm" ? "pos_80mm" : "a4");
        return {
            printerId: ctx.state.printerId,
            printerName: ctx.state.printerName,
            printFormat: ctx.state.defaultPrintFormat,
            printer: canonical || selectedRecord || null,
        };
    };

    ctx._buildCurrentBillPrintPayload = () => buildBillWizardPayload(ctx.currentBill, parseQtyExpression);

    ctx._previewCurrentBillReceipt = async (payload = {}) => {
        const bill = ctx.currentBill;
        if (!bill || !bill.lines?.length) {
            ctx.notification.add("No lines to preview.", {type: "warning"});
            return;
        }
        await ctx._loadPrintOptions({silent: true});
        const hasPayloadFormat = Object.prototype.hasOwnProperty.call(payload || {}, "printFormat");
        const selectedId = Number.parseInt(
            payload?.printerId !== undefined ? payload.printerId : (ctx.state.printerId || 0),
            10
        ) || 0;
        const selectedRecord = findPrinterById(ctx.state.availablePrinters, selectedId) || payload?.printer || null;
        const format = selectedRecord?.paper_size || (
            hasPayloadFormat
                ? (payload?.printFormat === "pos_80mm" ? "pos_80mm" : "a4")
                : (ctx.state.defaultPrintFormat === "pos_80mm" ? "pos_80mm" : DEFAULT_PRINT_FORMAT)
        );
        try {
            await ctx._saveBillWizardPrintPreferences({
                printerId: selectedId,
                printerName: payload?.printerName,
                printFormat: format,
                printer: selectedRecord,
            });
            const result = await ctx.orm.call("ab_sales_ui_api", "bill_wizard_render_print_html_from_payload", [], {
                payload: ctx._buildCurrentBillPrintPayload(),
                print_format: format,
            });
            const content = String(result?.content || "").trim();
            if (!content) {
                ctx.notification.add("Nothing to preview.", {type: "warning"});
                return;
            }
            const win = openBillWizardPrintWindow(content, format, {focus: true});
            if (!win) {
                ctx.notification.add("Popup blocked. Allow popups to print.", {type: "warning"});
            }
        } catch (err) {
            ctx.notification.add(getRpcErrorMessage(err, "Preview failed."), {type: "danger"});
        }
    };

    ctx._confirmCurrentBillPrint = async (payload = {}) => {
        const bill = ctx.currentBill;
        if (!bill || !bill.lines?.length) {
            return;
        }
        const selectedId = Number.parseInt(
            payload?.printerId !== undefined ? payload.printerId : (ctx.state.printerId || 0),
            10
        ) || 0;
        const selectedRecord = findPrinterById(ctx.state.availablePrinters, selectedId) || payload?.printer || null;
        const selectedPrinter = selectedRecord?.label || String(
            payload?.printerName !== undefined ? payload.printerName : (ctx.state.printerName || "")
        ).trim();
        const printFormat = selectedRecord?.paper_size || (payload?.printFormat === "pos_80mm" ? "pos_80mm" : "a4");
        try {
            await ctx._saveBillWizardPrintPreferences({
                printerId: selectedId,
                printerName: selectedPrinter,
                printFormat: printFormat,
                printer: selectedRecord,
            });
        } catch (err) {
            ctx.notification.add(getRpcErrorMessage(err, "Failed to save print preferences."), {type: "danger"});
            return;
        }
        try {
            const result = await ctx.orm.call("ab_sales_ui_api", "bill_wizard_direct_print_from_payload", [], {
                payload: ctx._buildCurrentBillPrintPayload(),
                print_format: printFormat,
                printer_id: selectedId,
                printer_name: selectedPrinter || ctx.state.printerName || "",
                selected_printer: selectedRecord || false,
            });
            const finalPrinter = (result?.printer_name || selectedPrinter || ctx.state.printerName || "").trim();
            ctx.state.printerId = Number.parseInt(result?.printer_id || ctx.state.printerId || 0, 10) || 0;
            ctx.notification.add(
                finalPrinter
                    ? `Print command sent to '${finalPrinter}'.`
                    : "Print command sent to default system printer.",
                {type: "success"}
            );
        } catch (err) {
            ctx.notification.add(getRpcErrorMessage(err, "Direct print failed."), {type: "danger"});
        }
    };

    ctx.openPrintDialog = async () => {
        const bill = ctx.currentBill;
        if (!bill) {
            ctx.notification.add("Select a bill to print.", {type: "warning"});
            return;
        }
        if (!bill.lines || !bill.lines.length) {
            ctx.notification.add("Add products before printing.", {type: "warning"});
            return;
        }
        await ctx._loadPrintOptions({silent: true});
        ctx.dialog.add(AbSalesBillWizardPrintDialog, {
            printerId: ctx.state.printerId || 0,
            printerName: ctx.state.printerName || "",
            printFormat: ctx.state.defaultPrintFormat || DEFAULT_PRINT_FORMAT,
            availablePrinters: ctx.state.availablePrinters || [],
            onRefreshPrinters: async () => ctx._loadPrintOptions(),
            onPreview: async (payload) => {
                await ctx._previewCurrentBillReceipt(payload || {});
            },
            onConfirm: async (payload) => {
                await ctx._confirmCurrentBillPrint(payload || {});
            },
        });
    };

    ctx.printReceipt = async () => {
        await ctx.openPrintDialog();
    };

    ctx.loadPrinterSettings = async () => {
        await ctx._loadPrintOptions({silent: true});
    };

    ctx.openPrinterDialog = () => {
        ctx.dialog.add(AbSalesPosPrinterDialog, {
            printerName: ctx.state.printerName || "",
            receiptHeader: ctx.state.receiptHeader || "",
            receiptFooter: ctx.state.receiptFooter || "",
            onSave: async (payload) => {
                await ctx.savePrinterSettings(payload);
            },
        });
    };

    ctx.savePrinterSettings = async (payload) => {
        const printerName = payload?.printerName || "";
        const receiptHeader = payload?.receiptHeader || "";
        const receiptFooter = payload?.receiptFooter || "";
        try {
            const result = await ctx.orm.call("ab_sales_ui_api", "set_printer_settings", [], {
                printer_name: printerName,
                receipt_header: receiptHeader,
                receipt_footer: receiptFooter,
            });
            ctx.state.printerName = result?.printer_name || "";
            ctx.state.receiptHeader = result?.receipt_header || "";
            ctx.state.receiptFooter = result?.receipt_footer || "";
            ctx.notification.add("Default printer saved.", {type: "success"});
        } catch (err) {
            ctx.notification.add(err?.message || "Failed to save printer.", {type: "danger"});
        }
    };
};
