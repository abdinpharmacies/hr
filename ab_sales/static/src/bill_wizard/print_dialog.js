/** @odoo-module **/

import {Component, useState} from "@odoo/owl";
import {Dialog} from "@web/core/dialog/dialog";

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
            label: label,
            name: String(raw.name || "").trim(),
            protocol: String(raw.protocol || "").trim(),
            paper_size: String(raw.paper_size || "").trim() === "pos_80mm" ? "pos_80mm" : "a4",
            printer_name: String(raw.printer_name || "").trim(),
            ip: String(raw.ip || "").trim(),
            port: Number.parseInt(raw.port || 9100, 10) || 9100,
            username: String(raw.username || "").trim(),
            is_default: !!raw.is_default,
        });
    }
    return out;
};

export class AbSalesBillWizardPrintDialog extends Component {
    static template = "ab_sales.BillWizardPrintDialog";
    static components = {Dialog};
    static props = {
        printerId: {type: Number, optional: true},
        printerName: {type: String, optional: true},
        printFormat: {type: String, optional: true},
        availablePrinters: {type: Array, optional: true},
        onRefreshPrinters: {type: Function, optional: true},
        onDiscoverPrinters: {type: Function, optional: true},
        onPreview: {type: Function, optional: true},
        onConfirm: Function,
        close: Function,
    };

    setup() {
        const initialPrinterName = String(this.props.printerName || "").trim();
        const initialPrinters = normalizePrinterRecords(this.props.availablePrinters);
        let initialPrinterId = Number.parseInt(this.props.printerId || 0, 10) || 0;
        if (!initialPrinterId && initialPrinterName) {
            const foundByName = initialPrinters.find((rec) => rec.label.toLowerCase() === initialPrinterName.toLowerCase());
            if (foundByName) {
                initialPrinterId = foundByName.id;
            }
        }
        const selected = initialPrinters.find((rec) => rec.id === initialPrinterId);
        const formatFromPrinter = selected?.paper_size === "pos_80mm" ? "pos_80mm" : "a4";
        this.state = useState({
            printerId: selected ? selected.id : 0,
            printerName: selected?.label || initialPrinterName,
            printFormat: selected ? formatFromPrinter : (this.props.printFormat === "pos_80mm" ? "pos_80mm" : "a4"),
            availablePrinters: initialPrinters,
            loadingPrinters: false,
            saving: false,
        });
        this.onPrinterInput = this.onPrinterInput.bind(this);
        this.onFormatInput = this.onFormatInput.bind(this);
        this.refreshPrinters = this.refreshPrinters.bind(this);
        this.discoverPrinters = this.discoverPrinters.bind(this);
        this.preview = this.preview.bind(this);
        this.confirm = this.confirm.bind(this);
        this.cancel = this.cancel.bind(this);
    }

    onPrinterInput(ev) {
        const printerId = Number.parseInt(ev.target.value || 0, 10) || 0;
        const selected = (this.state.availablePrinters || []).find((rec) => rec.id === printerId);
        this.state.printerId = selected ? selected.id : 0;
        this.state.printerName = selected?.label || "";
        if (selected?.paper_size) {
            this.state.printFormat = selected.paper_size === "pos_80mm" ? "pos_80mm" : "a4";
        }
    }

    onFormatInput(ev) {
        const value = String(ev.target.value || "a4").trim();
        this.state.printFormat = value === "pos_80mm" ? "pos_80mm" : "a4";
    }

    async refreshPrinters() {
        if (!this.props.onRefreshPrinters || this.state.loadingPrinters) {
            return;
        }
        this.state.loadingPrinters = true;
        try {
            const printers = await this.props.onRefreshPrinters();
            this.state.availablePrinters = normalizePrinterRecords(printers);
            if (this.state.printerId) {
                const selected = this.state.availablePrinters.find((rec) => rec.id === this.state.printerId);
                if (selected) {
                    this.state.printerName = selected.label;
                    if (selected.paper_size) {
                        this.state.printFormat = selected.paper_size === "pos_80mm" ? "pos_80mm" : "a4";
                    }
                }
            }
        } finally {
            this.state.loadingPrinters = false;
        }
    }

    async discoverPrinters() {
        if (!this.props.onDiscoverPrinters || this.state.loadingPrinters) {
            return;
        }
        const startIp = String(window.prompt("Start IP", "") || "").trim();
        if (!startIp) {
            return;
        }
        const endIp = String(window.prompt("End IP", startIp) || "").trim();
        if (!endIp) {
            return;
        }
        this.state.loadingPrinters = true;
        try {
            const printers = await this.props.onDiscoverPrinters({
                startIp: startIp,
                endIp: endIp,
            });
            const normalized = normalizePrinterRecords(printers);
            if (normalized.length) {
                this.state.availablePrinters = normalized;
            }
            if (this.state.printerId) {
                const selected = this.state.availablePrinters.find((rec) => rec.id === this.state.printerId);
                if (selected) {
                    this.state.printerName = selected.label;
                    if (selected.paper_size) {
                        this.state.printFormat = selected.paper_size === "pos_80mm" ? "pos_80mm" : "a4";
                    }
                }
            }
        } finally {
            this.state.loadingPrinters = false;
        }
    }

    async confirm() {
        if (this.state.saving) {
            return;
        }
        this.state.saving = true;
        try {
            if (this.props.onConfirm) {
                const selected = (this.state.availablePrinters || []).find((rec) => rec.id === this.state.printerId) || null;
                await this.props.onConfirm({
                    printerId: this.state.printerId || 0,
                    printerName: this.state.printerName || "",
                    printFormat: this.state.printFormat || "a4",
                    printer: selected,
                });
            }
            if (this.props.close) {
                this.props.close();
            }
        } finally {
            this.state.saving = false;
        }
    }

    async preview() {
        if (this.state.saving || !this.props.onPreview) {
            return;
        }
        const selected = (this.state.availablePrinters || []).find((rec) => rec.id === this.state.printerId) || null;
        await this.props.onPreview({
            printerId: this.state.printerId || 0,
            printerName: this.state.printerName || "",
            printFormat: this.state.printFormat || "a4",
            printer: selected,
        });
    }

    cancel() {
        if (this.props.close) {
            this.props.close();
        }
    }
}
