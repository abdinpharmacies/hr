/** @odoo-module **/

import { registry } from "@web/core/registry";
import { AbSalesPosPromoPanel } from "./pos_promo_panel";

const PosAction = registry.category("actions").get("ab_sales.pos");
if (PosAction) {
    PosAction.components = {
        ...(PosAction.components || {}),
        AbSalesPosPromoPanel,
    };
}
