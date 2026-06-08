/** @odoo-module **/
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { Component, useState, xml, useRef, onWillStart, onWillUnmount, onPatched, useExternalListener } from "@odoo/owl";
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

const ROW_HEIGHT = 56;
const PAGE_SIZE = 50;

// ===================================================================
// Data Grid Widget - Modern SaaS grid replacing O2M
// Features: analytics header, branch nav, search, selection, l/loading
// ===================================================================

class DataGridWidget extends Component {
    static template = xml`
        <div class="ab_saas_grid_wrapper">
            <div class="ab_saas_grid_loading" t-if="state.loading &amp;&amp; !state.rows.length">
                <div class="ab_saas_grid_spinner"></div>
                <span>Loading data...</span>
            </div>

            <div class="ab_saas_grid_content" t-if="state.analytics">
                <!-- Analytics Header -->
                <div class="ab_saas_analytics_row">
                    <div class="ab_saas_analytics_card ab_saas_analytics_card--branches">
                        <div class="ab_saas_analytics_value" t-esc="state.analytics.branch_count"/>
                        <div class="ab_saas_analytics_label">Branches</div>
                    </div>
                    <div class="ab_saas_analytics_card ab_saas_analytics_card--products">
                        <div class="ab_saas_analytics_value" t-esc="state.analytics.total_products"/>
                        <div class="ab_saas_analytics_label">Products</div>
                    </div>
                    <div class="ab_saas_analytics_card ab_saas_analytics_card--selected">
                        <div class="ab_saas_analytics_value" t-esc="state.analytics.selected_products"/>
                        <div class="ab_saas_analytics_label">Selected</div>
                    </div>
                    <div class="ab_saas_analytics_card ab_saas_analytics_card--matched">
                        <div class="ab_saas_analytics_value" t-esc="state.analytics.matched_pct + '%'"/>
                        <div class="ab_saas_analytics_label">Matched</div>
                    </div>
                </div>


                <!-- Branch Nav -->
                <div class="ab_saas_branch_nav">
                    <div class="ab_saas_branch_search">
                        <input type="text" placeholder="Search branch..." t-model="state.branchSearchText" class="o_input"/>
                    </div>
                    <div class="ab_saas_branch_chips_wrap">
                        <button t-att-class="'ab_saas_branch_chip' + (state.selected_branch_id ? '' : ' ab_saas_branch_chip_active')" t-on-click="() => this.selectBranch(false)">
                            All Branches
                        </button>
                        <t t-foreach="filteredBranches" t-as="b" t-key="b.id">
                            <button t-att-class="'ab_saas_branch_chip' + (state.selected_branch_id === b.id ? ' ab_saas_branch_chip_active' : '')" t-on-click="() => this.selectBranch(b.id)">
                                <t t-esc="b.name"/>
                                <span class="ab_saas_branch_chip_count" t-esc="' ' + b.count"/>
                            </button>
                        </t>
                        <span class="ab_saas_branch_chip_more" t-if="filteredBranches.length > 8" t-on-click="() => this.state.showAllBranches = !this.state.showAllBranches">
                            <t t-esc="state.showAllBranches ? 'Show less' : ('+' + (state.branches.length - 8) + ' more')"/>
                        </span>
                    </div>
                </div>

                <!-- Selected branch indicator -->
                <div class="ab_saas_branch_selected" t-if="state.selected_branch_id &amp;&amp; selectedBranchLabel">
                    <span class="ab_saas_branch_selected_text">Showing: <t t-esc="selectedBranchLabel"/></span>
                    <button class="ab_saas_branch_selected_clear" t-on-click="() => this.selectBranch(false)">Show All</button>
                </div>

                <!-- Toolbar -->
                <div class="ab_saas_toolbar">
                    <div class="ab_saas_toolbar_left">
                        <div class="ab_saas_search">
                            <span class="ab_saas_search_icon">&#x1F50D;</span>
                            <input type="text" placeholder="Search products..." t-model="state.searchText" t-on-input="onSearchInput" class="o_input"/>
                        </div>
                    </div>
                    <div class="ab_saas_toolbar_right">
                        <span class="ab_saas_selection_pill" t-if="!state.groupByBranch &amp;&amp; selectedCount" t-on-click="() => this.unselectAll()">
                            &#x2611; <t t-esc="selectedCount"/> selected &#x2716;
                        </span>
                        <button class="ab_saas_toolbar_btn" t-if="!state.groupByBranch" t-on-click="() => this.selectAll()" t-att-disabled="!state.total || isReadonly">Select All</button>
                                <button class="ab_saas_toolbar_btn" t-if="!state.groupByBranch" t-on-click="() => this.unselectAll()" t-att-disabled="!selectedCount || isReadonly">Clear</button>
                                <button class="ab_saas_toolbar_btn ab_saas_toolbar_btn--danger" t-if="!state.groupByBranch" t-on-click="() => this.deleteSelected()" t-att-disabled="!selectedCount || isReadonly">Delete</button>
                        <button class="ab_saas_toolbar_btn" t-on-click="toggleGrouping">
                            <t t-if="state.groupByBranch">&#x25BC;</t><t t-else="">&#x25B6;</t> Group
                        </button>
                    </div>
                </div>

                <!-- Selection bar -->
                <div class="ab_saas_selection_bar" t-if="!state.groupByBranch &amp;&amp; selectedCount > 0 &amp;&amp; state.selected_branch_id">
                    <span class="ab_saas_selection_bar_count"><t t-esc="selectedCount"/> products selected</span>
                    <button class="ab_saas_toolbar_btn ab_saas_toolbar_btn--danger" t-on-click="() => this.deleteSelected()" t-att-disabled="isReadonly">Delete Selected</button>
                    <button class="ab_saas_toolbar_btn" t-on-click="() => this.unselectAll()">Clear</button>
                </div>

                <!-- Grid -->
                <div class="ab_saas_grid_container" t-ref="gridContainer">
                    <div class="ab_saas_grid_header">
                        <div class="ab_saas_grid_header_row">
                            <div class="ab_saas_grid_cell ab_saas_grid_cell_check" t-on-click="toggleAllCheck">&#x2611;</div>
                            <div class="ab_saas_grid_cell ab_saas_grid_cell_branch" t-on-click="() => this.sortBy('branch_name')">
                                Branch <span class="ab_saas_sort_icon" t-esc="sortIcon('branch_name')"/>
                            </div>
                            <div class="ab_saas_grid_cell ab_saas_grid_cell_product">
                                Product <span class="ab_saas_sort_icon" t-esc="sortIcon('product_name')" t-on-click="() => this.sortBy('product_name')"/>
                            </div>
                            <div class="ab_saas_grid_cell ab_saas_grid_cell_code">Code</div>
                            <div class="ab_saas_grid_cell ab_saas_grid_cell_qty" t-on-click="() => this.sortBy('system_qty')">
                                Qty <span class="ab_saas_sort_icon" t-esc="sortIcon('system_qty')"/>
                            </div>
                            <div class="ab_saas_grid_cell ab_saas_grid_cell_match">Match</div>
                            <div class="ab_saas_grid_cell ab_saas_grid_cell_note">Note</div>
                        </div>
                    </div>
                    <div class="ab_saas_grid_body" t-ref="gridBody" t-on-scroll="onGridScroll">
                        <t t-if="!state.groupByBranch">
                            <t t-foreach="state.rows" t-as="row" t-key="row.id">
                                <div t-att-class="'ab_saas_grid_row' + (row.selected ? ' ab_saas_grid_row_selected' : '') + (row._highlight ? ' ab_saas_grid_row_highlight' : '')" t-on-click="() => this.toggleRow(row)">
                                    <div class="ab_saas_grid_cell ab_saas_grid_cell_check" t-on-click.stop="() => this.toggleRow(row)">
                                        <span class="ab_saas_checkbox" t-esc="row.selected ? '\u2611' : '\u2610'"/>
                                    </div>
                                    <div class="ab_saas_grid_cell ab_saas_grid_cell_branch">
                                        <span class="ab_saas_branch_pill"><t t-esc="row.branch_name"/></span>
                                    </div>
                                    <div class="ab_saas_grid_cell ab_saas_grid_cell_product">
                                        <div class="ab_saas_product_name" t-if="row.product_name"><t t-esc="row.product_name"/></div>
                                        <div class="ab_saas_product_code" t-if="row.product_code"><t t-esc="row.product_code"/></div>
                                    </div>
                                    <div class="ab_saas_grid_cell ab_saas_grid_cell_code">
                                        <code class="ab_saas_eplus_code" t-if="row.eplus_item_code"><t t-esc="row.eplus_item_code"/></code>
                                    </div>
                                    <div class="ab_saas_grid_cell ab_saas_grid_cell_qty">
                                        <span t-att-class="'ab_saas_qty' + (row.system_qty > 0 ? ' ab_saas_qty_positive' : '')"><t t-esc="row.system_qty"/></span>
                                    </div>
                                    <div class="ab_saas_grid_cell ab_saas_grid_cell_match">
                                        <span t-att-class="'ab_saas_match_badge ab_saas_match_badge--' + row.matched_by"><t t-esc="matchLabel(row.matched_by)"/></span>
                                    </div>
                                    <div class="ab_saas_grid_cell ab_saas_grid_cell_note">
                                        <span class="ab_saas_note" t-if="row.note" t-att-title="row.note"><t t-esc="row.note"/></span>
                                    </div>
                                </div>
                            </t>
                        </t>
                        <t t-else="">
                            <t t-foreach="state.groupedData" t-as="group" t-key="group.branch_id">
                                <div class="ab_saas_grid_group_header" t-on-click="() => this.toggleGroup(group.branch_id)">
                                    <span class="ab_saas_grid_group_arrow"><t t-esc="state.expandedBranches[group.branch_id] ? '\u25BC' : '\u25B6'"/></span>
                                    <span class="ab_saas_grid_group_name"><t t-esc="group.branch_name"/></span>
                                    <span class="ab_saas_grid_group_count"><t t-esc="group.count"/> / <t t-esc="group.total"/> products</span>
                                </div>
                                <t t-if="state.expandedBranches[group.branch_id]">
                                    <t t-foreach="group.rows" t-as="row" t-key="row.id">
                                        <div t-att-class="'ab_saas_grid_row' + (row.selected ? ' ab_saas_grid_row_selected' : '')" t-on-click="() => this.toggleRow(row)">
                                            <div class="ab_saas_grid_cell ab_saas_grid_cell_check" t-on-click.stop="() => this.toggleRow(row)">
                                                <span class="ab_saas_checkbox" t-esc="row.selected ? '\u2611' : '\u2610'"/>
                                            </div>
                                            <div class="ab_saas_grid_cell ab_saas_grid_cell_branch"/>
                                            <div class="ab_saas_grid_cell ab_saas_grid_cell_product">
                                                <div class="ab_saas_product_name" t-if="row.product_name"><t t-esc="row.product_name"/></div>
                                                <div class="ab_saas_product_code" t-if="row.product_code"><t t-esc="row.product_code"/></div>
                                            </div>
                                            <div class="ab_saas_grid_cell ab_saas_grid_cell_code">
                                                <code class="ab_saas_eplus_code" t-if="row.eplus_item_code"><t t-esc="row.eplus_item_code"/></code>
                                            </div>
                                            <div class="ab_saas_grid_cell ab_saas_grid_cell_qty">
                                                <span t-att-class="'ab_saas_qty' + (row.system_qty > 0 ? ' ab_saas_qty_positive' : '')"><t t-esc="row.system_qty"/></span>
                                            </div>
                                            <div class="ab_saas_grid_cell ab_saas_grid_cell_match">
                                                <span t-att-class="'ab_saas_match_badge ab_saas_match_badge--' + row.matched_by"><t t-esc="matchLabel(row.matched_by)"/></span>
                                            </div>
                                            <div class="ab_saas_grid_cell ab_saas_grid_cell_note">
                                                <span class="ab_saas_note" t-if="row.note" t-att-title="row.note"><t t-esc="row.note"/></span>
                                            </div>
                                        </div>
                                    </t>
                                </t>
                            </t>
                        </t>
                        <div class="ab_saas_grid_empty" t-if="(!state.groupByBranch &amp;&amp; !state.rows.length || state.groupByBranch &amp;&amp; !state.groupedData.length) &amp;&amp; !state.loading">
                            <div class="ab_saas_grid_empty_content">
                                <div class="ab_saas_grid_empty_icon">&#x1F50D;</div>
                                <div class="ab_saas_grid_empty_title">No products found</div>
                                <div class="ab_saas_grid_empty_text">Try changing the branch filter or search terms.</div>
                            </div>
                        </div>
                    </div>
                    <div class="ab_saas_grid_footer" t-if="!state.groupByBranch &amp;&amp; state.total > state.rows.length">
                        <span class="ab_saas_grid_footer_text"><t t-esc="state.rows.length"/> of <t t-esc="state.total"/> loaded</span>
                        <button class="ab_saas_load_more" t-on-click="loadMore">Load more</button>
                    </div>
                </div>
            </div>
        </div>
    `;

