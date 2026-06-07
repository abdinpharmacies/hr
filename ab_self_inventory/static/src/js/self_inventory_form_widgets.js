/** @odoo-module **/
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { Component, useState, xml, useRef, onWillUnmount, onPatched } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { Dialog } from "@web/core/dialog/dialog";

// ------------------------------------------------------------------
// Form Hero Widget
// Shows batch name, status badge, deadline, requester info
// ------------------------------------------------------------------

class FormHeroWidget extends Component {
    static template = xml`
        <div class="ab_form_hero">
            <div class="ab_form_hero_left">
                <div class="ab_form_hero_title"><t t-esc="recordName"/></div>
                <div class="ab_form_hero_subtitle" t-if="subtitle">
                    <t t-esc="subtitle"/>
                </div>
            </div>
            <div class="ab_form_hero_center">
                <span t-att-class="'ab_form_state_badge ab_form_state_' + stateValue">
                    <t t-esc="stateLabel"/>
                </span>
                <div class="ab_form_hero_deadline" t-if="deadline">
                    <div class="ab_form_hero_deadline_label">Deadline</div>
                    <div class="ab_form_hero_deadline_date"><t t-esc="deadlineDisplay"/></div>
                </div>
            </div>
            <div class="ab_form_hero_right" t-if="showProgress">
                <div class="ab_progress_stats">
                    <div class="ab_progress_stat">
                        <div class="ab_progress_stat_value"><t t-esc="requestCount"/></div>
                        <div class="ab_progress_stat_label">Requests</div>
                    </div>
                    <div class="ab_progress_stat">
                        <div class="ab_progress_stat_value"><t t-esc="processCount"/></div>
                        <div class="ab_progress_stat_label">Processed</div>
                    </div>
                </div>
            </div>
        </div>
    `;
    static props = { ...standardFieldProps };

    get recordName() {
        return this.props.record.data[this.props.name] || "";
    }

    get requesterName() {
        const raw = this.props.record.data.requester_id;
        if (!raw) return "";
        if (Array.isArray(raw)) return raw[1] || "";
        if (typeof raw === "object") return raw.display_name || raw.name || "";
        return String(raw);
    }

    get submittedDate() {
        const raw = this.props.record.data.submitted_date;
        if (!raw) return null;
        const d = new Date(raw);
        if (isNaN(d.getTime())) return null;
        return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
    }

    get subtitle() {
        const parts = [];
        if (this.requesterName) parts.push("by " + this.requesterName);
        if (this.submittedDate) parts.push(this.submittedDate);
        return parts.join(" · ") || null;
    }

    get stateValue() {
        return this.props.record.data.state || "";
    }

    get stateLabel() {
        const labels = {
            draft: "Draft",
            submitted: "Submitted",
            cancelled: "Cancelled",
            in_progress: "In Progress",
            completed: "Completed",
        };
        return labels[this.stateValue] || this.stateValue;
    }

    get deadline() {
        return this.props.record.data.deadline;
    }

    get deadlineDisplay() {
        const raw = this.deadline;
        if (!raw) return "";
        const d = new Date(raw);
        if (isNaN(d.getTime())) return String(raw);
        return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
    }

    get showProgress() {
        return this.requestCount > 0;
    }

    get requestCount() {
        return this.props.record.data.request_count || 0;
    }

    get processCount() {
        return this.props.record.data.process_count || 0;
    }
}

registry.category("fields").add("ab_inventory_form_hero", {
    component: FormHeroWidget,
});

// ------------------------------------------------------------------
// KPI Card Widget
// Stripe-style metric card with icon, value, label
// ------------------------------------------------------------------

class KpiCardWidget extends Component {
    static template = xml`
        <div t-att-class="'ab_kpi_card ab_kpi_card--' + cardType">
            <div t-att-class="'ab_kpi_card_icon ab_kpi_card_icon--' + cardType">
                <t t-esc="iconChar"/>
            </div>
            <div class="ab_kpi_card_value"><t t-esc="formattedValue"/></div>
            <div class="ab_kpi_card_label"><t t-esc="cardLabel"/></div>
        </div>
    `;
    static props = {
        ...standardFieldProps,
        cardType: { type: String, optional: true },
        cardIcon: { type: String, optional: true },
        cardLabel: { type: String, optional: true },
    };

    static fieldTypeMap = {
        selected_line_count: { type: "items", icon: "items", label: "Selected" },
        request_count: { type: "requests", icon: "requests", label: "Requests" },
        process_count: { type: "processes", icon: "processes", label: "Processed" },
        line_count: { type: "items", icon: "items", label: "Total Lines" },
    };

