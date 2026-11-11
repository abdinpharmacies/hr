import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { localization } from "@web/core/l10n/localization";
import { _t } from "@web/core/l10n/translation";

class AuditFastCount extends Component {
    static template = "ab_inventory_audit.FastCount";
    static props = ["*"];
    setup() {
        this.direction = localization.direction;
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({ barcode: "", lines: [], busy: false, labels: {} });
        onWillStart(() => this.load());
    }
    async load(productIds) {
        const auditId = this.props.action.params?.audit_id || this.props.action.context?.active_id;
        const domain = [["audit_id", "=", auditId]];
        if (productIds) domain.push(["product_id", "in", productIds]);
        const fields = await this.orm.call("ab_inventory_audit_line", "fields_get", [["state"]]);
        this.state.labels = Object.fromEntries(fields.state.selection);
        this.state.lines = await this.orm.searchRead("ab_inventory_audit_line", domain,
            ["product_id", "product_code", "barcodes", "expired", "large_unit_id", "medium_unit_id", "small_unit_id", "latest_attempt_id", "accepted_count_id", "exp_date", "comparison_price", "posted_qty", "reserved_qty", "available_qty", "physical_quantity", "state"], { limit: 200 });
    }
    onKeydown(event) {
        if (event.key === "Enter") this.scan();
    }
    async scan() {
        this.state.busy = true;
        try {
            const products = await this.orm.searchRead("ab_product", [["barcode_ids.name", "=", this.state.barcode]], ["id"]);
            await this.load(products.map((product) => product.id));
            if (!products.length) this.notification.add(_t("No product matches this barcode."), { type: "warning" });
        } finally {
            this.state.busy = false;
        }
    }
    async start(line) {
        const action = await this.orm.call("ab_inventory_audit_line", "action_start", [[line.id]], { input_method: this.state.barcode ? "barcode" : "manual" });
        await this.action.doAction(action, { onClose: () => this.load() });
    }
}
registry.category("actions").add("ab_inventory_audit.fast_count", AuditFastCount);