    static props = { ...standardFieldProps };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.gridContainer = useRef("gridContainer");
        this.gridBody = useRef("gridBody");
        this._searchTimer = null;
        this._loadKey = "";
        this.state = useState({
            analytics: null,
            branches: [],
            selected_branch_id: false,
            branchSearchText: "",
            searchText: "",
            rows: [],
            groupedData: [],
            total: 0,
            loading: false,
            page: 0,
            sortBy: "branch_id",
            sortOrder: "asc",
            groupByBranch: false,
            expandedBranches: {},
            showAllBranches: false,
        });
        onWillStart(() => this._load());
        useExternalListener(window, "keydown", (e) => {
            if (e.key === "Escape" && this.selectedCount) {
                this.unselectAll();
            }
        });
        onPatched(() => this._onPatched());
    }

    _currentKey() {
        const rec = this.props.record;
        if (!rec || !rec.resId) return "";
        const sb = this.state.selected_branch_id;
        const grp = this.state.groupByBranch ? "g" : "f";
        const version = rec.data?.__last_update || rec.data?.write_date || "";
        const search = this.state.searchText || "";
        return `${rec.resId}:${sb}:${version}:${search}:${grp}`;
    }

    get resModel() {
        return this.props.record?.resModel || "ab_self_inventory_request_batch";
    }

    get resId() {
        return this.props.record?.resId;
    }

    get isReadonly() {
        const st = this.props.record?.data?.state;
        return st && st !== "draft";
    }

    _getServerBranchId() {
        const raw = this.props.record?.data?.selected_branch_id;
        if (!raw) return false;
        if (Array.isArray(raw)) return raw[0];
        if (typeof raw === "object") return raw.id;
        return raw;
    }

    async _load() {
        const key = this._currentKey();
        if (!key) return;
        this._loadKey = key;
        const id = this.resId;
        if (!id) return;
        const branchId = this.state.selected_branch_id || false;
        this.state.loading = true;
        try {
            const [analytics, branches, result] = await Promise.all([
                this.orm.call(this.resModel, "action_get_analytics", [[id]], {}),
                this.orm.call(this.resModel, "action_get_branch_counts", [[id]], {}),
                this.orm.call(this.resModel, "action_get_grid_rows", [[id]], {
                    branch_id: branchId,
                    search: this.state.searchText || false,
                    offset: 0,
                    limit: PAGE_SIZE,
                    sort_by: this.state.sortBy,
                    sort_order: this.state.sortOrder,
                }),
            ]);
            if (this._currentKey() !== this._loadKey) {
                return;
            }
            this.state.analytics = analytics;
            this.state.branches = branches;
            const rows = result.rows || [];
            rows.sort((a, b) => (a.selected === b.selected ? 0 : a.selected ? -1 : 1));
            this.state.rows = rows;
            this.state.total = result.total || 0;
            this.state.page = 0;
        } catch (e) {
            console.warn("[DataGrid] load error", e);
            if (this._currentKey() !== this._loadKey) return;
            this.state.analytics = { branch_count: 0, total_products: 0, selected_products: 0, matched_pct: 0 };
            this.state.rows = [];
            this.state.total = 0;
        } finally {
            if (this._currentKey() === this._loadKey) {
                this.state.loading = false;
            }
        }
    }

    async _loadGrouped() {
        const key = this._currentKey();
        if (!key) return;
        this._loadKey = key;
        const id = this.resId;
        if (!id) return;
        this.state.loading = true;
        try {
            const groups = await this.orm.call(this.resModel, "action_get_grouped_rows", [[id]], {
                search: this.state.searchText || false,
                branch_id: this.state.selected_branch_id || false,
            });
            if (this._currentKey() !== this._loadKey) return;
            this.state.groupedData = groups || [];
            for (const g of this.state.groupedData) {
                g.rows.sort((a, b) => (a.selected === b.selected ? 0 : a.selected ? -1 : 1));
                this.state.expandedBranches[g.branch_id] = true;
            }
        } catch (e) {
            console.warn("[DataGrid] loadGrouped error", e);
            if (this._currentKey() !== this._loadKey) return;
            this.state.groupedData = [];
        } finally {
            if (this._currentKey() === this._loadKey) {
                this.state.loading = false;
            }
        }
    }

    _onPatched() {
        // Sync state with record's selected_branch_id (handles sidebar chip clicks)
        // Skip in group mode — branch_id is already in state from chip click or stays false for all
        if (!this.state.groupByBranch) {
            const recBranch = this._getServerBranchId();
            if (recBranch && recBranch !== this.state.selected_branch_id) {
                this.state.selected_branch_id = recBranch;
            }
        }
        const key = this._currentKey();
        if (key && key !== this._loadKey) {
            if (this.state.groupByBranch) {
                this._loadGrouped();
            } else {
                this._load();
            }
        }
    }

    async loadMore() {
        if (this.state.rows.length >= this.state.total || this.state.loading) return;
        const id = this.resId;
        if (!id) return;
        this.state.loading = true;
        try {
            const result = await this.orm.call(this.resModel, "action_get_grid_rows", [[id]], {
                branch_id: this.state.selected_branch_id || false,
                search: this.state.searchText || false,
                offset: this.state.rows.length,
                limit: PAGE_SIZE,
                sort_by: this.state.sortBy,
                sort_order: this.state.sortOrder,
            });
            if (this._currentKey() !== this._loadKey) return;
            this.state.rows = [...this.state.rows, ...(result.rows || [])];
            this.state.total = result.total || this.state.total;
        } catch (e) {
            console.warn("[DataGrid] loadMore error", e);
        } finally {
            if (this._currentKey() === this._loadKey) {
                this.state.loading = false;
            }
        }
    }

    get filteredBranches() {
        const all = this.state.branches || [];
        const q = (this.state.branchSearchText || "").trim().toLowerCase();
        let filtered = q ? all.filter(b => b.name.toLowerCase().includes(q)) : all;
        if (!this.state.showAllBranches && filtered.length > 8) {
            filtered = filtered.slice(0, 8);
        }
        return filtered;
    }

    get selectedCount() {
        if (this.state.groupByBranch) {
            let count = 0;
            for (const g of this.state.groupedData) {
                count += g.rows.filter(r => r.selected).length;
            }
            return count;
        }
        return this.state.rows.filter(r => r.selected).length;
    }

    get selectedBranchLabel() {
        if (!this.state.selected_branch_id) return "";
        const found = this.state.branches.find(b => b.id === this.state.selected_branch_id);
        return found ? found.name : "";
    }

    selectBranch(branchId) {
        this.state.selected_branch_id = branchId;
    }

    onSearchInput() {
        if (this._searchTimer) clearTimeout(this._searchTimer);
        this._searchTimer = setTimeout(() => {
            if (this.state.groupByBranch) {
                this.state.groupedData = [];
                this._loadGrouped();
            } else {
                this.state.rows = [];
                this.state.total = 0;
                this._load();
            }
        }, 350);
    }

    async toggleRow(row) {
        if (!row || !row.id) return;
        const current = row.selected;
        row.selected = !current;
        this.state.rows = [...this.state.rows];
        try {
            const result = await this.orm.call(this.resModel, "action_toggle_line_selection", [[this.resId], row.id], {});
            row.selected = result.selected;
            this.state.rows = [...this.state.rows];
        } catch (e) {
            row.selected = current;
            this.state.rows = [...this.state.rows];
        }
    }

    toggleAllCheck() {
        const visible = this.state.rows;
        if (!visible.length) return;
        const allSelected = visible.every(r => r.selected);
        for (const r of visible) r.selected = !allSelected;
        this.state.rows = [...this.state.rows];
    }

    async unselectAll() {
        const id = this.resId;
        if (!id) return;
        try {
            await this.orm.call(this.resModel, "action_unselect_all_filtered", [[id]], {
                branch_id: this.state.selected_branch_id || false,
                search: this.state.searchText || false,
            });
            for (const r of this.state.rows) r.selected = false;
            this.state.rows = [...this.state.rows];
        } catch (e) {
            console.warn("[DataGrid] unselectAll error", e);
            this.notification.add("Could not clear selections.", { type: "danger" });
        }
    }

    async selectAll() {
        const id = this.resId;
        if (!id) return;
        try {
            await this.orm.call(this.resModel, "action_select_all_filtered", [[id]], {
                branch_id: this.state.selected_branch_id || false,
                search: this.state.searchText || false,
            });
            for (const r of this.state.rows) r.selected = true;
            this.state.rows = [...this.state.rows];
        } catch (e) {
            console.warn("[DataGrid] selectAll error", e);
            this.notification.add("Could not select all.", { type: "danger" });
        }
    }

    async deleteSelected() {
        const id = this.resId;
        if (!id) return;
        const selected = this.state.rows.filter(r => r.selected);
        if (!selected.length) return;
        try {
            await this.orm.call(this.resModel, "action_delete_selected_filtered", [[id]], {
                branch_id: this.state.selected_branch_id || false,
                search: this.state.searchText || false,
            });
            this.state.rows = this.state.rows.filter(r => !r.selected);
            this.state.total = Math.max(0, this.state.total - selected.length);
        } catch (e) {
            console.warn("[DataGrid] deleteSelected error", e);
            this.notification.add("Could not delete selected items.", { type: "danger" });
        }
    }

    toggleGrouping() {
        this.state.groupByBranch = !this.state.groupByBranch;
        if (this.state.groupByBranch) {
            this.state.groupedData = [];
            this._loadGrouped();
        }
    }

    toggleGroup(branchId) {
        const expanded = this.state.expandedBranches[branchId];
        this.state.expandedBranches[branchId] = !expanded;
        this.state.expandedBranches = { ...this.state.expandedBranches };
    }

    sortBy(field) {
        if (!field) return;
        if (this.state.sortBy === field) {
            this.state.sortOrder = this.state.sortOrder === "asc" ? "desc" : "asc";
        } else {
            this.state.sortBy = field;
            this.state.sortOrder = "asc";
        }
        this.state.rows = [];
        this.state.total = 0;
        this._load();
    }

    sortIcon(field) {
        if (this.state.sortBy !== field) return "";
        return this.state.sortOrder === "asc" ? "\u25B2" : "\u25BC";
    }

    matchLabel(value) {
        const labels = { eplus_serial: "E-plus ID", code: "Item Code", none: "Unmatched" };
        return labels[value] || value || "";
    }

    get groupedRows() {
        const groups = {};
        for (const r of this.state.rows) {
            if (!groups[r.branch_id]) {
                groups[r.branch_id] = { branch_id: r.branch_id, branch_name: r.branch_name, count: 0, rows: [] };
            }
            groups[r.branch_id].count++;
            groups[r.branch_id].rows.push(r);
        }
        return Object.values(groups);
    }

    onGridScroll() {}
}

registry.category("fields").add("ab_inventory_data_grid", {
    component: DataGridWidget,
});

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