    get rawValue() {
        return this.props.record.data[this.props.name] || 0;
    }

    get formattedValue() {
        const n = Number(this.rawValue);
        if (isNaN(n)) return "0";
        return n.toLocaleString();
    }

    get cardType() {
        const mapped = KpiCardWidget.fieldTypeMap[this.props.name];
        return mapped ? mapped.type : "items";
    }

    get iconChar() {
        const chars = {
            items: "\u25A0",
            requests: "\u25B6",
            processes: "\u2713",
            shortage: "\u2193",
            extra: "\u2191",
        };
        const iconKey = this.props.cardIcon || this.cardType;
        return chars[iconKey] || "\u25A0";
    }

    get cardLabel() {
        const mapped = KpiCardWidget.fieldTypeMap[this.props.name];
        return mapped ? mapped.label : "Value";
    }
}

registry.category("fields").add("ab_inventory_kpi_card", {
    component: KpiCardWidget,
});

// ------------------------------------------------------------------
// Branch Form Widget
// Shows assigned branches as removable chips/cards
// ------------------------------------------------------------------

class BranchFormWidget extends Component {
    static template = xml`
        <div class="ab_form_branch_list">
            <t t-foreach="visibleBranches" t-as="branch" t-key="branch.id || branch.name">
                <span t-att-class="branchChipClass(branch)" t-on-click="() => this.selectBranch(branch)">
                    <span class="ab_form_branch_chip_icon">&#x1F3E2;</span>
                    <t t-esc="branch.name"/>
                </span>
            </t>
            <span class="ab_form_branch_more" t-if="extraCount > 0" t-on-click="onClickMore">
                +<t t-esc="extraCount"/> more
            </span>
            <div class="ab_form_empty" t-if="!state.branches.length">
                <div class="ab_form_empty_icon">&#x1F3E2;</div>
                <div class="ab_form_empty_text">No branches assigned yet</div>
            </div>
        </div>
    `;
    static props = { ...standardFieldProps };
    static components = {};

    setup() {
        this.state = useState({ branches: [], loaded: false });
        this._dialog = null;
        const record = this.props.record;
        if (record && record.model && record.model.dialog) {
            this._dialog = record.model.dialog;
        } else {
            try { this._dialog = useService("dialog"); } catch (_) { this._dialog = null; }
        }
        this._extractNames();
        this._fetchNames();
        onPatched(() => {
            if (!this.state.branches.length && this._getRaw()) {
                this._extractNames();
            }
        });
    }

    _getRaw() {
        return this.props.record ? this.props.record.data[this.props.name] : null;
    }

    _extractNames() {
        const raw = this._getRaw();
        if (!raw) return;
        const branches = [];
        if (raw.records && raw.records.length) {
            for (const r of raw.records) {
                if (Array.isArray(r)) {
                    branches.push({ id: r[0], name: r[1] || String(r[0]) });
                } else if (typeof r === "object") {
                    branches.push({ id: r.id, name: r.display_name || r.name || String(r.id) });
                }
            }
        } else if (raw.currentIds) {
            for (const id of raw.currentIds) {
                branches.push({ id, name: "ID " + id });
            }
        } else if (Array.isArray(raw)) {
            for (const r of raw) {
                if (Array.isArray(r)) {
                    branches.push({ id: r[0], name: r[1] || String(r[0]) });
                } else if (typeof r === "object") {
                    branches.push({ id: r.id, name: r.display_name || r.name || String(r.id) });
                } else {
                    branches.push({ id: r, name: String(r) });
                }
            }
        }
        this.state.branches = branches.filter((branch) => branch.name);
    }

    async _fetchNames() {
        const raw = this._getRaw();
        if (!raw) return;
        let ids = [];
        let resModel = "ab_store";
        if (raw.currentIds) {
            ids = [...raw.currentIds];
            resModel = raw.resModel || "ab_store";
            if (typeof raw.load === "function" && raw.count > (raw.records ? raw.records.length : 0)) {
                try { await raw.load({ limit: raw.count }); } catch (_) {}
            }
        } else if (Array.isArray(raw)) {
            ids = raw.map(function (r) { return Array.isArray(r) ? r[0] : (r && r.id) || r; }).filter(Boolean);
        }
        if (!ids.length) return;
        const model = this.props.record?.model;
        if (!model || !model.orm) return;
        try {
            const recs = await model.orm.searchRead(resModel, [["id", "in", ids]], ["display_name", "name", "code"], { limit: ids.length });
            const nameMap = {};
            for (const r of recs) {
                const n = r.display_name || r.name || "";
                const c = r.code || "";
                if (n && n.indexOf("datapoint") === -1) nameMap[r.id] = n;
                else if (c) nameMap[r.id] = c + (n && n !== c ? " - " + n : "");
                else nameMap[r.id] = n || String(r.id);
            }
            this.state.branches = ids.map(function (id) {
                return { id, name: nameMap[id] || String(id) };
            });
            this.state.loaded = true;
        } catch (_) {}
    }

