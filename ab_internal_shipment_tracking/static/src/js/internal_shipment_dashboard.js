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
            inTransit,
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
            this.orm.searchCount("ab_internal_shipment", [["state", "=", "in_transit"]]),
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
                label: _t("Open Shipments"),
                value: totalOpen,
                icon: "fa fa-cubes",
                accent: "#2f6fdd",
                domain: [["state", "in", openStates]],
            },
            {
                key: "my_shipments",
                label: _t("My Shipments"),
                value: myShipments,
                icon: "fa fa-inbox",
                accent: "#1f8f8a",
                domain: [["created_by_id", "=", user.userId]],
            },
            {
                key: "in_transit",
                label: _t("In Transit"),
                value: inTransit,
                icon: "fa fa-truck",
                accent: "#df7a22",
                domain: [["state", "=", "in_transit"]],
            },
            {
                key: "warehouse",
                label: _t("Warehouse Receipt"),
                value: waitingWarehouse,
                icon: "fa fa-archive",
                accent: "#a16207",
                domain: [["state", "=", "awaiting_warehouse_receipt"]],
            },
            {
                key: "receipt",
                label: _t("Awaiting Receipt"),
                value: waitingReceipt,
                icon: "fa fa-check-square-o",
                accent: "#7b4fd7",
                domain: [["state", "=", "awaiting_receipt"]],
            },
            {
                key: "delayed",
                label: _t("Delayed"),
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

        this.state.byDeliveryMethod = byDeliveryMethod
            .map((item) => ({
                label: this.getDeliveryMethodLabel(item.delivery_method),
                value: item.shipment_count || item.delivery_method_count || 0,
            }))
            .filter((item) => item.value);

        this.state.byShipmentType = byShipmentType
            .map((item) => ({
                label: this.getShipmentTypeLabel(item.shipment_type),
                value: item.shipment_count || item.shipment_type_count || 0,
            }))
            .filter((item) => item.value);

        this.state.recent = recent.map((record) => ({
            id: record.id,
            name: record.name,
            subject: record.subject,
            state: record.state,
            stateLabel: this.getStateLabel(record.state),
            sender: record.sender_display || _t("No sender"),
            recipient: record.recipient_display || _t("No recipient"),
            expected: record.expected_delivery_date || _t("No expected date"),
        }));
        this.state.loading = false;
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
            draft: _t("Draft"),
            sent: _t("Sent"),
            in_transit: _t("In Transit"),
            awaiting_warehouse_receipt: _t("Waiting Warehouse Receipt"),
            awaiting_receipt: _t("Awaiting Receipt"),
            received: _t("Confirmed"),
            closed: _t("Closed"),
        }[value] || value || _t("Unknown");
    }

    getDeliveryMethodLabel(value) {
        return {
            company_vehicle: _t("Internal Company Vehicle"),
            external_company: _t("External Shipping Company"),
            hand_delivery: _t("Hand Delivery"),
            other: _t("Other"),
        }[value] || value || _t("Unknown");
    }

    getShipmentTypeLabel(value) {
        return {
            documents: _t("Documents"),
            devices: _t("Devices"),
            mixed: _t("Mixed"),
            other: _t("Other"),
        }[value] || value || _t("Unknown");
    }

    getDashboardLabels() {
        return {
            moduleName: _t("Internal Shipments"),
            title: _t("Operations Dashboard"),
            subtitle: _t("Track shipment workload, route stages, pending receipts, and recent movement from one responsive workspace."),
            byState: _t("By State"),
            workflowDistribution: _t("Workflow distribution"),
            noWorkflowActivity: _t("No shipment workflow activity yet."),
            byDeliveryMethod: _t("By Delivery Method"),
            movementChannels: _t("Movement channels"),
            noDeliveryMethodStats: _t("No delivery method statistics yet."),
            byShipmentType: _t("By Shipment Type"),
            shipmentMix: _t("Shipment mix"),
            noShipmentTypeStats: _t("No shipment type statistics yet."),
            recentShipments: _t("Recent Shipments"),
            lastSix: _t("Last 6"),
            noRecentShipments: _t("No recent shipments yet."),
        };
    }

    async openList(domain) {
        await this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Internal Shipments"),
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

registry.category("actions").add("ab_internal_shipment_tracking.dashboard", AbInternalShipmentDashboard);
