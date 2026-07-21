/** @odoo-module **/
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";
import { _t } from "@web/core/l10n/translation";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";

class TelegramManagers extends Component {
    static template = "ab_supplier_claim_workflow_telegram.TelegramManagers";
    static props = { ...standardActionServiceProps };

    setup() {
        this.action = useService("action");
        this.labels = {
            employeeName: _t("Employee Name"),
            department: _t("Department"),
            telegramUsername: _t("Telegram Username"),
            telegramChatId: _t("Telegram Chat ID"),
            linkedAt: _t("Linked At"),
            action: _t("Action"),
        };
        this.state = useState({
            employees: [],
            loading: true,
        });
        onWillStart(async () => {
            try {
                this.state.employees = await rpc("/scc/telegram-managers");
            } catch (_) {
                this.state.employees = [];
            } finally {
                this.state.loading = false;
            }
        });
    }

    openEmployee(employeeId) {
        if (!employeeId) return;
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "ab_hr_employee",
            res_id: employeeId,
            view_mode: "form",
            views: [[false, "form"]],
            target: "current",
        });
    }
}

registry.category("actions").add("scc_telegram_managers", TelegramManagers);