    get maxVisible() { return 5; }

    get visibleBranches() {
        const all = this.state.branches || [];
        return all.slice(0, this.maxVisible);
    }

    get extraCount() {
        const all = this.state.branches || [];
        return Math.max(0, all.length - this.maxVisible);
    }

    get selectedBranchId() {
        const raw = this.props.record?.data?.selected_branch_id;
        if (!raw) return false;
        if (Array.isArray(raw)) return raw[0];
        if (typeof raw === "object") return raw.id;
        return raw;
    }

    branchChipClass(branch) {
        const active = branch.id && branch.id === this.selectedBranchId;
        return "ab_form_branch_chip" + (active ? " ab_form_branch_chip_active" : "");
    }

    async selectBranch(branch) {
        if (!branch.id || !this.props.record) return;
        const record = this.props.record;
        const { model, resId, resModel } = record;
        if (!model || !model.orm || !resId || !resModel) return;
        const current = this.selectedBranchId;
        const newVal = current === branch.id ? false : branch.id;
        await model.orm.write(
            resModel,
            [resId],
            { selected_branch_id: newVal || false },
            { context: model.context }
        );
        if (typeof model.load === 'function') {
            await model.load();
        }
    }

    onClickMore() {
        if (!this._dialog) return;
        const branches = this.state.branches || [];
        if (!branches.length) return;
        this._dialog.add(BranchDialog, {
            branchItems: branches,
            onSelect: (branch) => this.selectBranch(branch),
        });
    }
}

class SelectedBranchFilterWidget extends Component {
    static template = xml`
        <div class="ab_selected_branch_filter">
            <div class="ab_selected_branch_filter_text">
                <span class="ab_selected_branch_filter_label">Showing</span>
                <span class="ab_selected_branch_filter_value"><t t-esc="selectedBranchName"/></span>
            </div>
            <button t-if="selectedBranchId" type="button" class="btn btn-secondary btn-sm" t-on-click="clearBranch">
                All Branches
            </button>
        </div>
    `;
    static props = { ...standardFieldProps };

    get selectedBranchId() {
        const raw = this.props.record?.data?.[this.props.name];
        if (!raw) return false;
        if (Array.isArray(raw)) return raw[0];
        if (typeof raw === "object") return raw.id;
        return raw;
    }

    get selectedBranchName() {
        const raw = this.props.record?.data?.[this.props.name];
        if (!raw) return "All branches";
        if (Array.isArray(raw)) return raw[1] || "Selected branch";
        if (typeof raw === "object") return raw.display_name || raw.name || "Selected branch";
        return "Selected branch";
    }

    async clearBranch() {
        if (!this.props.record) return;
        const { model, resId, resModel } = this.props.record;
        if (!model || !model.orm || !resId || !resModel) return;
        await model.orm.write(
            resModel,
            [resId],
            { [this.props.name]: false },
            { context: model.context }
        );
        if (typeof model.load === 'function') {
            await model.load();
        }
    }
}

// Dialog for branch list (reuse from inline template)
class BranchDialog extends Component {
    static template = xml`
        <Dialog size="'md'" title="'Assigned Branches'">
            <div class="ab_branch_dialog">
                <div class="ab_branch_dialog_search">
                    <input type="text" class="o_input" placeholder="Search Branch..." t-model="state.searchText"/>
                </div>
                <div class="ab_branch_dialog_list" t-if="filteredBranches.length">
                    <t t-foreach="filteredBranches" t-as="branch" t-key="branch.id || branch.name">
                        <button type="button" class="ab_branch_dialog_item" t-on-click="() => this.selectBranch(branch)">
                            <t t-esc="branch.name"/>
                        </button>
                    </t>
                </div>
                <div class="ab_branch_dialog_empty" t-else="">
                    No branches match your search.
                </div>
            </div>
        </Dialog>
    `;
    static components = { Dialog };
    static props = {
        branchItems: { type: Array, optional: true },
        branchNames: { type: Array, optional: true },
        onSelect: { type: Function, optional: true },
        close: { type: Function, optional: true },
    };
    setup() {
        this.state = useState({ searchText: "" });
    }
    get branches() {
        if (this.props.branchItems) return this.props.branchItems;
        return (this.props.branchNames || []).map(function (name) {
            return { id: false, name };
        });
    }
    get filteredBranches() {
        const q = this.state.searchText.trim().toLowerCase();
        if (!q) return this.branches;
        return this.branches.filter(function (branch) {
            return branch.name.toLowerCase().includes(q);
        });
    }
    selectBranch(branch) {
        if (this.props.onSelect) {
            this.props.onSelect(branch);
        }
        if (this.props.close) {
            this.props.close();
        }
    }
}

