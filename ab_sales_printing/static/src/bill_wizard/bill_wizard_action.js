/** @odoo-module **/

import "@ab_sales/bill_wizard/bill_wizard_action";
import {_t} from "@web/core/l10n/translation";
import {registry} from "@web/core/registry";
import {user} from "@web/core/user";
import {session} from "@web/session";
import {AbSalesCupsPrintDialog} from "./cups_print_dialog";

const actions = registry.category("actions");
const SalesBillWizard = actions.get("ab_sales.bill_wizard");
const paperFormat = (value) => value === "pos_80mm" ? "pos_80mm" : "a4";

export class AbSalesPrintingBillWizard extends SalesBillWizard {
    get printingPreferenceKey() {
        return `ab_sales_printing.preferences.${session.db}.${user.userId}`;
    }

    _readPrintingPreference() {
        if (this._printingPreference !== undefined) {
            return this._printingPreference;
        }
        try {
            const value = JSON.parse(window.localStorage.getItem(this.printingPreferenceKey));
            this._printingPreference = value && typeof value === "object" ? value : {};
        } catch {
            this._printingPreference = {};
        }
        return this._printingPreference;
    }

    async loadPrintOptions({silent = false} = {}) {
        if (this._loadPrintOptionsPromise) {
            return this._loadPrintOptionsPromise;
        }
        this._loadPrintOptionsPromise = (async () => {
            this.state.loadingPrintOptions = true;
            try {
                const result = await this.orm.call("ab_sales_ui_api", "bill_wizard_cups_options", [], {});
                const printers = result.available_printer_records || [];
                const preference = this._readPrintingPreference();
                const selected = printers.find((printer) => printer.printer_name === preference.printerName);
                this.state.availablePrinters = printers;
                this.state.printerId = selected?.id || 0;
                this.state.printerName = selected?.printer_name || "";
                this.state.defaultPrintFormat = paperFormat(preference.printFormat || result.print_format);
                return printers;
            } catch (error) {
                if (!silent) {
                    this.notification.add(this._getErrorMessage(error, _t("Failed to load printer options.")), {type: "warning"});
                }
                // Do not offer stale queues after a failed refresh. Browser
                // printing remains available even when CUPS is unreachable.
                this.state.availablePrinters = [];
                this.state.printerId = 0;
                this.state.printerName = "";
                return [];
            } finally {
                this.state.loadingPrintOptions = false;
                this._loadPrintOptionsPromise = null;
            }
        })();
        return this._loadPrintOptionsPromise;
    }

    _rememberPrintingPreference(payload) {
        this._printingPreference = {
            printerName: payload.printerName || "",
            printFormat: paperFormat(payload.printFormat),
        };
        this.state.printerName = this._printingPreference.printerName;
        this.state.defaultPrintFormat = this._printingPreference.printFormat;
        try {
            window.localStorage.setItem(this.printingPreferenceKey, JSON.stringify(this._printingPreference));
        } catch {
            this.notification.add(_t("Print preferences could not be saved in this browser."), {type: "warning"});
        }
    }

    async _openReceiptWindow(headerId, payload, print) {
        // Open before any RPC so this remains part of the user's click.
        const format = paperFormat(payload.printFormat);
        const win = window.open("", "_blank", format === "pos_80mm" ? "width=360,height=900" : "width=900,height=720");
        if (!win) {
            this.notification.add(_t("Popup blocked. Allow popups to print."), {type: "warning"});
            return false;
        }
        try {
            const result = await this.orm.call("ab_sales_ui_api", "bill_wizard_cups_render", [], {
                header_id: headerId, print_format: format,
            });
            if (!result.content) {
                throw new Error(_t("Nothing to print."));
            }
            win.document.open();
            win.document.write(result.content);
            win.document.close();
            await win.document.fonts.ready;
            win.focus();
            if (print) {
                win.print();
            }
            return true;
        } catch (error) {
            win.close();
            this.notification.add(this._getErrorMessage(error, _t("Could not open the receipt.")), {type: "danger"});
            return false;
        }
    }

    async _printReceipt(headerId, payload) {
        this._rememberPrintingPreference(payload);
        if (!payload.printerName) {
            return this._openReceiptWindow(headerId, payload, true);
        }
        try {
            const result = await this.orm.call("ab_sales_ui_api", "bill_wizard_cups_print", [], {
                header_id: headerId,
                printer_name: payload.printerName,
                print_format: paperFormat(payload.printFormat),
            });
            this.notification.add(_t("Sent to %(printer)s. CUPS job: %(job)s.", {
                printer: result.printer_name, job: result.job_id,
            }), {type: "success"});
            return true;
        } catch (error) {
            this.notification.add(this._getErrorMessage(error, _t("Direct print failed.")), {type: "danger"});
            return false;
        }
    }

    async openPrintDialog() {
        if (this._printingDialogOpen) {
            return;
        }
        this._printingDialogOpen = true;
        const headerId = this.state.selectedId;
        try {
            await this.loadPrintOptions();
            this.dialog.add(AbSalesCupsPrintDialog, {
                printerId: this.state.printerId,
                printerName: this.state.printerName,
                printFormat: this.state.defaultPrintFormat,
                availablePrinters: this.state.availablePrinters,
                onRefreshPrinters: () => this.loadPrintOptions(),
                onPreview: (payload) => this._openReceiptWindow(headerId, payload, false),
                onConfirm: (payload) => this._printReceipt(headerId, payload),
            }, {onClose: () => { this._printingDialogOpen = false; }});
        } catch (error) {
            this._printingDialogOpen = false;
            throw error;
        }
    }
}

// Substitute only this action with a subclass; the Sales class and prototype
// remain intact, as do all other consumers of its print dialog.
actions.add("ab_sales.bill_wizard", AbSalesPrintingBillWizard, {force: true});
