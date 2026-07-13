/** @odoo-module **/

import {FormController} from "@web/views/form/form_controller";
import {ListController} from "@web/views/list/list_controller";
import {patch} from "@web/core/utils/patch";

const SHIPMENT_MODEL = "ab_internal_shipment";
const SHIPMENT_ACTION_CLASS = "o_ais_shipment_action";

function withShipmentClass(className, resModel) {
    if (resModel !== SHIPMENT_MODEL) {
        return className;
    }
    if (typeof className === "string") {
        return `${className || ""} ${SHIPMENT_ACTION_CLASS}`.trim();
    }
    return {
        ...className,
        [SHIPMENT_ACTION_CLASS]: true,
    };
}

patch(ListController.prototype, {
    get className() {
        return withShipmentClass(super.className, this.props.resModel);
    },
});

patch(FormController.prototype, {
    get className() {
        return withShipmentClass(super.className, this.props.resModel);
    },
});
