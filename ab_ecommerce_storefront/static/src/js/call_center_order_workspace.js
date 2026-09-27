/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { Dialog } from "@web/core/dialog/dialog";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { Component, useState } from "@odoo/owl";


class AbCallCenterDeliveryDialog extends Component {
    static template = "ab_ecommerce_storefront.CallCenterDeliveryDialog";
    static components = { Dialog };
    static props = {
        close: Function,
        deliveries: Array,
        onOpenPicking: Function,
        orderName: String,
        title: String,
    };

    openPicking(pickingId) {
        this.props.close();
        this.props.onOpenPicking(pickingId);
    }
}


class AbCallCenterPrescriptionImageDialog extends Component {
    static template = "ab_ecommerce_storefront.CallCenterPrescriptionImageDialog";
    static components = { Dialog };
    static props = {
        close: Function,
        imageUrl: String,
        name: String,
        publicReference: { type: String, optional: true },
        title: String,
    };

    setup() {
        this.zoom = useState({
            active: false,
            x: 50,
            y: 50,
        });
    }

    get imageStyle() {
        return `transform-origin: ${this.zoom.x}% ${this.zoom.y}%;`;
    }

    onImageMove(event) {
        const image = event.currentTarget.querySelector("img");
        const imageRect = (image || event.currentTarget).getBoundingClientRect();
        if (!imageRect.width || !imageRect.height) {
            return;
        }
        const x = Math.max(0, Math.min(100, ((event.clientX - imageRect.left) / imageRect.width) * 100));
        const y = Math.max(0, Math.min(100, ((event.clientY - imageRect.top) / imageRect.height) * 100));
        this.zoom.x = x;
        this.zoom.y = y;
    }

    toggleImageZoom(event) {
        if (event.button && event.button !== 0) {
            return;
        }
        this.onImageMove(event);
        this.zoom.active = !this.zoom.active;
    }

    onImageKeydown(event) {
        if (!["Enter", " "].includes(event.key)) {
            return;
        }
        event.preventDefault();
        this.zoom.active = !this.zoom.active;
    }
}


export class AbCallCenterOrderWorkspace extends Component {
    static template = "ab_ecommerce_storefront.CallCenterOrderWorkspace";
    static props = standardFieldProps;

    setup() {
        this.action = useService("action");
        this.dialog = useService("dialog");
        this.notification = useService("notification");
        this.orm = useService("orm");
        this.state = useState({ loadingDelivery: false });
    }

    get data() {
        return this.props.record.data[this.props.name] || {};
    }

    async openDeliveryQuickView() {
        const orderId = this.props.record.resId;
        if (!orderId || this.state.loadingDelivery) {
            return;
        }
        this.state.loadingDelivery = true;
        try {
            const deliveries = await this.orm.call(
                "sale.order",
                "get_ab_call_center_delivery_summary",
                [[orderId]]
            );
            this.dialog.add(AbCallCenterDeliveryDialog, {
                deliveries,
                onOpenPicking: (pickingId) => this.openPicking(pickingId),
                orderName: this.data.name || "",
                title: _t("Delivery details"),
            });
        } catch (error) {
            this.notification.add(_t("Delivery details could not be loaded."), {
                type: "danger",
            });
            throw error;
        } finally {
            this.state.loadingDelivery = false;
        }
    }

    openPicking(pickingId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Delivery Order"),
            res_model: "stock.picking",
            res_id: pickingId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    openPrescriptionImage() {
        const prescription = this.data.prescription;
        if (!prescription?.image_url) {
            return;
        }
        this.dialog.add(AbCallCenterPrescriptionImageDialog, {
            imageUrl: prescription.image_url,
            name: prescription.name || _t("Prescription"),
            publicReference: prescription.public_reference || "",
            title: _t("Prescription image"),
        });
    }
}


registry.category("fields").add("ab_call_center_order_workspace", {
    component: AbCallCenterOrderWorkspace,
    displayName: _t("Call Center Order Workspace"),
    supportedTypes: ["json"],
});
