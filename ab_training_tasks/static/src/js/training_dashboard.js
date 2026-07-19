/** @odoo-module **/

import {_t} from "@web/core/l10n/translation";
import {registry} from "@web/core/registry";
import {useService} from "@web/core/utils/hooks";
import {Component, onWillStart, useState} from "@odoo/owl";
import {StatCard} from "@ab_core_ui/core_ui/components/stat_card/stat_card";

export class TrainingDashboard extends Component {
    static template = "ab_training_tasks.TrainingDashboard";
    static components = {StatCard};

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({
            loading: true,
            month: new Date().toISOString().slice(0, 7),
            data: null,
        });
        onWillStart(() => this.loadDashboard());
    }

    async loadDashboard() {
        this.state.loading = true;
        try {
            this.state.data = await this.orm.call(
                "ab.training.task",
                "get_dashboard_data",
                [],
                {month: this.state.month}
            );
        } catch (error) {
            this.notification.add(
                error?.data?.message || _t("The training dashboard could not be loaded."),
                {type: "danger"}
            );
        } finally {
            this.state.loading = false;
        }
    }

    get isManager() {
        return this.state.data?.role === "manager";
    }

    get summaryCards() {
        const data = this.state.data;
        if (!data) {
            return [];
        }
        if (this.isManager) {
            return [
                {
                    key: "monthly_tasks",
                    label: _t("Tasks This Month"),
                    value: data.monthly.total_count,
                    icon: "fa-list-check",
                    tone: "info",
                    hint: _t("Across active members"),
                    scope: "month",
                },
                {
                    key: "pending_review",
                    label: _t("Pending Approval"),
                    value: data.monthly.pending_count,
                    icon: "fa-hourglass-half",
                    tone: "warning",
                    hint: this.formatAmount(data.monthly.pending_amount),
                    state: "pending",
                    scope: "month",
                },
                {
                    key: "approved_wallets",
                    label: _t("Approved to Pay"),
                    value: this.formatAmount(data.wallet.approved_amount),
                    icon: "fa-money",
                    tone: "success",
                    hint: _t("%s approved tasks", data.wallet.approved_count),
                    state: "approved",
                    scope: "wallet",
                },
                {
                    key: "active_members",
                    label: _t("Active Members"),
                    value: data.monthly.active_member_count,
                    icon: "fa-users",
                    tone: "primary",
                    hint: this.formatMonth(data.month),
                    scope: "month",
                },
            ];
        }
        return [
            {
                key: "approved_balance",
                label: _t("Approved Balance"),
                value: this.formatAmount(data.wallet.approved_amount),
                icon: "fa-check-circle",
                tone: "success",
                hint: _t("%s unpaid tasks", data.wallet.approved_count),
                state: "approved",
                scope: "wallet",
            },
            {
                key: "pending_balance",
                label: _t("Pending Balance"),
                value: this.formatAmount(data.wallet.pending_amount),
                icon: "fa-clock-o",
                tone: "warning",
                hint: _t("%s tasks awaiting review", data.wallet.pending_count),
                state: "pending",
                scope: "wallet",
            },
            {
                key: "approved_month",
                label: _t("Approved This Month"),
                value: data.monthly.approved_count,
                icon: "fa-calendar-check-o",
                tone: "info",
                hint: this.formatAmount(data.monthly.approved_amount),
                state: "approved",
                scope: "month",
            },
            {
                key: "rejected_month",
                label: _t("Needs Correction"),
                value: data.monthly.rejected_count,
                icon: "fa-pencil-square-o",
                tone: "danger",
                hint: this.formatMonth(data.month),
                state: "rejected",
                scope: "month",
            },
        ];
    }

    get maxCategoryCount() {
        return Math.max(...(this.state.data?.categories || []).map((item) => item.count), 1);
    }

    get maxTrendAmount() {
        return Math.max(...(this.state.data?.trend || []).map((item) => item.approved_amount), 1);
    }

    get maxMemberTasks() {
        return Math.max(...(this.state.data?.top_members || []).map((item) => item.task_count), 1);
    }

    formatAmount(value) {
        const amount = Number(value || 0);
        const currency = this.state.data?.currency_code;
        if (!currency) {
            return amount.toLocaleString();
        }
        try {
            return new Intl.NumberFormat(undefined, {
                style: "currency",
                currency,
                maximumFractionDigits: 2,
            }).format(amount);
        } catch {
            return `${amount.toLocaleString()} ${this.state.data?.currency_symbol || currency}`;
        }
    }

    formatMonth(month) {
        if (!month) {
            return "";
        }
        const [year, monthNumber] = month.split("-").map(Number);
        return new Intl.DateTimeFormat(undefined, {month: "short", year: "numeric"}).format(
            new Date(Date.UTC(year, monthNumber - 1, 1))
        );
    }

    formatDate(value) {
        if (!value) {
            return "";
        }
        return new Intl.DateTimeFormat(undefined, {
            day: "numeric",
            month: "short",
            year: "numeric",
        }).format(new Date(`${value}T00:00:00`));
    }

    monthBounds() {
        const [year, month] = this.state.month.split("-").map(Number);
        const next = new Date(Date.UTC(year, month, 1));
        return {
            from: `${this.state.month}-01`,
            to: next.toISOString().slice(0, 10),
        };
    }

    async onMonthChange(event) {
        if (!event.target.value) {
            return;
        }
        this.state.month = event.target.value;
        await this.loadDashboard();
    }

    async openTasks(state = null, scope = "month", memberId = null) {
        const domain = [];
        if (scope === "month") {
            const bounds = this.monthBounds();
            domain.push(["completion_date", ">=", bounds.from], ["completion_date", "<", bounds.to]);
        }
        if (scope === "wallet" && state === "approved") {
            domain.push(["wallet_reset_line_id", "=", false]);
        }
        if (state) {
            domain.push(["state", "=", state]);
        }
        if (memberId) {
            domain.push(["member_id", "=", memberId]);
        }
        await this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Training Tasks"),
            res_model: "ab.training.task",
            views: [[false, "list"], [false, "kanban"], [false, "form"]],
            domain,
            target: "current",
        });
    }

    async openTask(taskId) {
        await this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Training Task"),
            res_model: "ab.training.task",
            res_id: taskId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    async createTask() {
        await this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("New Training Task"),
            res_model: "ab.training.task",
            views: [[false, "form"]],
            target: "current",
            context: {default_completion_date: new Date().toISOString().slice(0, 10)},
        });
    }

    async resetAllWallets() {
        await this.action.doAction("ab_training_tasks.action_training_wallet_reset_all", {
            onClose: () => this.loadDashboard(),
        });
    }
}

registry.category("actions").add("ab_training_tasks.dashboard", TrainingDashboard);
