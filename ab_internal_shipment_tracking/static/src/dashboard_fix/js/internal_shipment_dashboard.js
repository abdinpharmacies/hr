/** @odoo-module **/

import {_t} from "@web/core/l10n/translation";
import {registry} from "@web/core/registry";
import {user} from "@web/core/user";
import {useService} from "@web/core/utils/hooks";
import {Component, onWillStart, useState} from "@odoo/owl";

const STATE_THEME = {
    draft: "#7b8794",
    sent: "#2f6fdd",
    in_transit: "#df7a22",
    awaiting_warehouse_receipt: "#a16207",
    awaiting_receipt: "#7b4fd7",
    received: "#2f8f57",
    closed: "#96a1ad",
};

const CHART_PALETTE = ["#2f6fdd", "#5da9e9", "#8fd3b6", "#f2c572", "#ef6f6c", "#7b4fd7"];

function isArabic() {
    return (user.lang || "").startsWith("ar");
}

function label(en, ar) {
    return isArabic() ? ar : _t(en);
}

export class AbInternalShipmentDashboard extends Component {
    static template = "ab_internal_shipment_tracking.AbInternalShipmentDashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            loading: true,
            labels: this.getDashboardLabels(),
            cards: [],
            byState: [],
            byDeliveryMethod: [],
            byShipmentType: [],
            recent: [],
        });

        onWillStart(async () => {
            await this.loadDashboard();
        });
    }

    async loadDashboard() {
        this.state.loading = true;
        const today = new Date().toISOString().slice(0, 10);
        const openStates = ["draft", "sent", "in_transit", "awaiting_warehouse_receipt", "awaiting_receipt"];

        const [
            totalOpen,
            myShipments,
            dispatched,
            waitingWarehouse,
            waitingReceipt,
            delayed,
            byState,
            byDeliveryMethod,
            byShipmentType,
            recent,
        ] = await Promise.all([
            this.orm.searchCount("ab_internal_shipment", [["state", "in", openStates]]),
            this.orm.searchCount("ab_internal_shipment", [["created_by_id", "=", user.userId]]),
            this.orm.searchCount("ab_internal_shipment", [["state", "in", ["sent", "in_transit"]]]),
            this.orm.searchCount("ab_internal_shipment", [["state", "=", "awaiting_warehouse_receipt"]]),
            this.orm.searchCount("ab_internal_shipment", [["state", "=", "awaiting_receipt"]]),
            this.orm.searchCount("ab_internal_shipment", [
                ["expected_delivery_date", "!=", false],
                ["expected_delivery_date", "<", today],
                ["state", "not in", ["received", "closed"]],
            ]),
            this.orm.call("ab_internal_shipment", "read_group", [[], ["shipment_count:sum"], ["state"]]),
            this.orm.call("ab_internal_shipment", "read_group", [[], ["shipment_count:sum"], ["delivery_method"]]),
            this.orm.call("ab_internal_shipment", "read_group", [[], ["shipment_count:sum"], ["shipment_type"]]),
            this.orm.searchRead(
                "ab_internal_shipment",
                [],
                ["name", "subject", "state", "sender_display", "recipient_display", "expected_delivery_date"],
                {limit: 6, order: "shipment_date desc, id desc"}
            ),
        ]);

        this.state.cards = [
            {
                key: "open",
                label: label("Open Shipments", "الشحنات المفتوحة"),
                value: totalOpen,
                icon: "fa fa-cubes",
                accent: "#2f6fdd",
                domain: [["state", "in", openStates]],
            },
            {
                key: "my_shipments",
                label: label("My Shipments", "شحناتي"),
                value: myShipments,
                icon: "fa fa-inbox",
                accent: "#1f8f8a",
                domain: [["created_by_id", "=", user.userId]],
            },
            {
                key: "dispatched",
                label: label("Dispatched", "تم الإرسال والتسليم"),
                value: dispatched,
                icon: "fa fa-truck",
                accent: "#df7a22",
                domain: [["state", "in", ["sent", "in_transit"]]],
            },
            {
                key: "warehouse",
                label: label("Warehouse Receipt", "استلام المخزن"),
                value: waitingWarehouse,
                icon: "fa fa-archive",
                accent: "#a16207",
                domain: [["state", "=", "awaiting_warehouse_receipt"]],
            },
            {
                key: "receipt",
                label: label("Awaiting Receipt", "بانتظار الاستلام"),
                value: waitingReceipt,
                icon: "fa fa-check-square-o",
                accent: "#7b4fd7",
                domain: [["state", "=", "awaiting_receipt"]],
            },
            {
                key: "delayed",
                label: label("Delayed", "متأخرة"),
                value: delayed,
                icon: "fa fa-bell-o",
                accent: "#cf4c4c",
                domain: [
                    ["expected_delivery_date", "!=", false],
                    ["expected_delivery_date", "<", today],
                    ["state", "not in", ["received", "closed"]],
                ],
            },
        ];

        this.state.byState = byState
            .map((item) => ({
                key: item.state,
                label: this.getStateLabel(item.state),
                value: item.shipment_count || item.state_count || 0,
                color: STATE_THEME[item.state] || "#96a1ad",
            }))
            .filter((item) => item.value);

        const deliveryMethodRows = byDeliveryMethod
            .map((item, index) => ({
                label: this.getDeliveryMethodLabel(item.delivery_method),
                value: item.shipment_count || item.delivery_method_count || 0,
                color: CHART_PALETTE[index % CHART_PALETTE.length],
            }))
            .filter((item) => item.value);
        const maxDeliveryMethodValue = this.maxValue(deliveryMethodRows);
        this.state.byDeliveryMethod = deliveryMethodRows.map((item) => ({
            ...item,
            style: `width:${(item.value / maxDeliveryMethodValue) * 100}%; background:${item.color}`,
        }));

        const shipmentTypeRows = byShipmentType
            .map((item, index) => ({
                label: this.getShipmentTypeLabel(item.shipment_type),
                value: item.shipment_count || item.shipment_type_count || 0,
                color: CHART_PALETTE[index % CHART_PALETTE.length],
            }))
            .filter((item) => item.value);
        const maxShipmentTypeValue = this.maxValue(shipmentTypeRows);
        this.state.byShipmentType = shipmentTypeRows.map((item) => ({
            ...item,
            style: `width:${(item.value / maxShipmentTypeValue) * 100}%; background:${item.color}`,
        }));

        this.state.recent = recent.map((record) => ({
            id: record.id,
            name: record.name,
            subject: record.subject,
            state: record.state,
            stateClass: `o_ais_dashboard_state_badge o_ais_dashboard_state_${record.state || "unknown"}`,
            stateLabel: this.getStateLabel(record.state),
            sender: record.sender_display || label("No sender", "لا يوجد مرسل"),
            recipient: record.recipient_display || label("No recipient", "لا يوجد مستلم"),
            expected: record.expected_delivery_date || label("No expected date", "لا يوجد تاريخ متوقع"),
        }));
        this.state.loading = false;
    }

    maxValue(items) {
        return Math.max(...items.map((item) => item.value), 1);
    }

    get palette() {
        return CHART_PALETTE;
    }

    get maxDeliveryMethodValue() {
        return Math.max(...this.state.byDeliveryMethod.map((item) => item.value), 1);
    }

    get maxShipmentTypeValue() {
        return Math.max(...this.state.byShipmentType.map((item) => item.value), 1);
    }

    get donutSegments() {
        const total = this.state.byState.reduce((sum, item) => sum + item.value, 0);
        if (!total) return [];

        const radius = 15.9155;
        const circumference = 2 * Math.PI * radius;
        let offset = 0;

        return this.state.byState.map((item, index) => {
            const dash = (item.value / total) * circumference;
            const segment = {
                key: item.key || index,
                color: item.color,
                dasharray: `${dash} ${circumference}`,
                dashoffset: -offset,
            };
            offset += dash;
            return segment;
        });
    }

    getStateLabel(value) {
        return {
            draft: label("Draft", "مسودة"),
            sent: label("Dispatched", "تم الإرسال والتسليم"),
            in_transit: label("Dispatched", "تم الإرسال والتسليم"),
            awaiting_warehouse_receipt: label("Waiting Warehouse Receipt", "بانتظار استلام المخزن"),
            awaiting_receipt: label("Awaiting Receipt", "بانتظار الاستلام"),
            received: label("Confirmed", "تم الاستلام"),
            closed: label("Closed", "مغلق"),
        }[value] || value || label("Unknown", "غير معروف");
    }

    getDeliveryMethodLabel(value) {
        return {
            company_vehicle: label("Internal Company Vehicle", "سيارة الشركة الداخلية"),
            external_company: label("External Shipping Company", "شركة شحن خارجية"),
            hand_delivery: label("Hand Delivery", "تسليم يدوي"),
            other: label("Other", "غير ذلك"),
        }[value] || value || label("Unknown", "غير معروف");
    }

    getShipmentTypeLabel(value) {
        return {
            documents: label("Documents", "مستندات"),
            devices: label("Devices", "أجهزة"),
            mixed: label("Mixed", "متنوع"),
            other: label("Other", "غير ذلك"),
        }[value] || value || label("Unknown", "غير معروف");
    }

    getDashboardLabels() {
        return {
            moduleName: label("Internal Shipments", "الشحنات الداخلية"),
            title: label("Operations Dashboard", "لوحة متابعة العمليات"),
            subtitle: label(
                "Track shipment workload, route stages, pending receipts, and recent movement from one responsive workspace.",
                "تابع الشحنات ومراحل المسار والاستلامات المعلقة وآخر الحركات من مساحة واحدة."
            ),
            byState: label("By State", "حسب الحالة"),
            workflowDistribution: label("Workflow distribution", "توزيع سير العمل"),
            noWorkflowActivity: label("No shipment workflow activity yet.", "لا توجد حركة في سير عمل الشحنات حتى الآن."),
            byDeliveryMethod: label("By Delivery Method", "حسب طريقة التسليم"),
            movementChannels: label("Movement channels", "قنوات الحركة"),
            noDeliveryMethodStats: label("No delivery method statistics yet.", "لا توجد إحصائيات لطريقة التسليم حتى الآن."),
            byShipmentType: label("By Shipment Type", "حسب نوع الشحنة"),
            shipmentMix: label("Shipment mix", "توزيع أنواع الشحنات"),
            noShipmentTypeStats: label("No shipment type statistics yet.", "لا توجد إحصائيات لأنواع الشحنات حتى الآن."),
            recentShipments: label("Recent Shipments", "أحدث الشحنات"),
            lastSix: label("Last 6", "آخر 6"),
            noRecentShipments: label("No recent shipments yet.", "لا توجد شحنات حديثة حتى الآن."),
        };
    }

    async openList(domain) {
        await this.action.doAction({
            type: "ir.actions.act_window",
            name: label("Internal Shipments", "الشحنات الداخلية"),
            res_model: "ab_internal_shipment",
            views: [[false, "list"], [false, "form"]],
            domain,
            context: {
                list_view_ref: "ab_internal_shipment_tracking.ab_internal_shipment_view_list",
                form_view_ref: "ab_internal_shipment_tracking.ab_internal_shipment_view_form",
            },
            target: "current",
        });
    }
}

registry.category("actions").add("ab_internal_shipment_tracking.dashboard", AbInternalShipmentDashboard, {force: true});
