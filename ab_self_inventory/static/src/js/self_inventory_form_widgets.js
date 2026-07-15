/** @odoo-module **/
import { _t } from "@web/core/l10n/translation";
import { user } from "@web/core/user";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { Component, useState, xml, useRef, onWillStart, onWillUnmount, onPatched, useExternalListener } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { Dialog } from "@web/core/dialog/dialog";
import { BatchesLoadingOverlay, useBatchLoading } from "./batches_loading_overlay";

function getRecordValue(record, fieldName, fallback = null) {
    const data = record?.data;
    if (!data || !(fieldName in data)) return fallback;
    return data[fieldName] ?? fallback;
}

function getUiLocale() {
    const locale = (user.lang || document.documentElement.lang || navigator.language || "en-US").replace("_", "-");
    return locale.toLowerCase().startsWith("ar") ? "ar-EG" : locale;
}

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
                    <div class="ab_form_hero_deadline_label"><t t-esc="_t('Deadline')"/></div>
                    <div class="ab_form_hero_deadline_date"><t t-esc="deadlineDisplay"/></div>
                </div>
            </div>
            <div class="ab_form_hero_right" t-if="showProgress">
                <div class="ab_progress_stats">
                    <div class="ab_progress_stat">
                        <div class="ab_progress_stat_value"><t t-esc="requestCount"/></div>
                        <div class="ab_progress_stat_label"><t t-esc="_t('Requests')"/></div>
                    </div>
                    <div class="ab_progress_stat">
                        <div class="ab_progress_stat_value"><t t-esc="processCount"/></div>
                        <div class="ab_progress_stat_label"><t t-esc="_t('Processed')"/></div>
                    </div>
                </div>
            </div>
        </div>
    `;
    static props = { ...standardFieldProps };

    setup() { this._t = _t; }

    get recordName() {
        return getRecordValue(this.props.record, this.props.name, "");
    }

    get requesterName() {
        const raw = getRecordValue(this.props.record, "requester_id", null);
        if (!raw) return "";
        if (Array.isArray(raw)) return raw[1] || "";
        if (typeof raw === "object") return raw.display_name || raw.name || "";
        return String(raw);
    }

    get submittedDate() {
        const raw = getRecordValue(this.props.record, "submitted_date", null);
        if (!raw) return null;
        const d = new Date(raw);
        if (isNaN(d.getTime())) return null;
        return d.toLocaleDateString(getUiLocale(), { month: "short", day: "numeric", year: "numeric" });
    }

    get subtitle() {
        const parts = [];
        if (this.requesterName) parts.push(_t("by ") + this.requesterName);
        if (this.submittedDate) parts.push(this.submittedDate);
        return parts.join(" · ") || null;
    }

    get stateValue() {
        return getRecordValue(this.props.record, "state", "");
    }

    get stateLabel() {
        const labels = {
            draft: _t("Draft"),
            submitted: _t("Submitted"),
            cancelled: _t("Cancelled"),
            in_progress: _t("In Progress"),
            completed: _t("Completed"),
        };
        return labels[this.stateValue] || this.stateValue;
    }

    get deadline() {
        return getRecordValue(this.props.record, "deadline", null);
    }

    get deadlineDisplay() {
        const raw = this.deadline;
        if (!raw) return "";
        const d = new Date(raw);
        if (isNaN(d.getTime())) return String(raw);
        return d.toLocaleDateString(getUiLocale(), { month: "short", day: "numeric", year: "numeric" });
    }

    get showProgress() {
        return this.requestCount > 0;
    }

    get requestCount() {
        return Number(getRecordValue(this.props.record, "request_count", 0)) || 0;
    }

    get processCount() {
        return Number(getRecordValue(this.props.record, "process_count", 0)) || 0;
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
        options: { type: Object, optional: true },
    };

    setup() { this._t = _t; }

    static fieldTypeMap = {
        selected_line_count: { type: "items", icon: "items", label: _t("Selected") },
        request_count: { type: "requests", icon: "requests", label: _t("Requests") },
        process_count: { type: "processes", icon: "processes", label: _t("Processed") },
        line_count: { type: "items", icon: "items", label: _t("Total Lines") },
        shortage_qty: { type: "shortage", icon: "shortage", label: _t("Shortage") },
        extra_qty: { type: "extra", icon: "extra", label: _t("Extra") },
    };

    get rawValue() {
        return getRecordValue(this.props.record, this.props.name, 0) || 0;
    }

    get formattedValue() {
        const n = Number(this.rawValue);
        if (isNaN(n)) return "0";
        return n.toLocaleString();
    }

    get cardType() {
        const mapped = KpiCardWidget.fieldTypeMap[this.props.name];
        if (this.props.cardType) return this.props.cardType;
        if (this.props.options?.type) return this.props.options.type;
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
        const iconKey = this.props.cardIcon || this.props.options?.icon || this.cardType;
        return chars[iconKey] || "\u25A0";
    }

    get cardLabel() {
        const mapped = KpiCardWidget.fieldTypeMap[this.props.name];
        if (this.props.cardLabel) return this.props.cardLabel;
        if (this.props.options?.label) return this.props.options.label;
        return mapped ? mapped.label : _t("Value");
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
                <div class="ab_form_empty_text"><t t-esc="_t('No branches assigned yet')"/></div>
            </div>
        </div>
    `;
    static props = { ...standardFieldProps };
    static components = {};

    setup() {
        this._t = _t;
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
        return getRecordValue(this.props.record, this.props.name, null);
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

    get selectedBranchIds() {
        const raw = getRecordValue(this.props.record, "selected_branch_ids", null);
        if (!raw) return [];
        if (raw.currentIds) return [...raw.currentIds];
        if (raw.records) {
            return raw.records.map(r => Array.isArray(r) ? r[0] : (r && r.id));
        }
        if (Array.isArray(raw)) {
            return raw.map(r => Array.isArray(r) ? r[0] : (r && r.id) || r).filter(Boolean);
        }
        return [];
    }

    branchChipClass(branch) {
        const active = branch.id && this.selectedBranchIds.includes(branch.id);
        return "ab_form_branch_chip" + (active ? " ab_form_branch_chip_active" : "");
    }

    async selectBranch(branch) {
        if (!branch.id || !this.props.record) return;
        const record = this.props.record;
        const { model, resId, resModel } = record;
        if (!model || !model.orm || !resId || !resModel) return;
        const current = this.selectedBranchIds;
        const idx = current.indexOf(branch.id);
        let newVal;
        if (idx >= 0) {
            newVal = current.filter(id => id !== branch.id);
        } else {
            newVal = [...current, branch.id];
        }
        await model.orm.write(
            resModel,
            [resId],
            { selected_branch_ids: [[6, 0, newVal]] },
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
                <span class="ab_selected_branch_filter_label"><t t-esc="_t('Showing')"/></span>
                <span class="ab_selected_branch_filter_value"><t t-esc="selectedBranchNames"/></span>
            </div>
            <button t-if="hasSelection" type="button" class="btn btn-secondary btn-sm" t-on-click="clearBranch">
                <t t-esc="_t('All Branches')"/>
            </button>
        </div>
    `;
    static props = { ...standardFieldProps };

    setup() { this._t = _t; }

    get selectedIds() {
        const raw = getRecordValue(this.props.record, this.props.name, null);
        if (!raw) return [];
        if (raw.currentIds) return [...raw.currentIds];
        if (raw.records) return raw.records.map(r => Array.isArray(r) ? r[0] : (r && r.id));
        if (Array.isArray(raw)) return raw.map(r => Array.isArray(r) ? r[0] : (r && r.id) || r).filter(Boolean);
        return [];
    }

    get hasSelection() { return this.selectedIds.length > 0; }

    get selectedBranchNames() {
        const ids = this.selectedIds;
        if (!ids.length) return _t("All branches");
        if (ids.length === 1) return _t("1 branch selected");
        return _t("%s branches selected").replace("%s", ids.length);
    }

    async clearBranch() {
        if (!this.props.record) return;
        const { model, resId, resModel } = this.props.record;
        if (!model || !model.orm || !resId || !resModel) return;
        await model.orm.write(
            resModel,
            [resId],
            { [this.props.name]: [[6, 0, []]] },
            { context: model.context }
        );
        if (typeof model.load === 'function') {
            await model.load();
        }
    }
}

const ROW_HEIGHT = 56;
const PAGE_SIZE = 50;

// ------------------------------------------------------------------
// Analysis Mode Cards Widget
// Selectable card-style radio group for analysis mode
// ------------------------------------------------------------------

class AnalysisModeCards extends Component {
    static template = xml`
        <div class="ab_mode_card_grid">
            <label t-att-class="'ab_mode_card' + (fieldValue === 'top_n' ? ' ab_mode_card--active' : '')" t-on-click="() => this.selectMode('top_n')">
                <div class="ab_mode_card_icon">📈</div>
                <div class="ab_mode_card_title">Top Selling</div>
                <div class="ab_mode_card_desc">Most sold products by qty</div>
            </label>
            <label t-att-class="'ab_mode_card' + (fieldValue === 'min_price' ? ' ab_mode_card--active' : '')" t-on-click="() => this.selectMode('min_price')">
                <div class="ab_mode_card_icon">💰</div>
                <div class="ab_mode_card_title">High Value</div>
                <div class="ab_mode_card_desc">Products above min price</div>
            </label>
            <label t-att-class="'ab_mode_card' + (fieldValue === 'both' ? ' ab_mode_card--active' : '')" t-on-click="() => this.selectMode('both')">
                <div class="ab_mode_card_icon">⚡</div>
                <div class="ab_mode_card_title">Combined</div>
                <div class="ab_mode_card_desc">Top selling + high value</div>
            </label>
        </div>
    `;
    static props = { ...standardFieldProps };

    get fieldValue() {
        return getRecordValue(this.props.record, this.props.name, "top_n");
    }

    async selectMode(value) {
        if (!this.props.record) return;
        const { model, resId, resModel } = this.props.record;
        if (!model || !model.orm || !resId || !resModel) return;
        await model.orm.write(
            resModel, [resId],
            { [this.props.name]: value },
            { context: model.context }
        );
        if (typeof model.load === 'function') {
            await model.load();
        }
    }
}

registry.category("fields").add("ab_inventory_analysis_mode", {
    component: AnalysisModeCards,
});

// ===================================================================
// Data Grid Widget - Modern SaaS grid replacing O2M
// Features: analytics header, branch nav, search, selection, l/loading
// ===================================================================

class DataGridWidget extends Component {
    static template = xml`
        <div class="ab_saas_grid_wrapper" style="position: relative;">
            <div t-att-class="'ab-batches-overlay-fixed' + (loading.state.isLoading ? ' ab-batches-overlay-fixed--visible' : '')">
                <BatchesLoadingOverlay/>
            </div>

            <div class="ab_saas_grid_content" t-if="state.analytics">
                <!-- Analytics Header -->
                <div class="ab_saas_analytics_row" t-if="!hideBranchSummary">
                    <div class="ab_saas_analytics_card ab_saas_analytics_card--branches">
                        <div class="ab_saas_analytics_value" t-esc="state.analytics.branch_count"/>
                        <div class="ab_saas_analytics_label"><t t-esc="_t('Branches')"/></div>
                    </div>
                    <div class="ab_saas_analytics_card ab_saas_analytics_card--products">
                        <div class="ab_saas_analytics_value" t-esc="state.analytics.total_products"/>
                        <div class="ab_saas_analytics_label"><t t-esc="_t('Products')"/></div>
                    </div>
                    <div class="ab_saas_analytics_card ab_saas_analytics_card--selected">
                        <div class="ab_saas_analytics_value" t-esc="state.analytics.selected_products"/>
                        <div class="ab_saas_analytics_label"><t t-esc="_t('Selected')"/></div>
                    </div>
                    <div class="ab_saas_analytics_card ab_saas_analytics_card--matched">
                        <div class="ab_saas_analytics_value" t-esc="state.analytics.matched_pct + '%'"/>
                        <div class="ab_saas_analytics_label"><t t-esc="_t('Matched')"/></div>
                    </div>
                </div>


                <!-- Branch Nav -->
                <div class="ab_saas_branch_nav" t-if="!hideBranchSummary">
                    <div class="ab_saas_branch_search">
                        <input type="text" t-att-placeholder="_t('Search branch...')" t-model="state.branchSearchText" class="o_input"/>
                    </div>
                    <div class="ab_saas_branch_chips_wrap">
                        <button t-att-class="'ab_saas_branch_chip' + (state.selected_branch_ids.length ? '' : ' ab_saas_branch_chip_active')" t-on-click="() => this.selectBranch(false)">
                            <t t-esc="_t('All Branches')"/>
                        </button>
                        <t t-foreach="filteredBranches" t-as="b" t-key="b.id">
                            <button t-att-class="'ab_saas_branch_chip' + (state.selected_branch_ids.includes(b.id) ? ' ab_saas_branch_chip_active' : '')" t-on-click="() => this.selectBranch(b.id)">
                                <t t-esc="b.name"/>
                                <span class="ab_saas_branch_chip_count" t-esc="' ' + b.count"/>
                            </button>
                        </t>
                        <span class="ab_saas_branch_chip_more" t-if="filteredBranches.length > 8" t-on-click="() => this.state.showAllBranches = !this.state.showAllBranches">
                            <t t-esc="state.showAllBranches ? _t('Show less') : ('+' + (state.branches.length - 8) + _t(' more'))"/>
                        </span>
                    </div>
                </div>

                <!-- Selected branch indicator -->
                <div class="ab_saas_branch_selected" t-if="!hideBranchSummary &amp;&amp; state.selected_branch_ids.length &amp;&amp; selectedBranchLabel">
                    <span class="ab_saas_branch_selected_text" t-esc="_t('Showing:') + ' ' + selectedBranchLabel"/>
                    <button class="ab_saas_branch_selected_clear" t-on-click="() => this.selectBranch(false)"><t t-esc="_t('Show All')"/></button>
                </div>

                <!-- Toolbar -->
                <div class="ab_saas_toolbar">
                    <div class="ab_saas_toolbar_left">
                        <div t-att-class="'ab_saas_search' + (state.searchGlow ? ' ab_saas_search--glow' : '')">
                            <span class="ab_saas_search_icon">&#x1F50D;</span>
                            <input type="text" t-ref="searchInput" t-att-placeholder="_t('Search products...')" t-on-input="onSearchInput" class="o_input"/>
                        </div>
                    </div>
                    <div class="ab_saas_toolbar_right" t-if="!isProcessColumns">
                        <button class="ab_saas_toolbar_btn ab_saas_toolbar_btn--primary" t-on-click="() => this.openAddLine()" t-att-disabled="isReadonly"><t t-esc="_t('Add Line')"/></button>
                        <button class="ab_saas_toolbar_btn" t-if="!state.groupByBranch" t-on-click="() => this.selectAll()" t-att-disabled="!state.total || isReadonly"><t t-esc="_t('Select All')"/></button>
                        <button class="ab_saas_toolbar_btn" t-if="!state.groupByBranch" t-on-click="() => this.unselectAll()" t-att-disabled="!selectedTotal || isReadonly"><t t-esc="_t('Unselect All')"/></button>
                        <button class="ab_saas_toolbar_btn ab_saas_toolbar_btn--danger" t-if="!state.groupByBranch" t-on-click="() => this.deleteSelected()" t-att-disabled="!selectedTotal || isReadonly"><t t-esc="_t('Delete Selected')"/></button>
                        <button class="ab_saas_toolbar_btn" t-if="!hideBranchSummary" t-on-click="toggleGrouping">
                            <t t-if="state.groupByBranch">&#x25BC;</t><t t-else="">&#x25B6;</t> <t t-esc="_t('Group')"/>
                        </button>
                    </div>
                </div>

                <!-- Selection bar -->
                <div class="ab_saas_selection_bar" t-if="!isProcessColumns &amp;&amp; !state.groupByBranch &amp;&amp; selectedTotal > 0">
                    <span class="ab_saas_selection_bar_count">
                        <span class="ab_selection_badge"><t t-esc="selectedTotal"/></span>
                        <t t-esc="_t('products selected')"/>
                    </span>
                    <button class="ab_saas_toolbar_btn ab_saas_toolbar_btn--danger" t-on-click="() => this.deleteSelected()" t-att-disabled="isReadonly"><t t-esc="_t('Delete')"/></button>
                    <button class="ab_saas_toolbar_btn" t-on-click="() => this.unselectAll()"><t t-esc="_t('Clear')"/></button>
                </div>

                <!-- Grid -->
                <div class="ab_saas_grid_container" t-ref="gridContainer">
                    <div t-att-class="'ab_saas_grid_header' + (isRequestColumns ? ' ab_saas_grid_header--request' : '') + (isProcessColumns ? ' ab_saas_grid_header--process' : '')">
                        <div t-att-class="'ab_saas_grid_header_row' + (isRequestColumns ? ' ab_saas_grid_header_row--request' : '') + (isProcessColumns ? ' ab_saas_grid_header_row--process' : '')">
                            <t t-if="isProcessColumns">
                                <div class="ab_saas_grid_cell ab_saas_grid_cell_source"><t t-esc="_t('Source')"/></div>
                                <div class="ab_saas_grid_cell ab_saas_grid_cell_product">
                                    <t t-esc="_t('Product')"/> <span class="ab_saas_sort_icon" t-esc="sortIcon('product_name')" t-on-click="() => this.sortBy('product_name')"/>
                                </div>
                                <div class="ab_saas_grid_cell ab_saas_grid_cell_eplus"><t t-esc="_t('Code')"/></div>
                                <div class="ab_saas_grid_cell ab_saas_grid_cell_qty" t-on-click="() => this.sortBy('system_qty')">
                                    <t t-esc="_t('E-stock Qty')"/> <span class="ab_saas_sort_icon" t-esc="sortIcon('system_qty')"/>
                                </div>
                                <div class="ab_saas_grid_cell ab_saas_grid_cell_actual" t-on-click="() => this.sortBy('actual_qty')">
                                    <t t-esc="_t('Actual Qty')"/> <span class="ab_saas_sort_icon" t-esc="sortIcon('actual_qty')"/>
                                </div>
                                <div class="ab_saas_grid_cell ab_saas_grid_cell_difference" t-on-click="() => this.sortBy('difference_qty')">
                                    <t t-esc="_t('Difference')"/> <span class="ab_saas_sort_icon" t-esc="sortIcon('difference_qty')"/>
                                </div>
                                <div class="ab_saas_grid_cell ab_saas_grid_cell_shortage" t-on-click="() => this.sortBy('shortage_qty')">
                                    <t t-esc="_t('Shortage')"/> <span class="ab_saas_sort_icon" t-esc="sortIcon('shortage_qty')"/>
                                </div>
                                <div class="ab_saas_grid_cell ab_saas_grid_cell_extra" t-on-click="() => this.sortBy('extra_qty')">
                                    <t t-esc="_t('Extra')"/> <span class="ab_saas_sort_icon" t-esc="sortIcon('extra_qty')"/>
                                </div>
                                <div class="ab_saas_grid_cell ab_saas_grid_cell_explanation"><t t-esc="_t('Explanation')"/></div>
                            </t>
                            <t t-else="">
                                <div class="ab_saas_grid_cell ab_saas_grid_cell_check" t-on-click="toggleAllCheck">☑</div>
                                <div class="ab_saas_grid_cell ab_saas_grid_cell_branch" t-if="!isRequestColumns" t-on-click="() => this.sortBy('branch_name')">
                                    <t t-esc="_t('Branch')"/> <span class="ab_saas_sort_icon" t-esc="sortIcon('branch_name')"/>
                                </div>
                                <div class="ab_saas_grid_cell ab_saas_grid_cell_product">
                                    <t t-esc="_t('Product')"/> <span class="ab_saas_sort_icon" t-esc="sortIcon('product_name')" t-on-click="() => this.sortBy('product_name')"/>
                                </div>
                                <div class="ab_saas_grid_cell ab_saas_grid_cell_eplus"><t t-esc="_t('Code')"/></div>
                                <div class="ab_saas_grid_cell ab_saas_grid_cell_qty" t-on-click="() => this.sortBy('system_qty')">
                                    <t t-esc="_t('E-stock Qty')"/> <span class="ab_saas_sort_icon" t-esc="sortIcon('system_qty')"/>
                                </div>
                                <div class="ab_saas_grid_cell ab_saas_grid_cell_price"><t t-esc="_t('Sell Price')"/></div>
                                <div class="ab_saas_grid_cell ab_saas_grid_cell_sold"><t t-esc="_t('Sold Qty')"/></div>
                                <div class="ab_saas_grid_cell ab_saas_grid_cell_note"><t t-esc="_t('Note')"/></div>
                            </t>
                        </div>
                    </div>
                    <div t-att-class="'ab_saas_grid_body' + (isRequestColumns ? ' ab_saas_grid_body--request' : '') + (isProcessColumns ? ' ab_saas_grid_body--process' : '')" t-ref="gridBody" t-on-scroll="onGridScroll">
                        <t t-if="!state.groupByBranch">
                            <t t-foreach="state.rows" t-as="row" t-key="row.id">
                                <t t-if="isProcessColumns">
                                    <div t-att-class="'ab_saas_grid_row ab_saas_grid_row--process' + (row._highlight ? ' ab_saas_grid_row_highlight' : '')">
                                        <div class="ab_saas_grid_cell ab_saas_grid_cell_source">
                                            <span t-att-class="'ab_saas_source_badge ' + (row.requested ? 'ab_saas_source_badge--requested' : 'ab_saas_source_badge--manual')">
                                                <t t-esc="row.requested ? _t('Requested') : _t('Manual')"/>
                                            </span>
                                        </div>
                                        <div class="ab_saas_grid_cell ab_saas_grid_cell_product">
                                            <div class="ab_saas_product_name" t-if="row.product_name"><t t-esc="row.product_name"/></div>
                                        </div>
                                        <div class="ab_saas_grid_cell ab_saas_grid_cell_eplus">
                                            <code class="ab_saas_eplus_code" t-if="row.eplus_item_code"><t t-esc="row.eplus_item_code"/></code>
                                        </div>
                                        <div class="ab_saas_grid_cell ab_saas_grid_cell_qty">
                                            <span t-att-class="'ab_saas_qty' + (row.system_qty > 0 ? ' ab_saas_qty_positive' : '')"><t t-esc="row.system_qty"/></span>
                                        </div>
                                        <div class="ab_saas_grid_cell ab_saas_grid_cell_actual">
                                            <input type="number" step="0.001" class="o_input ab_saas_grid_input ab_saas_grid_input_qty" t-att-value="row.actual_qty" t-att-disabled="isReadonly" t-on-click.stop="() => {}" t-on-change="(ev) => this.updateProcessRow(row, 'actual_qty', ev.target.value)"/>
                                        </div>
                                        <div class="ab_saas_grid_cell ab_saas_grid_cell_difference">
                                            <span t-att-class="'ab_saas_qty ' + (row.difference_qty > 0 ? 'ab_saas_qty_extra' : row.difference_qty &lt; 0 ? 'ab_saas_qty_shortage' : '')"><t t-esc="row.difference_qty"/></span>
                                        </div>
                                        <div class="ab_saas_grid_cell ab_saas_grid_cell_shortage">
                                            <span t-if="row.shortage_qty" class="ab_saas_qty ab_saas_qty_shortage"><t t-esc="row.shortage_qty"/></span>
                                        </div>
                                        <div class="ab_saas_grid_cell ab_saas_grid_cell_extra">
                                            <span t-if="row.extra_qty" class="ab_saas_qty ab_saas_qty_extra"><t t-esc="row.extra_qty"/></span>
                                        </div>
                                        <div class="ab_saas_grid_cell ab_saas_grid_cell_explanation">
                                            <input type="text" class="o_input ab_saas_grid_input" t-att-value="row.explanation" t-att-disabled="isReadonly" t-on-click.stop="() => {}" t-on-change="(ev) => this.updateProcessRow(row, 'explanation', ev.target.value)"/>
                                        </div>
                                    </div>
                                </t>
                                <t t-else="">
                                    <div t-att-class="'ab_saas_grid_row' + (isRequestColumns ? ' ab_saas_grid_row--request' : '') + (row.selected ? ' ab_saas_grid_row_selected' : '') + (row._highlight ? ' ab_saas_grid_row_highlight' : '')" t-on-click="() => this.toggleRow(row)">
                                        <div class="ab_saas_grid_cell ab_saas_grid_cell_check" t-on-click.stop="() => this.toggleRow(row)">
                                            <span class="ab_saas_checkbox" t-esc="row.selected ? '\u2611' : '\u2610'"/>
                                        </div>
                                        <div class="ab_saas_grid_cell ab_saas_grid_cell_branch" t-if="!isRequestColumns">
                                            <span class="ab_saas_branch_pill"><t t-esc="row.branch_name"/></span>
                                        </div>
                                        <div class="ab_saas_grid_cell ab_saas_grid_cell_product">
                                            <div class="ab_saas_product_name" t-if="row.product_name"><t t-esc="row.product_name"/></div>
                                        </div>
                                        <div class="ab_saas_grid_cell ab_saas_grid_cell_eplus">
                                            <code class="ab_saas_eplus_code" t-if="row.eplus_item_code"><t t-esc="row.eplus_item_code"/></code>
                                        </div>
                                        <div class="ab_saas_grid_cell ab_saas_grid_cell_qty">
                                            <span t-att-class="'ab_saas_qty' + (row.system_qty > 0 ? ' ab_saas_qty_positive' : '')"><t t-esc="row.system_qty"/></span>
                                        </div>
                                        <div class="ab_saas_grid_cell ab_saas_grid_cell_price">
                                            <span class="ab_saas_price" t-if="row.sell_price"><t t-esc="row.sell_price"/></span>
                                        </div>
                                        <div class="ab_saas_grid_cell ab_saas_grid_cell_sold">
                                            <span class="ab_saas_sold" t-if="row.sold_qty"><t t-esc="row.sold_qty"/></span>
                                        </div>
                                        <div class="ab_saas_grid_cell ab_saas_grid_cell_note">
                                            <span class="ab_saas_note" t-if="row.note" t-att-title="row.note"><t t-esc="row.note"/></span>
                                        </div>
                                    </div>
                                </t>
                            </t>
                        </t>
                        <t t-else="">
                            <t t-foreach="state.groupedData" t-as="group" t-key="group.branch_id">
                                <div class="ab_saas_grid_group_header" t-on-click="() => this.toggleGroup(group.branch_id)">
                                    <span class="ab_saas_grid_group_arrow"><t t-esc="state.expandedBranches[group.branch_id] ? '\u25BC' : '\u25B6'"/></span>
                                    <span class="ab_saas_grid_group_name"><t t-esc="group.branch_name"/></span>
                                    <span class="ab_saas_grid_group_count"><t t-esc="group.count"/> / <t t-esc="group.total"/> <t t-esc="_t('products')"/></span>
                                </div>
                                <t t-if="state.expandedBranches[group.branch_id]">
                                    <t t-foreach="group.rows" t-as="row" t-key="row.id">
                                        <div t-att-class="'ab_saas_grid_row' + (isRequestColumns ? ' ab_saas_grid_row--request' : '') + (row.selected ? ' ab_saas_grid_row_selected' : '')" t-on-click="() => this.toggleRow(row)">
                                            <div class="ab_saas_grid_cell ab_saas_grid_cell_check" t-on-click.stop="() => this.toggleRow(row)">
                                                <span class="ab_saas_checkbox" t-esc="row.selected ? '\u2611' : '\u2610'"/>
                                            </div>
                                            <div class="ab_saas_grid_cell ab_saas_grid_cell_branch" t-if="!isRequestColumns"/>
                                            <div class="ab_saas_grid_cell ab_saas_grid_cell_product">
                                                <div class="ab_saas_product_name" t-if="row.product_name"><t t-esc="row.product_name"/></div>
                                            </div>
                                            <div class="ab_saas_grid_cell ab_saas_grid_cell_eplus">
                                                <code class="ab_saas_eplus_code" t-if="row.eplus_item_code"><t t-esc="row.eplus_item_code"/></code>
                                            </div>
                                            <div class="ab_saas_grid_cell ab_saas_grid_cell_qty">
                                                <span t-att-class="'ab_saas_qty' + (row.system_qty > 0 ? ' ab_saas_qty_positive' : '')"><t t-esc="row.system_qty"/></span>
                                            </div>
                                            <div class="ab_saas_grid_cell ab_saas_grid_cell_price">
                                                <span class="ab_saas_price" t-if="row.sell_price"><t t-esc="row.sell_price"/></span>
                                            </div>
                                            <div class="ab_saas_grid_cell ab_saas_grid_cell_sold">
                                                <span class="ab_saas_sold" t-if="row.sold_qty"><t t-esc="row.sold_qty"/></span>
                                            </div>
                                            <div class="ab_saas_grid_cell ab_saas_grid_cell_note">
                                                <span class="ab_saas_note" t-if="row.note" t-att-title="row.note"><t t-esc="row.note"/></span>
                                            </div>
                                        </div>
                                    </t>
                                </t>
                            </t>
                        </t>
                        <div class="ab_saas_grid_empty" t-if="(!state.groupByBranch &amp;&amp; !state.rows.length || state.groupByBranch &amp;&amp; !state.groupedData.length) &amp;&amp; !loading.state.isLoading">
                            <div class="ab_saas_grid_empty_content">
                                <svg class="ab_saas_empty_svg" width="120" height="100" viewBox="0 0 120 100" fill="none" xmlns="http://www.w3.org/2000/svg">
                                    <rect x="20" y="30" width="80" height="55" rx="8" stroke="#CBD5E1" stroke-width="1.5" fill="#F8FAFC"/>
                                    <rect x="36" y="48" width="18" height="6" rx="3" fill="#E2E8F0"/>
                                    <rect x="58" y="48" width="18" height="6" rx="3" fill="#E2E8F0"/>
                                    <rect x="80" y="48" width="10" height="6" rx="3" fill="#E2E8F0"/>
                                    <rect x="36" y="60" width="14" height="6" rx="3" fill="#E2E8F0"/>
                                    <rect x="54" y="60" width="22" height="6" rx="3" fill="#E2E8F0"/>
                                    <rect x="80" y="60" width="10" height="6" rx="3" fill="#E2E8F0"/>
                                    <circle cx="14" cy="42" r="6" fill="#DBEAFE" stroke="#93C5FD" stroke-width="1.2"/>
                                    <circle cx="106" cy="42" r="6" fill="#DBEAFE" stroke="#93C5FD" stroke-width="1.2"/>
                                    <path d="M60 18 L66 26 L54 26 Z" fill="#E2E8F0" stroke="#CBD5E1" stroke-width="1"/>
                                    <circle cx="60" cy="12" r="3" fill="#E2E8F0" stroke="#CBD5E1" stroke-width="1"/>
                                    <path d="M56 12 C56 6, 64 6, 64 12" fill="none" stroke="#CBD5E1" stroke-width="1.2"/>
                                </svg>
                                <div class="ab_saas_grid_empty_title"><t t-esc="_t('No products found')"/></div>
                                <div class="ab_saas_grid_empty_text"><t t-esc="_t('Try changing the branch filter or search terms to find products.')"/></div>
                                <button class="ab_saas_toolbar_btn ab_saas_toolbar_btn--primary" t-on-click="() => this.openAddLine()" t-att-disabled="isReadonly" t-if="!isProcessColumns &amp;&amp; !state.searchText &amp;&amp; !state.selected_branch_ids.length" style="margin-top: 16px;">
                                    <t t-esc="_t('Add Products')"/>
                                </button>
                            </div>
                        </div>
                    </div>
                    <div class="ab_saas_grid_footer" t-if="!state.groupByBranch &amp;&amp; state.total">
                        <span class="ab_saas_grid_footer_text">
                            <t t-esc="rangeLabel"/>
                            <t t-if="!isProcessColumns &amp;&amp; selectedTotal"> · <t t-esc="selectedLabel"/></t>
                        </span>
                        <div class="ab_saas_pagination">
                            <button class="ab_saas_pagination_btn" t-on-click="previousPage" t-att-disabled="!hasPreviousPage || loading.state.isLoading">
                                <t t-esc="_t('Previous')"/>
                            </button>
                            <span class="ab_saas_pagination_label">
                                <t t-esc="_t('Page')"/> <t t-esc="currentPage"/> / <t t-esc="pageCount"/>
                            </span>
                            <button class="ab_saas_pagination_btn" t-on-click="nextPage" t-att-disabled="!hasNextPage || loading.state.isLoading">
                                <t t-esc="_t('Next')"/>
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;

    static components = { BatchesLoadingOverlay };
    static props = {
        ...standardFieldProps,
        options: { type: Object, optional: true },
    };

    setup() {
        this._t = _t;
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.gridContainer = useRef("gridContainer");
        this.gridBody = useRef("gridBody");
        this.searchInput = useRef("searchInput");
        this._searchTimer = null;
        this._searchGlowTimer = null;
        this._loadKey = "";
        this.loading = useBatchLoading({ minDuration: 600 });
        this.state = useState({
            analytics: null,
            branches: [],
            selected_branch_ids: [],
            branchSearchText: "",
            searchText: "",
            rows: [],
            groupedData: [],
            total: 0,
            selectedTotal: 0,
            page: 0,
            sortBy: "branch_id",
            sortOrder: "asc",
            groupByBranch: false,
            expandedBranches: {},
            showAllBranches: false,
            branchSelectionInitialized: false,
            serverBranchKey: "",
            bulkDropdownOpen: false,
            searchGlow: false,
        });
        onWillStart(() => this._load());
        useExternalListener(window, "keydown", (e) => {
            if (e.key === "Escape" && this.selectedTotal) {
                this.unselectAll();
            }
            if (e.key === "Escape" && this.state.bulkDropdownOpen) {
                this.state.bulkDropdownOpen = false;
            }
        });
        useExternalListener(window, "click", (e) => {
            if (this.state.bulkDropdownOpen) {
                this.state.bulkDropdownOpen = false;
            }
        });
        onPatched(() => this._onPatched());
        onWillUnmount(() => {
            if (this._searchTimer) clearTimeout(this._searchTimer);
            if (this._searchGlowTimer) clearTimeout(this._searchGlowTimer);
        });
    }

    _currentKey() {
        const rec = this.props.record;
        if (!rec || !rec.resId) return "";
        const branchIds = this.state.selected_branch_ids || [];
        const key = branchIds.length ? [...branchIds].sort((a, b) => a - b).join(",") : "all";
        const grp = this.state.groupByBranch ? "g" : "f";
        const version = getRecordValue(rec, "__last_update", "") || getRecordValue(rec, "write_date", "");
        const lineCount = getRecordValue(rec, this.props.name, "");
        const search = this.state.searchText || "";
        return `${rec.resId}:${key}:${version}:${lineCount}:${search}:${grp}:${this.state.page}:${this.state.sortBy}:${this.state.sortOrder}`;
    }

    get resModel() {
        return this.props.record?.resModel || "ab_self_inventory_request_batch";
    }

    get resId() {
        return this.props.record?.resId;
    }

    get isReadonly() {
        const st = getRecordValue(this.props.record, "state", null);
        if (this.isProcessColumns) {
            return !Boolean(getRecordValue(this.props.record, "can_sync_requested_stock", false));
        }
        return st && st !== "draft";
    }

    get isProcessColumns() {
        return this.resModel === "ab_self_inventory_process" || Boolean(this.props.options && this.props.options.process_columns);
    }

    get isRequestColumns() {
        return !this.isProcessColumns && (
            this.resModel === "ab_self_inventory_request" || Boolean(this.props.options && this.props.options.request_columns)
        );
    }

    get hideBranchSummary() {
        return this.isProcessColumns || this.resModel === "ab_self_inventory_request" || Boolean(this.props.options && this.props.options.hide_branch_summary);
    }

    _getServerBranchIds() {
        const raw = getRecordValue(this.props.record, "selected_branch_ids", null);
        if (!raw) return [];
        if (raw.currentIds) return [...raw.currentIds];
        if (raw.records) return raw.records.map(r => Array.isArray(r) ? r[0] : (r && r.id));
        if (Array.isArray(raw)) return raw.map(r => Array.isArray(r) ? r[0] : (r && r.id) || r).filter(Boolean);
        return [];
    }

    _branchKey(branchIds) {
        return branchIds.length ? [...branchIds].sort((a, b) => a - b).join(",") : "";
    }

    _syncServerBranchSelection() {
        const serverBranchIds = this._getServerBranchIds();
        const serverBranchKey = this._branchKey(serverBranchIds);
        if (!this.state.branchSelectionInitialized || serverBranchKey !== this.state.serverBranchKey) {
            this.state.selected_branch_ids = serverBranchIds;
            this.state.serverBranchKey = serverBranchKey;
            this.state.branchSelectionInitialized = true;
            this.state.page = 0;
        }
    }

    async _load(silent = false) {
        this._syncServerBranchSelection();
        const key = this._currentKey();
        if (!key) return;
        this._loadKey = key;
        const id = this.resId;
        if (!id) return;
        const branchIds = this.state.selected_branch_ids.length ? this.state.selected_branch_ids : false;
        if (!silent) this.loading.show();
        try {
            const [analytics, branches, result] = await Promise.all([
                this.orm.call(this.resModel, "action_get_analytics", [[id]], {}),
                this.orm.call(this.resModel, "action_get_branch_counts", [[id]], {}),
                this.orm.call(this.resModel, "action_get_grid_rows", [[id]], {
                    branch_ids: branchIds,
                    search: this.state.searchText || false,
                    offset: this.state.page * PAGE_SIZE,
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
            if (!this.isProcessColumns) {
                rows.sort((a, b) => (a.selected === b.selected ? 0 : a.selected ? -1 : 1));
            }
            this.state.rows = rows;
            this.state.total = result.total || 0;
            this.state.selectedTotal = result.selected_total || 0;
            if (!rows.length && this.state.total && this.state.page > 0) {
                this.state.page = Math.max(0, this.pageCount - 1);
                await this._load(silent);
            }
        } catch (e) {
            if (this._currentKey() !== this._loadKey) return;
            this.state.analytics = { branch_count: 0, total_products: 0, selected_products: 0, matched_pct: 0 };
            this.state.rows = [];
            this.state.total = 0;
            this.state.selectedTotal = 0;
        } finally {
            if (this._currentKey() === this._loadKey) {
                if (!silent) this.loading.hide();
            }
        }
    }

    async _loadGrouped(silent = false) {
        this._syncServerBranchSelection();
        const key = this._currentKey();
        if (!key) return;
        this._loadKey = key;
        const id = this.resId;
        if (!id) return;
        const branchIds = this.state.selected_branch_ids.length ? this.state.selected_branch_ids : false;
        if (!silent) this.loading.show();
        try {
            const groups = await this.orm.call(this.resModel, "action_get_grouped_rows", [[id]], {
                search: this.state.searchText || false,
                branch_ids: branchIds,
            });
            if (this._currentKey() !== this._loadKey) return;
            this.state.groupedData = groups || [];
            for (const g of this.state.groupedData) {
                if (!this.isProcessColumns) {
                    g.rows.sort((a, b) => (a.selected === b.selected ? 0 : a.selected ? -1 : 1));
                }
                this.state.expandedBranches[g.branch_id] = true;
            }
        } catch (e) {
            if (this._currentKey() !== this._loadKey) return;
            this.state.groupedData = [];
        } finally {
            if (this._currentKey() === this._loadKey) {
                if (!silent) this.loading.hide();
            }
        }
    }

    _onPatched() {
        this._syncServerBranchSelection();
        const key = this._currentKey();
        if (key && key !== this._loadKey) {
            if (this.state.groupByBranch) {
                this._loadGrouped();
            } else {
                this._load();
            }
        }
    }

    async goToPage(page) {
        if (this.loading.state.isLoading || this.state.groupByBranch) return;
        const nextPage = Math.max(0, Math.min(page, this.pageCount - 1));
        if (nextPage === this.state.page) return;
        this.state.page = nextPage;
        await this._load();
    }

    async previousPage() {
        await this.goToPage(this.state.page - 1);
    }

    async nextPage() {
        await this.goToPage(this.state.page + 1);
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

    get pageCount() {
        return Math.max(1, Math.ceil((this.state.total || 0) / PAGE_SIZE));
    }

    get currentPage() {
        return Math.min(this.state.page + 1, this.pageCount);
    }

    get hasPreviousPage() {
        return this.state.page > 0;
    }

    get hasNextPage() {
        return this.state.page + 1 < this.pageCount;
    }

    get rangeStart() {
        if (!this.state.total) return 0;
        return this.state.page * PAGE_SIZE + 1;
    }

    get rangeEnd() {
        return Math.min((this.state.page + 1) * PAGE_SIZE, this.state.total || 0);
    }

    get rangeLabel() {
        return _t("%(start)s-%(end)s of %(total)s")
            .replace("%(start)s", this.rangeStart)
            .replace("%(end)s", this.rangeEnd)
            .replace("%(total)s", this.state.total || 0);
    }

    get selectedTotal() {
        if (this.isProcessColumns) return 0;
        return Number(this.state.selectedTotal || 0);
    }

    get selectedLabel() {
        return _t("%s selected").replace("%s", this.selectedTotal);
    }

    get allFilteredSelected() {
        if (this.isProcessColumns) return false;
        return Boolean(this.state.total && this.selectedTotal >= this.state.total);
    }

    get selectedCount() {
        if (this.isProcessColumns) return 0;
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
        const ids = this.state.selected_branch_ids;
        if (!ids.length) return "";
        const names = this.state.branches.filter(b => ids.includes(b.id)).map(b => b.name);
        if (!names.length) return ids.length + _t(" branches");
        if (names.length <= 3) return names.join(", ");
        return names.slice(0, 2).join(", ") + " +" + (names.length - 2) + _t(" more");
    }

    selectBranch(branchId) {
        const ids = this.state.selected_branch_ids;
        if (!branchId) {
            this.state.selected_branch_ids = [];
        } else {
            const idx = ids.indexOf(branchId);
            if (idx >= 0) {
                this.state.selected_branch_ids = ids.filter(id => id !== branchId);
            } else {
                this.state.selected_branch_ids = [...ids, branchId];
            }
        }
        this.state.page = 0;
        this.state.rows = [];
        this.state.groupedData = [];
        this.state.total = 0;
        this.state.selectedTotal = 0;
        if (this.state.groupByBranch) {
            this._loadGrouped();
        } else {
            this._load();
        }
    }

    onSearchInput(ev) {
        if (this._searchTimer) clearTimeout(this._searchTimer);
        const value = ev.target.value;
        this._searchTimer = setTimeout(() => {
            this.state.searchText = value;
            this.state.page = 0;
            if (this.state.groupByBranch) {
                this.state.groupedData = [];
                this._loadGrouped(true);
            } else {
                this.state.rows = [];
                this.state.total = 0;
                this._load(true);
            }
        }, 350);
    }

    async toggleRow(row) {
        if (this.isProcessColumns) return;
        if (!row || !row.id) return;
        const current = row.selected;
        row.selected = !current;
        this.state.rows = [...this.state.rows];
        try {
            const result = await this.orm.call(this.resModel, "action_toggle_line_selection", [[this.resId], row.id], {});
            row.selected = result.selected;
            this.state.selectedTotal += row.selected ? 1 : -1;
            this.state.selectedTotal = Math.max(0, Math.min(this.state.selectedTotal, this.state.total));
            this.state.rows = [...this.state.rows];
        } catch (e) {
            row.selected = current;
            this.state.rows = [...this.state.rows];
        }
    }

    async toggleAllCheck() {
        if (this.isProcessColumns) return;
        if (this.isReadonly || this.state.groupByBranch || !this.state.total) return;
        if (this.allFilteredSelected) {
            await this.unselectAll();
        } else {
            await this.selectAll();
        }
    }

    async selectAll() {
        if (this.isProcessColumns) return;
        try {
            await this.orm.call(this.resModel, "action_select_all_filtered", [[this.resId]], {
                branch_ids: this.state.selected_branch_ids.length ? this.state.selected_branch_ids : false,
                search: this.state.searchText || false,
            });
            await this._load(true);
        } catch (e) {
            this.notification.add(_t("Could not select all."), { type: "danger" });
        }
    }

    async unselectAll() {
        if (this.isProcessColumns) return;
        const id = this.resId;
        if (!id) return;
        try {
            await this.orm.call(this.resModel, "action_unselect_all_filtered", [[this.resId]], {
                branch_ids: this.state.selected_branch_ids.length ? this.state.selected_branch_ids : false,
                search: this.state.searchText || false,
            });
            await this._load(true);
        } catch (e) {
            this.notification.add(_t("Could not clear selections."), { type: "danger" });
        }
    }

    async deleteSelected() {
        if (this.isProcessColumns) return;
        const id = this.resId;
        if (!id) return;
        if (!this.selectedTotal) return;
        try {
            await this.orm.call(this.resModel, "action_delete_selected_filtered", [[this.resId]], {
                branch_ids: this.state.selected_branch_ids.length ? this.state.selected_branch_ids : false,
                search: this.state.searchText || false,
            });
            await this._load(true);
        } catch (e) {
            this.notification.add(_t("Could not delete selected items."), { type: "danger" });
        }
    }

    async openAddLine() {
        if (this.isProcessColumns) return;
        if (!this.resId || this.isReadonly) return;
        try {
            const action = await this.orm.call(this.resModel, "action_open_manual_add_line_wizard", [[this.resId]], {});
            await this.action.doAction(action, {
                onClose: async () => {
                    this.state.rows = [];
                    this.state.groupedData = [];
                    this.state.total = 0;
                    if (this.state.groupByBranch) {
                        await this._loadGrouped();
                    } else {
                        await this._load();
                    }
                },
            });
        } catch (e) {
            this.notification.add(_t("Could not open Add Line."), { type: "danger" });
        }
    }

    toggleGrouping() {
        if (this.isProcessColumns) return;
        this.state.groupByBranch = !this.state.groupByBranch;
        if (this.state.groupByBranch) {
            this.state.groupedData = [];
            this._loadGrouped();
        }
    }

    toggleBulkDropdown() {
        this.state.bulkDropdownOpen = !this.state.bulkDropdownOpen;
    }

    closeDropdown(fn) {
        this.state.bulkDropdownOpen = false;
        if (typeof fn === "function") fn.call(this);
    }

    async selectAllMatching() {
        if (this.isProcessColumns) return;
        await this.selectAll();
        this.focusProductSearch();
    }

    async updateProcessRow(row, field, value) {
        if (!this.isProcessColumns || !row || !row.id || this.isReadonly) return;
        const oldValue = row[field];
        let nextValue = value;
        if (field === "actual_qty") {
            nextValue = value === "" || value === null || value === undefined ? 0 : Number(value);
            if (Number.isNaN(nextValue)) {
                this.notification.add(_t("Actual quantity must be numeric."), { type: "danger" });
                return;
            }
        }
        if (oldValue === nextValue) return;
        row[field] = nextValue;
        this.state.rows = [...this.state.rows];
        try {
            const result = await this.orm.call(this.resModel, "action_update_process_line", [[this.resId], row.id, { [field]: nextValue }], {});
            if (result && result.row) {
                Object.assign(row, result.row);
            }
            this.state.rows = [...this.state.rows];
        } catch (e) {
            row[field] = oldValue;
            this.state.rows = [...this.state.rows];
            this.notification.add(_t("Could not update inventory line."), { type: "danger" });
        }
    }

    focusProductSearch() {
        this.state.searchGlow = true;
        if (this._searchGlowTimer) clearTimeout(this._searchGlowTimer);
        setTimeout(() => {
            const input = this.searchInput.el;
            if (input) {
                input.focus();
                input.select?.();
            }
        }, 0);
        this._searchGlowTimer = setTimeout(() => {
            this.state.searchGlow = false;
            this._searchGlowTimer = null;
        }, 3000);
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
        this.state.page = 0;
        this.state.rows = [];
        this.state.total = 0;
        this._load();
    }

    sortIcon(field) {
        if (this.state.sortBy !== field) return "";
        return this.state.sortOrder === "asc" ? "\u25B2" : "\u25BC";
    }

    matchLabel(value) {
        const labels = { eplus_serial: _t("E-plus ID"), code: _t("Item Code"), none: _t("Unmatched") };
        return labels[value] || value || "";
    }

    get footerText() {
        return _t("%(a)s of %(b)s loaded").replace("%(a)s", this.state.rows.length).replace("%(b)s", this.state.total);
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
        <Dialog size="'md'" title.translate="Assigned Branches">
            <div class="ab_branch_dialog">
                <div class="ab_branch_dialog_search">
                    <input type="text" class="o_input" t-att-placeholder="_t('Search Branch...')" t-model="state.searchText"/>
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
        this._t = _t;
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
                    <div class="ab_progress_stat_label"><t t-esc="_t('Requested')"/></div>
                </div>
                <div class="ab_progress_stat">
                    <div class="ab_progress_stat_value"><t t-esc="processCount"/></div>
                    <div class="ab_progress_stat_label"><t t-esc="_t('Processed')"/></div>
                </div>
            </div>
        </div>
    `;
    static props = { ...standardFieldProps };

    setup() { this._t = _t; }

    get requestCount() {
        return Number(getRecordValue(this.props.record, "request_count", 0)) || 0;
    }

    get processCount() {
        return Number(getRecordValue(this.props.record, "process_count", 0)) || 0;
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

    setup() { this._t = _t; }

    get stateValue() {
        return getRecordValue(this.props.record, "state", "");
    }

    get submittedDate() {
        const raw = getRecordValue(this.props.record, "submitted_date", null);
        if (!raw) return null;
        const d = new Date(raw);
        if (isNaN(d.getTime())) return null;
        return d.toLocaleDateString(getUiLocale(), { month: "short", day: "numeric", year: "numeric" });
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
            title: _t("Batch Created"),
            date: null,
        });

        if (state === "in_progress" || state === "submitted" || state === "cancelled") {
            items.push({
                type: "in_progress",
                title: _t("In Progress"),
                date: null,
            });
        }

        if (state === "submitted" || state === "cancelled") {
            items.push({
                type: "completed",
                title: _t("Submitted"),
                date: this.submittedDate,
            });
        }

        if (state === "cancelled") {
            items.push({
                type: "cancelled",
                title: _t("Cancelled"),
                date: this.cancelledDate,
            });
        }

        return items;
    }
}

registry.category("fields").add("ab_inventory_timeline", {
    component: TimelineWidget,
});
