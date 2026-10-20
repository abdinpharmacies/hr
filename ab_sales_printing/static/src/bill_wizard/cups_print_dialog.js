/** @odoo-module **/

import {AbSalesBillWizardPrintDialog} from "@ab_sales/bill_wizard/print_dialog";

export class AbSalesCupsPrintDialog extends AbSalesBillWizardPrintDialog {
    static template = "ab_sales_printing.CupsPrintDialog";

    setup() {
        super.setup();
        this.state.printFormat = this.props.printFormat === "pos_80mm" ? "pos_80mm" : "a4";
        this.state.missingPrinter = false;
    }

    onPrinterInput(event) {
        super.onPrinterInput(event);
        this.state.missingPrinter = false;
    }

    async refreshPrinters() {
        if (this.state.saving || this.state.loadingPrinters) {
            return;
        }
        const queue = this.state.printerName;
        const format = this.state.printFormat;
        await super.refreshPrinters();
        const selected = this.state.availablePrinters.find((printer) => printer.printer_name === queue);
        this.state.printerId = selected?.id || (queue ? -1 : 0);
        this.state.printerName = selected?.printer_name || "";
        this.state.printFormat = format;
        this.state.missingPrinter = Boolean(queue && !selected);
    }

    async confirm() {
        if (this.state.saving || this.state.loadingPrinters || this.state.missingPrinter) {
            return;
        }
        this.state.saving = true;
        try {
            const selected = this.state.availablePrinters.find((printer) => printer.id === this.state.printerId);
            const result = await this.props.onConfirm({
                printerName: selected?.printer_name || "",
                printFormat: this.state.printFormat,
            });
            if (result !== false) {
                this.props.close();
            }
        } finally {
            this.state.saving = false;
        }
    }
}
