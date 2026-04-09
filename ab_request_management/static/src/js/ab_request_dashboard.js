/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, onMounted, useState } from "@odoo/owl";

const DASHBOARD_STORAGE_KEY = "ab_request_management.dashboard.preferences";

const STATE_THEME = {
    under_review: "#7b8794",
    scheduled: "#2f6fdd",
    in_progress: "#df7a22",
    under_requester_confirmation: "#7b4fd7",
    satisfied: "#2f8f57",
    rejected: "#cf4c4c",
    closed: "#96a1ad",
};

const CHART_THEMES = {
    ocean: ["#2f6fdd", "#5da9e9", "#7bdff2", "#8fd3b6", "#f2c572", "#ef6f6c"],
    ember: ["#c8553d", "#f28f3b", "#f7b267", "#fcd29f", "#8d99ae", "#4f5d75"],
    forest: ["#1f7a4c", "#4ca771", "#8bcf9b", "#d8f3dc", "#588157", "#344e41"],
};

function loadPreferences() {
    try {
        return {
            chartTheme: "ocean",
            showRecent: true,
            showDepartments: true,
            showStates: true,
            ...JSON.parse(window.localStorage.getItem(DASHBOARD_STORAGE_KEY) || "{}"),
        };
    } catch {
        return {
            chartTheme: "ocean",
            showRecent: true,
            showDepartments: true,
            showStates: true,
        };
    }
}

export class AbRequestDashboard extends Component {
    static template = "ab_request_management.AbRequestDashboard";

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            loading: true,
            preferences: loadPreferences(),
            cards: [],
            departmentChart: [],
            stateChart: [],
            recent: [],
        });

        onWillStart(async () => {
            await this.loadDashboard();
        });
    }

    async loadDashboard() {
        this.state.loading = true;
        const nowIso = new Date().toISOString().slice(0, 19).replace("T", " ");
        const [myRequests, pendingApproval, inProgress, overdue, byDepartment, byState, recent] = await Promise.all([
            this.orm.searchCount("ab.request", [["requester_user_id", "=", user.userId]]),
            this.orm.searchCount("ab.request", [
                ["state", "=", "under_review"],
                ["manager_user_id", "=", user.userId],
            ]),
            this.orm.searchCount("ab.request", [["state", "=", "in_progress"]]),
            this.orm.searchCount("ab.request", [
                ["deadline", "!=", false],
                ["deadline", "<", nowIso],
                ["state", "not in", ["closed", "rejected", "satisfied"]],
            ]),
            this.orm.call(
                "ab.request",
                "read_group",
                [[], ["department_id"], ["department_id"]],
                { orderby: "department_id" }
            ),
            this.orm.call("ab.request", "read_group", [[], ["state"], ["state"]]),
            this.orm.searchRead(
                "ab.request",
                [],
                ["name", "subject", "state", "request_type_id", "deadline", "assigned_employee_ids"],
                { limit: 5, order: "create_date desc, id desc" }
            ),
        ]);

        this.state.cards = [
            {
                key: "my_requests",
                label: _t("My Requests"),
                value: myRequests,
                icon: "fa fa-inbox",
                accent: "#2f6fdd",
                domain: [["requester_user_id", "=", user.userId]],
            },
            {
                key: "pending_approval",
                label: _t("Pending Approval"),
                value: pendingApproval,
                icon: "fa fa-hourglass-half",
                accent: "#7b8794",
                domain: [["state", "=", "under_review"], ["manager_user_id", "=", user.userId]],
            },
            {
                key: "in_progress",
                label: _t("In Progress"),
                value: inProgress,
                icon: "fa fa-gears",
                accent: "#df7a22",
                domain: [["state", "=", "in_progress"]],
            },
            {
                key: "overdue",
                label: _t("Overdue"),
                value: overdue,
                icon: "fa fa-bell-o",
                accent: "#cf4c4c",
                domain: [
                    ["deadline", "!=", false],
                    ["deadline", "<", nowIso],
                    ["state", "not in", ["closed", "rejected", "satisfied"]],
                ],
            },
        ];

        this.state.departmentChart = byDepartment
            .map((item) => ({
                label: item.department_id?.[1] || _t("Unassigned"),
                value: item.department_id_count,
            }))
            .filter((item) => item.value);

        this.state.stateChart = byState
            .map((item) => ({
                key: item.state,
                label: this.getStateLabel(item.state),
                value: item.state_count,
                color: STATE_THEME[item.state] || "#96a1ad",
            }))
            .filter((item) => item.value);

        this.state.recent = recent.map((record) => ({
            id: record.id,
            name: record.name,
            subject: record.subject,
            state: record.state,
            stateLabel: this.getStateLabel(record.state),
            deadline: record.deadline || _t("No deadline planned"),
            requestType: record.request_type_id?.[1] || _t("No type"),
            assigneeCount: record.assigned_employee_ids?.length || 0,
        }));

        this.state.loading = false;
    }

    get palette() {
        return CHART_THEMES[this.state.preferences.chartTheme] || CHART_THEMES.ocean;
    }

    get maxDepartmentValue() {
        return Math.max(...this.state.departmentChart.map((item) => item.value), 1);
    }

    get stateTotal() {
        return this.state.stateChart.reduce((total, item) => total + item.value, 0) || 1;
    }

    get donutSegments() {
        let offset = 0;
        return this.state.stateChart.map((item) => {
            const fraction = item.value / this.state.stateTotal;
            const segment = {
                ...item,
                dasharray: `${fraction * 100} ${100 - fraction * 100}`,
                dashoffset: -offset,
            };
            offset += fraction * 100;
            return segment;
        });
    }

    getStateLabel(value) {
        return {
            under_review: _t("Under Review"),
            scheduled: _t("Scheduled"),
            in_progress: _t("In Progress"),
            under_requester_confirmation: _t("Under Requester Confirmation"),
            satisfied: _t("Satisfied"),
            rejected: _t("Rejected"),
            closed: _t("Closed"),
        }[value] || value || _t("Unknown");
    }

    savePreferences() {
        window.localStorage.setItem(
            DASHBOARD_STORAGE_KEY,
            JSON.stringify(this.state.preferences)
        );
    }

    updatePreference(key, value) {
        this.state.preferences[key] = value;
        this.savePreferences();
    }

    async openList(domain) {
        await this.env.services.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Requests"),
            res_model: "ab.request",
            views: [[false, "list"], [false, "form"]],
            domain: domain,
            target: "current",
        });
    }

    onClickRecentItem(id) {
        this.openList([["id", "=", id]]);
    }
}

registry.category("actions").add("ab_request_management.dashboard", AbRequestDashboard);
