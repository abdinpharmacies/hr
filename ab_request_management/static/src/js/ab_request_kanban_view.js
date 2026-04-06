/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { KanbanRenderer } from "@web/views/kanban/kanban_renderer";
import { kanbanView } from "@web/views/kanban/kanban_view";

const WORKFLOW_ACTIONS = {
    "under_review->scheduled": "action_approve",
    "under_review->rejected": "action_reject",
    "scheduled->in_progress": "action_mark_in_progress",
    "in_progress->under_requester_confirmation": "action_request_confirmation",
    "under_requester_confirmation->in_progress": "action_request_changes",
    "under_requester_confirmation->satisfied": "action_mark_satisfied",
    "satisfied->closed": "action_close",
    "rejected->closed": "action_close",
};

export class AbRequestKanbanRenderer extends KanbanRenderer {
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.notification = useService("notification");
    }

    get canMoveRecords() {
        return super.canMoveRecords && this.props.list.groupByField?.name === "state";
    }

    get canResequenceRecords() {
        return super.canResequenceRecords && this.props.list.groupByField?.name === "state";
    }

    async sortRecordDrop(dataRecordId, dataGroupId, { element, parent }) {
        if (!this.props.list.isGrouped || this.props.list.groupByField?.name !== "state") {
            return super.sortRecordDrop(...arguments);
        }

        const sourceGroup = this.props.list.groups.find((group) => group.id === dataGroupId);
        const targetGroupId = parent?.dataset.id;
        const targetGroup = this.props.list.groups.find((group) => group.id === targetGroupId);

        parent?.classList.remove("o_kanban_hover");

        if (!sourceGroup || !targetGroup || sourceGroup.id === targetGroup.id) {
            await this.props.list.model.load();
            return;
        }

        const workflowAction = WORKFLOW_ACTIONS[`${sourceGroup.value}->${targetGroup.value}`];
        if (!workflowAction) {
            await this.props.list.model.load();
            this.notification.add(_t("This workflow move is not allowed for requests."), {
                type: "warning",
            });
            return;
        }

        const record = sourceGroup.list.records.find((currentRecord) => currentRecord.id === dataRecordId);
        if (!record) {
            await this.props.list.model.load();
            return;
        }

        this.toggleProcessing(dataRecordId, true);
        try {
            await this.orm.call("ab.request", workflowAction, [[record.resId]]);
            await this.props.list.model.load();
        } catch (error) {
            await this.props.list.model.load();
            throw error;
        } finally {
            this.toggleProcessing(dataRecordId, false);
            element?.classList.remove("shadow");
        }
    }
}

export const abRequestKanbanView = {
    ...kanbanView,
    Renderer: AbRequestKanbanRenderer,
};

registry.category("views").add("ab_request_kanban", abRequestKanbanView);
