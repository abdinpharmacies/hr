/** @odoo-module **/

import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";

const cogMenuRegistry = registry.category("cogMenu");

export class ResetListColumnOrder extends Component {
    static template = "web_list_column_order.ResetListColumnOrder";
    static components = { DropdownItem };
    static props = {};

    async resetColumnOrder() {
        this.env.bus.trigger("WEB_LIST_COLUMN_ORDER:RESET", {
            modelName: this.env.model.root.resModel,
            viewId: this.env.config.viewId || false,
        });
    }
}

cogMenuRegistry.add(
    "web-list-column-order-reset",
    {
        Component: ResetListColumnOrder,
        groupNumber: 35,
        isDisplayed: (env) => env.config.viewType === "list",
    },
    { sequence: 35 }
);
