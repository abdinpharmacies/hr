import { Component, onMounted, onPatched, onWillUnmount, useRef, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { localization } from "@web/core/l10n/localization";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { formatDateTime } from "@web/views/fields/formatters";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";

const STATUS_DETAILS = {
    waiting: { label: _t("Waiting"), className: "waiting" },
    pending: { label: _t("Pending"), className: "pending" },
    rejected: { label: _t("Rejected"), className: "rejected" },
    deferred: { label: _t("Deferred"), className: "deferred" },
    approved: { label: _t("Approved"), className: "approved" },
};

export class SupplierClaimWorkflowDiagram extends Component {
    static template = "ab_supplier_claim_cycle.WorkflowDiagram";
    static props = { ...standardFieldProps };

    get direction() {
        return localization.direction;
    }

    get stageGroups() {
        const list = this.props.record.data[this.props.name];
        const records = list?.records || [];
        const grouped = new Map();
        for (const record of records) {
            const sequence = record.data.sequence;
            if (!grouped.has(sequence)) {
                grouped.set(sequence, []);
            }
            const status = STATUS_DETAILS[record.data.status] || STATUS_DETAILS.waiting;
            const actor = record.data.user_id?.display_name || false;
            const decisionAt = record.data.decision_at;
            const hasActionMetadata = ["approved", "rejected", "deferred"].includes(
                record.data.status
            ) && Boolean(actor && decisionAt);
            grouped.get(sequence).push({
                id: record.resId,
                name: record.data.name,
                status: record.data.status,
                label: status.label,
                className: status.className,
                actor,
                actionDate: hasActionMetadata ? formatDateTime(decisionAt) : false,
                hasActionMetadata,
            });
        }
        return [...grouped.entries()]
            .sort(([left], [right]) => left - right)
            .map(([sequence, stages]) => ({ sequence, stages }));
    }

    get closedStatus() {
        return this.props.record.data.state === "closed" ? "approved" : "waiting";
    }

    get closedLabel() {
        return STATUS_DETAILS[this.closedStatus].label;
    }

}

export class SupplierClaimWorkflowActions extends Component {
    static template = "ab_supplier_claim_cycle.WorkflowActions";
    static props = { ...standardFieldProps };
    static components = { Dropdown, DropdownItem };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ busy: false, compact: false });
        this.actionsRef = useRef("actions");
        this.inlineRef = useRef("inlineActions");
        onMounted(() => {
            this.resizeObserver = new ResizeObserver(() => this.updateCompactMode());
            this.resizeObserver.observe(this.actionsRef.el);
            this.resizeObserver.observe(this.inlineRef.el);
            this.updateCompactMode();
        });
        onPatched(() => this.updateCompactMode());
        onWillUnmount(() => this.resizeObserver?.disconnect());
    }

    updateCompactMode() {
        const available = this.actionsRef.el?.clientWidth;
        if (available) {
            this.state.compact = this.activeStages.length > 1
                || this.inlineRef.el.scrollWidth > available + 1;
        }
    }

    get activeStages() {
        const list = this.props.record.data[this.props.name];
        return (list?.records || [])
            .filter((record) => record.data.can_decide)
            .map((record) => ({ id: record.resId, name: record.data.name }));
    }

    actionLabel(action, stageName) {
        const labels = {
            approve: _t("Approve"),
            reject: _t("Reject"),
            defer: _t("Defer"),
        };
        return `${labels[action]} ${stageName}`;
    }

    async approve(stageId) {
        if (this.state.busy) {
            return;
        }
        this.state.busy = true;
        try {
            await this.orm.call("ab_supplier_claim_stage_state", "action_approve", [[stageId]]);
            await this.props.record.load();
        } finally {
            this.state.busy = false;
        }
    }

    async openDecision(stageId, decision) {
        if (this.state.busy) {
            return;
        }
        this.state.busy = true;
        try {
            const method = decision === "rejected" ? "action_open_reject" : "action_open_defer";
            const action = await this.orm.call(
                "ab_supplier_claim_stage_state",
                method,
                [[stageId]]
            );
            await this.action.doAction(action, {
                onClose: () => this.props.record.load(),
            });
        } finally {
            this.state.busy = false;
        }
    }
}

export const supplierClaimWorkflowDiagram = {
    component: SupplierClaimWorkflowDiagram,
    displayName: _t("Supplier Claim Workflow Diagram"),
    supportedTypes: ["one2many"],
    isEmpty: () => false,
    relatedFields: [
        { name: "sequence", type: "integer" },
        { name: "name", type: "char" },
        {
            name: "status",
            type: "selection",
            selection: Object.entries(STATUS_DETAILS).map(([value, details]) => [
                value,
                details.label,
            ]),
        },
        { name: "user_id", type: "many2one", relation: "res.users" },
        { name: "decision_at", type: "datetime" },
    ],
};

registry.category("fields").add(
    "supplier_claim_workflow_diagram",
    supplierClaimWorkflowDiagram
);

registry.category("fields").add("supplier_claim_workflow_actions", {
    component: SupplierClaimWorkflowActions,
    displayName: _t("Supplier Claim Workflow Actions"),
    supportedTypes: ["one2many"],
    isEmpty: () => false,
    relatedFields: [
        { name: "name", type: "char" },
        { name: "can_decide", type: "boolean" },
    ],
});
