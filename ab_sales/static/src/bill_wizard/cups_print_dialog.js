/** @odoo-module **/
import {AbSalesBillWizardPrintDialog} from "./print_dialog";

export class AbSalesCupsPrintDialog extends AbSalesBillWizardPrintDialog {
    static template = "ab_sales.CupsPrintDialog";

    async refreshPrinters() {
        const queue = this.state.printerName;
        await super.refreshPrinters();
        const selected = this.state.availablePrinters.find((printer) => printer.printer_name === queue);
        this.state.printerId = selected?.id || 0;
        this.state.printerName = selected?.printer_name || "";
    }

    async confirm() {
        if (this.state.saving) { return; }
        this.state.saving = true;
        try {
            const selected = this.state.availablePrinters.find((printer) => printer.id === this.state.printerId);
            const result = await this.props.onConfirm({
                printerId: selected?.id || 0, printerName: selected?.printer_name || "",
                printer: selected || null, printFormat: this.state.printFormat,
            });
            if (result !== false) { this.props.close(); }
        } finally {
            this.state.saving = false;
        }
    }
}
