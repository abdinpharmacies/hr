/** @odoo-module **/
import { Component, hooks } from "@odoo/owl";
import { registry } from "@odoo/core/registry";

class BarcodeField extends Component {

    setup() {
        super.setup();
        this.state = hooks.useState({ value: "" });
        this.handleScan = this.handleScan.bind(this);
    }

    mounted() {
        window.addEventListener('barcodeScan', this.handleScan);
        console.log("hiiii")
    }

    willUnmount() {
        window.removeEventListener('barcodeScan', this.handleScan);
    }

    handleScan(event) {
        this.state.value = event.detail;
    }
}

BarcodeField.template = owl.tags.xml`<input t-model="state.value" />`;
registry.category("fields").add("product_id", BarcodeField);
