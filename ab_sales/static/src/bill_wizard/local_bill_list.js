/** @odoo-module **/
import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { ListController } from "@web/views/list/list_controller";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

export class LocalBillListModel extends listView.Model {
    async load(params = {}) {
        const generation = this.billLoadGeneration = (this.billLoadGeneration || 0) + 1;
        const domain = params.domain || this.config.domain || [];
        const key = JSON.stringify(domain);
        const refresh = this.isReady && this.billSearchKey !== undefined && key !== this.billSearchKey;
        this.billSearchKey = key;
        if (refresh) {
            try {
                const result = await this.orm.call("ab_sales_header", "refresh_bill_statuses", [], { domain });
                for (const message of result.unavailable_branches || []) {
                    this.billNotification?.add(message, { type: "warning" });
                }
            } catch {
                this.billNotification?.add(_t("Status refresh unavailable; showing local bills."), { type: "warning" });
            }
        }
        if (generation !== this.billLoadGeneration) {
            return;
        }
        return super.load(params);
    }
}

class LocalBillListController extends ListController {
    setup() {
        super.setup();
        this.model.billNotification = useService("notification");
    }
}

registry.category("views").add("ab_sales_local_bills", {
    ...listView, Model: LocalBillListModel, Controller: LocalBillListController,
});