registry.category("fields").add("ab_inventory_branch_form", {
    component: BranchFormWidget,
});

registry.category("fields").add("ab_inventory_selected_branch_filter", {
    component: SelectedBranchFilterWidget,
});

// ------------------------------------------------------------------
// Form Progress Widget
// Circular progress ring showing requests vs processes
// ------------------------------------------------------------------

class FormProgressWidget extends Component {
    static template = xml`
        <div class="ab_progress_card">
            <div class="ab_progress_circular">
                <svg width="100" height="100" viewBox="0 0 100 100">
                    <circle class="ab_progress_circular_bg" cx="50" cy="50" r="45"/>
                    <circle class="ab_progress_circular_fill" cx="50" cy="50" r="45"
                            t-att-stroke-dasharray="circumference"
                            t-att-stroke-dashoffset="dashOffset"/>
                </svg>
                <div class="ab_progress_circular_label">
                    <t t-esc="percentage"/>
                </div>
            </div>
            <div class="ab_progress_stats">
                <div class="ab_progress_stat">
                    <div class="ab_progress_stat_value"><t t-esc="requestCount"/></div>
                    <div class="ab_progress_stat_label">Requested</div>
                </div>
                <div class="ab_progress_stat">
                    <div class="ab_progress_stat_value"><t t-esc="processCount"/></div>
                    <div class="ab_progress_stat_label">Processed</div>
                </div>
            </div>
        </div>
    `;
    static props = { ...standardFieldProps };

    get requestCount() {
        return this.props.record.data.request_count || 0;
    }

    get processCount() {
        return this.props.record.data.process_count || 0;
    }

    get percentage() {
        const total = this.requestCount;
        if (!total) return "0%";
        return Math.round((this.processCount / total) * 100) + "%";
    }

    get circumference() {
        return 2 * Math.PI * 45;
    }

    get dashOffset() {
        const total = this.requestCount;
        if (!total) return this.circumference;
        const pct = Math.min(this.processCount / total, 1);
        return this.circumference * (1 - pct);
    }
}

registry.category("fields").add("ab_inventory_form_progress", {
    component: FormProgressWidget,
});

// ------------------------------------------------------------------
// Timeline Widget
// Activity timeline based on record state and dates
// ------------------------------------------------------------------

class TimelineWidget extends Component {
    static template = xml`
        <div class="ab_timeline">
            <t t-foreach="timelineItems" t-as="item" t-key="item_index">
                <div class="ab_timeline_item">
                    <div t-att-class="'ab_timeline_dot ab_timeline_dot--' + item.type"/>
                    <div class="ab_timeline_content">
                        <div class="ab_timeline_title"><t t-esc="item.title"/></div>
                        <div class="ab_timeline_date" t-if="item.date"><t t-esc="item.date"/></div>
                    </div>
                </div>
            </t>
        </div>
    `;
    static props = { ...standardFieldProps };

    get stateValue() {
        return this.props.record.data.state || "";
    }

    get submittedDate() {
        const raw = this.props.record.data.submitted_date;
        if (!raw) return null;
        const d = new Date(raw);
        if (isNaN(d.getTime())) return null;
        return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
    }

    get cancelledDate() {
        // Cancelled records might not have a separate date field.
        // Use submitted_date as approximation if available.
        return this.submittedDate;
    }

    get timelineItems() {
        const items = [];
        const state = this.stateValue;

        items.push({
            type: "draft",
            title: "Batch Created",
            date: null,
        });

        if (state === "submitted" || state === "cancelled") {
            items.push({
                type: "completed",
                title: "Submitted",
                date: this.submittedDate,
            });
        }

        if (state === "cancelled") {
            items.push({
                type: "cancelled",
                title: "Cancelled",
                date: this.cancelledDate,
            });
        }

        return items;
    }
}

registry.category("fields").add("ab_inventory_timeline", {
    component: TimelineWidget,
});
