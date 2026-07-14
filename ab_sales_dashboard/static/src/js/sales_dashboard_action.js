/** @odoo-module **/

import { Component, onWillStart, onWillUnmount, useState, xml } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

const COLLECTION_LABELS = {
    cash: _t("Cash"),
    delivery: _t("Delivery"),
    contract: _t("Contracts"),
    offer: _t("Offers"),
};

const FILTER_STORAGE_KEY = "ab_sales_dashboard.filters";
const SYNC_POLL_DELAY_MS = 750;

const UI_TEXT = {
    title: _t("Sales Dashboard"),
    subtitle: _t("Abdin Pharmacies - complete overview of sales performance"),
    allStores: _t("All Stores"),
    refreshing: _t("Refreshing..."),
    refreshFromEplus: _t("Refresh from E-Plus"),
    filterByStore: _t("Filter by store"),
    dateFilter: _t("Date Filter"),
    yesterday: _t("Yesterday"),
    last7Days: _t("Last 7 Days"),
    last30Days: _t("Last 30 Days"),
    last90Days: _t("Last 90 Days"),
    dateFrom: _t("Date From"),
    dateTo: _t("Date To"),
    loading: _t("Loading dashboard..."),
    syncing: _t("Syncing..."),
    syncStarted: _t("Dashboard sync started."),
    syncFinished: _t("Dashboard sync finished."),
    syncFailed: _t("Dashboard sync finished with failed days."),
    syncedDays: _t("Synced days"),
    partialStoredSummary: _t("Partial stored summary"),
    reportDataUnavailable: _t("Report data unavailable for this range. Run shorter E-Plus refreshes first to build daily facts."),
    cacheProgress: _t("Cached days"),
    branchDaysSynchronized: _t("branch-days synchronized"),
    notAvailableForSummary: _t("Not available for summary range."),
    totalSales: _t("Total Sales"),
    previousPeriodAverage: _t("vs previous period average"),
    averageDailySales: _t("Average Daily Sales"),
    previous: _t("Previous:"),
    invoiceCount: _t("Invoice Count"),
    totalUnitsSold: _t("Total Units Sold"),
    uniqueProductsSold: _t("Unique Products Sold"),
    totalProductSales: _t("Total Product Sales"),
    avgProductsPerInvoice: _t("Avg. Products / Invoice"),
    storesWithSales: _t("Stores with Sales"),
    avgProductsSoldPerStore: _t("Avg. Products / Store"),
    bearingPercentage: _t("Bearing Percentage"),
    company: _t("Company:"),
    medicineVsNonMedicine: _t("Medicine vs Non-Medicine"),
    medicineSales: _t("Medicine Sales"),
    nonMedicineSales: _t("Non-Medicine Sales"),
    ofTotal: _t("of total"),
    collectionMethodSales: _t("Sales by Collection Method"),
    fourCategories: _t("4 categories"),
    salesByUsers: _t("Sales by Users"),
    rankedDescending: _t("Ranked descending"),
    user: _t("User"),
    percentage: _t("Percentage"),
    topSoldItems: _t("Top Sold Items"),
    saleTimesCurrentBalance: _t("Sales + sale times + current balance"),
    item: _t("Item"),
    saleTimes: _t("Sale Times"),
    currentBalance: _t("Current Balance"),
    unit: _t("unit"),
    customerSales: _t("Customer Sales"),
    invoiceCustomerItems: _t("Invoice + Customer + Items"),
    invoice: _t("Invoice"),
    customer: _t("Customer"),
    items: _t("Items"),
    invoiceTotal: _t("Invoice Total"),
    refreshed: _t("Sales dashboard refreshed."),
};

class SalesDashboardAction extends Component {
    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.ui = UI_TEXT;
        this.syncPollTimer = null;
        this.unmounted = false;
        this.updateFilter = this.updateFilter.bind(this);
        this.onRefresh = this.onRefresh.bind(this);
        this.applyDatePreset = this.applyDatePreset.bind(this);
        this.onStoreSearchInput = this.onStoreSearchInput.bind(this);
        this.selectStore = this.selectStore.bind(this);
        this.toggleStoreMenu = this.toggleStoreMenu.bind(this);
        this.openStoreMenu = this.openStoreMenu.bind(this);
        const savedFilters = this.loadSavedFilters();
        this.state = useState({
            loading: true,
            refreshing: false,
            syncing: false,
            storeMenuOpen: false,
            storeSearch: UI_TEXT.allStores,
            filters: {
                date_from: savedFilters.date_from,
                date_to: savedFilters.date_to,
                store_id: savedFilters.store_id,
            },
            data: null,
            syncProgress: null,
        });
        onWillStart(async () => {
            await this.loadDashboard(false);
            await this.refreshSyncProgress();
            this.resumeSyncPollingIfNeeded();
        });
        onWillUnmount(() => {
            this.unmounted = true;
            this.stopSyncPolling();
        });
    }

    loadSavedFilters() {
        const latestReportDate = this.latestReportDate();
        const defaults = {
            date_from: this.toIsoDate(this.addDays(latestReportDate, -6)),
            date_to: this.toIsoDate(latestReportDate),
            store_id: 0,
        };
        try {
            const rawValue = window.localStorage && window.localStorage.getItem(FILTER_STORAGE_KEY);
            const saved = rawValue ? JSON.parse(rawValue) : {};
            return {
                date_from: this.clampIsoToLatestReportDate(saved.date_from || defaults.date_from),
                date_to: this.clampIsoToLatestReportDate(saved.date_to || defaults.date_to),
                store_id: Number(saved.store_id || 0),
            };
        } catch {
            return defaults;
        }
    }

    persistFilters() {
        try {
            if (window.localStorage) {
                window.localStorage.setItem(FILTER_STORAGE_KEY, JSON.stringify(this.state.filters));
            }
        } catch {
            // Browser storage is optional; the dashboard still works without it.
        }
    }

    async loadDashboard(refresh) {
        this.state.loading = !this.state.data;
        this.state.storeMenuOpen = false;
        if (refresh) {
            this.state.refreshing = true;
        }
        try {
            const data = await this.orm.call("ab.sales.dashboard.snapshot", "get_dashboard_data", [this.state.filters]);
            this.state.data = data;
            this.state.filters.date_from = data.date_from;
            this.state.filters.date_to = data.date_to;
            this.state.filters.store_id = data.store_id || 0;
            this.state.storeSearch = this.storeDisplayName(data.store_id, data.stores);
            this.persistFilters();
        } finally {
            this.state.loading = false;
            if (refresh) {
                this.state.refreshing = false;
            }
        }
    }

    updateFilter(name, value) {
        this.state.filters[name] = name === "store_id" ? Number(value || 0) : value;
    }

    toggleStoreMenu() {
        this.state.storeMenuOpen = !this.state.storeMenuOpen;
    }

    openStoreMenu() {
        this.state.storeMenuOpen = true;
    }

    onStoreSearchInput(ev) {
        this.state.storeSearch = ev.target.value;
        this.state.storeMenuOpen = true;
    }

    selectStore(storeId, storeName) {
        this.state.filters.store_id = Number(storeId || 0);
        this.state.storeSearch = storeName || this.ui.allStores;
        this.state.storeMenuOpen = false;
        this.persistFilters();
        return this.loadDashboard(false);
    }

    applyDatePreset(preset) {
        const latestReportDate = this.latestReportDate();
        let dateFrom = latestReportDate;
        let dateTo = latestReportDate;

        if (preset === "yesterday") {
            dateFrom = latestReportDate;
        } else if (preset === "last_7_days") {
            dateFrom = this.addDays(latestReportDate, -6);
        } else if (preset === "last_30_days") {
            dateFrom = this.addDays(latestReportDate, -29);
        } else if (preset === "last_90_days") {
            dateFrom = this.addDays(latestReportDate, -89);
        }

        this.state.filters.date_from = this.toIsoDate(dateFrom);
        this.state.filters.date_to = this.toIsoDate(dateTo);
        this.persistFilters();
        return this.loadDashboard(false);
    }

    updateCustomDate(name, value) {
        this.updateFilter(name, this.clampIsoToLatestReportDate(value));
        this.persistFilters();
        if (this.state.filters.date_from && this.state.filters.date_to) {
            return this.loadDashboard(false);
        }
    }

    async onRefresh() {
        if (this.state.refreshing) {
            return;
        }
        this.stopSyncPolling();
        this.state.refreshing = true;
        this.state.syncing = true;
        this.persistFilters();
        try {
            const progress = await this.orm.call("ab.sales.dashboard.snapshot", "start_dashboard_sync", [this.state.filters]);
            this.state.syncProgress = progress;
            this.notification.add(this.ui.syncStarted, { type: "info" });
            this.scheduleSyncPoll(0);
        } catch (error) {
            this.state.refreshing = false;
            this.state.syncing = false;
            throw error;
        }
    }

    async refreshSyncProgress() {
        if (!this.state.filters.date_from || !this.state.filters.date_to) {
            this.state.syncProgress = null;
            return null;
        }
        const progress = await this.orm.call("ab.sales.dashboard.snapshot", "get_dashboard_sync_progress", [this.state.filters]);
        this.state.syncProgress = progress && progress.has_sync_state ? progress : null;
        return this.state.syncProgress;
    }

    resumeSyncPollingIfNeeded() {
        const progress = this.state.syncProgress;
        if (progress && progress.is_active) {
            this.state.refreshing = true;
            this.state.syncing = true;
            this.scheduleSyncPoll(0);
        }
    }

    scheduleSyncPoll(delay = SYNC_POLL_DELAY_MS) {
        this.stopSyncPolling();
        if (this.unmounted) {
            return;
        }
        this.syncPollTimer = setTimeout(() => this.pollDashboardSync(), delay);
    }

    stopSyncPolling() {
        if (this.syncPollTimer) {
            clearTimeout(this.syncPollTimer);
            this.syncPollTimer = null;
        }
    }

    async pollDashboardSync() {
        if (this.unmounted) {
            return;
        }
        try {
            const progress = await this.orm.call("ab.sales.dashboard.snapshot", "process_dashboard_sync_day", [this.state.filters]);
            this.state.syncProgress = progress;
            if (progress.is_active) {
                this.scheduleSyncPoll();
                return;
            }

            this.state.refreshing = false;
            this.state.syncing = false;
            await this.loadDashboard(false);
            await this.refreshSyncProgress();
            if (progress.failed_days) {
                this.notification.add(this.ui.syncFailed, { type: "warning" });
            } else if (progress.is_complete) {
                this.notification.add(this.ui.syncFinished, { type: "success" });
            }
        } catch (error) {
            this.state.refreshing = false;
            this.state.syncing = false;
            this.stopSyncPolling();
            const message = (error && error.message) || String(error || "");
            this.notification.add(message || this.ui.syncFailed, { type: "danger" });
        }
    }

    get isRtl() {
        const html = document.documentElement;
        const lang = (html.lang || "").toLowerCase();
        return html.dir === "rtl" || lang.startsWith("ar");
    }

    get direction() {
        return this.isRtl ? "rtl" : "ltr";
    }

    get locale() {
        const lang = (document.documentElement.lang || "").replace("_", "-");
        return this.isRtl ? "ar-EG" : (lang || "en-US");
    }

    addDays(date, days) {
        const result = new Date(date);
        result.setDate(result.getDate() + days);
        return result;
    }

    latestReportDate() {
        return this.addDays(new Date(), -1);
    }

    get latestReportDateIso() {
        return this.toIsoDate(this.latestReportDate());
    }

    clampToLatestReportDate(date) {
        const latestReportDate = this.latestReportDate();
        if (!date || date > latestReportDate) {
            return latestReportDate;
        }
        return date;
    }

    clampIsoToLatestReportDate(value) {
        if (!value) {
            return value;
        }
        return this.toIsoDate(this.clampToLatestReportDate(this.parseIsoDate(value)));
    }

    toIsoDate(date) {
        const localDate = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
        return localDate.toISOString().slice(0, 10);
    }

    sameDate(left, right) {
        return left === this.toIsoDate(right);
    }

    sameRange(dateFrom, dateTo, start, end) {
        return this.sameDate(dateFrom, start) && this.sameDate(dateTo, end);
    }

    parseIsoDate(value) {
        if (!value) {
            return null;
        }
        const [year, month, day] = value.split("-").map((part) => Number(part));
        if (!year || !month || !day) {
            return null;
        }
        return new Date(year, month - 1, day);
    }

    storeDisplayName(storeId, stores) {
        const cleanId = Number(storeId || 0);
        if (!cleanId) {
            return this.ui.allStores;
        }
        const store = (stores || []).find((item) => Number(item.id) === cleanId);
        return store ? store.name : this.ui.allStores;
    }

    get filteredStores() {
        const stores = (this.state.data && this.state.data.stores) || [];
        const search = (this.state.storeSearch || "").trim().toLowerCase();
        if (!search || search === this.ui.allStores.toLowerCase()) {
            return stores.slice(0, 50);
        }
        return stores.filter((store) => (store.name || "").toLowerCase().includes(search)).slice(0, 50);
    }

    get dateFilterLabel() {
        const dateFrom = this.state.filters.date_from;
        const dateTo = this.state.filters.date_to;
        const latestReportDate = this.latestReportDate();

        if (this.sameDate(dateTo, latestReportDate)) {
            if (this.sameDate(dateFrom, latestReportDate)) {
                return this.ui.yesterday;
            }
            if (this.sameDate(dateFrom, this.addDays(latestReportDate, -6))) {
                return this.ui.last7Days;
            }
            if (this.sameDate(dateFrom, this.addDays(latestReportDate, -29))) {
                return this.ui.last30Days;
            }
            if (this.sameDate(dateFrom, this.addDays(latestReportDate, -89))) {
                return this.ui.last90Days;
            }
        }
        if (this.sameRange(dateFrom, dateTo, latestReportDate, latestReportDate)) {
            return this.ui.yesterday;
        }

        if (dateFrom && dateTo) {
            return `${dateFrom} - ${dateTo}`;
        }
        return this.ui.dateFilter;
    }

    money(value) {
        return new Intl.NumberFormat(this.locale, {
            style: "currency",
            currency: "EGP",
            maximumFractionDigits: 0,
        }).format(Number(value || 0));
    }

    number(value) {
        return new Intl.NumberFormat(this.locale, { maximumFractionDigits: 0 }).format(Number(value || 0));
    }

    decimal(value) {
        return new Intl.NumberFormat(this.locale, { maximumFractionDigits: 2 }).format(Number(value || 0));
    }

    pct(value) {
        return `${this.decimal(value)}%`;
    }

    abs(value) {
        return Math.abs(Number(value || 0));
    }

    collectionLabel(category) {
        return COLLECTION_LABELS[category] || category;
    }

    get reportMeta() {
        return (this.state.data && this.state.data.report_meta) || {};
    }

    get reportStatusTone() {
        const meta = this.reportMeta;
        if (meta.coverage_state === "unavailable") {
            return "danger";
        }
        if (meta.coverage_state === "partial") {
            return "warning";
        }
        return "";
    }

    get reportStatusMessage() {
        const meta = this.reportMeta;
        if (!meta.mode) {
            return "";
        }
        if (meta.coverage_state === "unavailable") {
            return this.ui.reportDataUnavailable;
        }
        if (meta.coverage_state === "partial") {
            return `${this.ui.partialStoredSummary}: ${this.number(meta.covered_store_days)} / ${this.number(meta.expected_store_days)} ${this.ui.branchDaysSynchronized}.`;
        }
        return "";
    }

    get cacheProgressVisible() {
        return Boolean(this.progressTotalDays);
    }

    get activeSyncProgress() {
        const progress = this.state.syncProgress;
        return progress && progress.has_sync_state ? progress : null;
    }

    get progressDoneDays() {
        const progress = this.activeSyncProgress;
        if (progress) {
            return Number(progress.done_days || 0);
        }
        return Number(this.reportMeta.fully_covered_days || 0);
    }

    get progressTotalDays() {
        const progress = this.activeSyncProgress;
        if (progress) {
            return Number(progress.requested_days || 0);
        }
        return Number(this.reportMeta.requested_days || 0);
    }

    get cacheProgressPct() {
        const progress = this.activeSyncProgress;
        if (progress) {
            return Math.max(0, Math.min(100, Number(progress.progress_pct || 0)));
        }
        const requestedDays = this.progressTotalDays;
        if (!requestedDays) {
            return 0;
        }
        return Math.max(0, Math.min(100, (100 * this.progressDoneDays) / requestedDays));
    }

    get cacheProgressStyle() {
        return `width: ${this.cacheProgressPct.toFixed(2)}%;`;
    }

    get cacheProgressLabel() {
        const label = this.activeSyncProgress ? this.ui.syncedDays : this.ui.cacheProgress;
        return `${label}: ${this.number(this.progressDoneDays)} / ${this.number(this.progressTotalDays)} (${this.pct(this.cacheProgressPct)})`;
    }

    sectionUnsupported(section) {
        return ((this.reportMeta && this.reportMeta.unsupported_sections) || []).includes(section);
    }

    get medicineTotal() {
        const data = this.state.data || {};
        return Number(data.medicine_sales || 0) + Number(data.non_medicine_sales || 0);
    }

    get medicinePct() {
        return this.medicineTotal ? (100 * Number(this.state.data.medicine_sales || 0)) / this.medicineTotal : 0;
    }

    get nonMedicinePct() {
        return this.medicineTotal ? (100 * Number(this.state.data.non_medicine_sales || 0)) / this.medicineTotal : 0;
    }
}

SalesDashboardAction.template = xml`
<div class="ab_sales_dashboard" t-att-dir="direction">
    <div class="o_control_panel d-flex flex-column gap-3 px-3 pt-2 pb-3 ab_sales_dashboard__control_panel">
        <div class="o_control_panel_main d-flex flex-wrap flex-lg-nowrap justify-content-between align-items-lg-start gap-2 gap-lg-3 flex-grow-1">
            <div class="o_control_panel_breadcrumbs d-flex align-items-center gap-1 order-0 h-lg-100">
                <div class="o_control_panel_main_buttons d-flex gap-1 d-empty-none d-print-none"/>
                <div class="o_breadcrumb d-flex gap-1 text-truncate">
                    <div class="o_last_breadcrumb_item active d-flex fs-4 min-w-0 align-items-center">
                        <span class="min-w-0 text-truncate" t-esc="ui.title"/>
                    </div>
                    <div class="o_control_panel_breadcrumbs_actions d-inline-flex d-print-none"/>
                </div>
                <div class="me-auto"/>
            </div>
            <div class="o_control_panel_actions d-empty-none d-flex align-items-center justify-content-start justify-content-lg-around order-2 order-lg-1 w-100 mw-100 w-lg-auto">
                <div class="d-flex flex-wrap w-100">
                    <div class="o_sp_dashboard_search d-flex flex-wrap flex-lg-nowrap gap-1 gap-lg-2 w-100 w-lg-auto ab_sales_dashboard__filters">
                        <div class="d-flex flex-grow-1 input-group w-auto ab_sales_dashboard__store_search">
                            <div class="o_searchview form-control d-flex align-items-center py-1 border-end-0 gap-1" aria-expanded="false">
                                <button class="btn border-0 p-0" type="button" tabindex="-1">
                                    <i class="oi oi-search me-2"/>
                                </button>
                                <div class="o_searchview_input_container d-flex flex-grow-1 flex-wrap gap-1 mw-100">
                                    <input type="text"
                                           class="o_searchview_input o_input d-print-none flex-grow-1 w-auto border-0 ab_sales_dashboard__store_input"
                                           t-att-title="ui.filterByStore"
                                           t-att-aria-label="ui.filterByStore"
                                           t-att-value="state.storeSearch"
                                           t-on-focus="openStoreMenu"
                                           t-on-input="onStoreSearchInput"/>
                                    <div t-if="state.storeMenuOpen" class="dropdown-menu show ab_sales_dashboard__store_menu">
                                        <button class="dropdown-item" type="button" t-on-mousedown.prevent="() => this.selectStore(0, ui.allStores)" t-esc="ui.allStores"/>
                                        <div class="dropdown-divider"/>
                                        <t t-foreach="filteredStores" t-as="store" t-key="store.id">
                                            <button class="dropdown-item text-truncate" type="button" t-on-mousedown.prevent="() => this.selectStore(store.id, store.name)" t-esc="store.name"/>
                                        </t>
                                    </div>
                                </div>
                            </div>
                            <button class="o_searchview_dropdown_toggler btn btn-outline-secondary o-dropdown-caret rounded-start-0 o-dropdown dropdown-toggle dropdown"
                                    type="button"
                                    tabindex="-1"
                                    t-att-title="ui.filterByStore"
                                    t-on-click="toggleStoreMenu"/>
                        </div>
                        <div class="ab_sales_dashboard__date_inputs">
                            <label class="ab_sales_dashboard__date_field">
                                <span t-esc="ui.dateFrom"/>
                                <input type="date"
                                       class="form-control"
                                       t-att-value="state.filters.date_from"
                                       t-att-max="latestReportDateIso"
                                       t-att-disabled="state.refreshing"
                                       t-on-change="(ev) => this.updateCustomDate('date_from', ev.target.value)"/>
                            </label>
                            <label class="ab_sales_dashboard__date_field">
                                <span t-esc="ui.dateTo"/>
                                <input type="date"
                                       class="form-control"
                                       t-att-value="state.filters.date_to"
                                       t-att-max="latestReportDateIso"
                                       t-att-disabled="state.refreshing"
                                       t-on-change="(ev) => this.updateCustomDate('date_to', ev.target.value)"/>
                            </label>
                        </div>
                        <div class="btn-group ab_sales_dashboard__quick_ranges" role="group" t-att-aria-label="ui.dateFilter">
                            <button class="btn btn-outline-secondary" type="button" t-att-disabled="state.refreshing" t-on-click="() => this.applyDatePreset('yesterday')" t-esc="ui.yesterday"/>
                            <button class="btn btn-outline-secondary" type="button" t-att-disabled="state.refreshing" t-on-click="() => this.applyDatePreset('last_7_days')" t-esc="ui.last7Days"/>
                            <button class="btn btn-outline-secondary" type="button" t-att-disabled="state.refreshing" t-on-click="() => this.applyDatePreset('last_30_days')" t-esc="ui.last30Days"/>
                            <button class="btn btn-outline-secondary" type="button" t-att-disabled="state.refreshing" t-on-click="() => this.applyDatePreset('last_90_days')" t-esc="ui.last90Days"/>
                        </div>
                        <button type="button" class="btn btn-primary" t-on-click="onRefresh" t-att-disabled="state.refreshing" t-att-title="ui.refreshFromEplus">
                            <t t-if="state.refreshing" t-esc="ui.syncing"/>
                            <t t-else="" t-esc="ui.refreshFromEplus"/>
                        </button>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <div class="ab_sales_dashboard__body">
        <t t-if="state.loading &amp;&amp; !state.data">
            <div class="ab_sales_dashboard__empty" t-esc="ui.loading"/>
        </t>
        <t t-elif="state.data">
            <div t-if="cacheProgressVisible" class="ab_sales_dashboard__cache_progress">
                <div class="ab_sales_dashboard__cache_progress_header">
                    <span t-esc="cacheProgressLabel"/>
                </div>
                <div class="ab_sales_dashboard__cache_progress_track">
                    <div class="ab_sales_dashboard__cache_progress_bar" t-att-style="cacheProgressStyle"/>
                </div>
            </div>
            <div t-if="reportStatusMessage" t-att-class="'ab_sales_dashboard__notice ab_sales_dashboard__notice--' + reportStatusTone">
                <t t-esc="reportStatusMessage"/>
            </div>

        <section class="ab_sales_dashboard__kpis">
            <article class="ab_sales_dashboard__kpi ab_sales_dashboard__kpi--wide">
                <span t-esc="ui.totalSales"/>
                <strong t-esc="money(state.data.total_sales)"/>
                <em>
                    <t t-if="state.data.avg_daily_growth_pct &gt;= 0">▲</t>
                    <t t-else="">▼</t>
                    <t t-esc="pct(abs(state.data.avg_daily_growth_pct))"/>
                    <t t-esc="ui.previousPeriodAverage"/>
                </em>
            </article>
            <article class="ab_sales_dashboard__kpi">
                <span t-esc="ui.averageDailySales"/>
                <strong t-esc="money(state.data.avg_daily_sales)"/>
                <em><t t-esc="ui.previous"/> <t t-esc="money(state.data.prev_avg_daily_sales)"/></em>
            </article>
            <article class="ab_sales_dashboard__kpi">
                <span t-esc="ui.invoiceCount"/>
                <strong t-esc="number(state.data.invoice_count)"/>
                <em t-esc="state.data.store_filter_label"/>
            </article>
            <article class="ab_sales_dashboard__kpi">
                <span t-esc="ui.bearingPercentage"/>
                <strong t-esc="pct(state.data.bearing_pct)"/>
                <em><t t-esc="ui.company"/> <t t-esc="money(state.data.company_part_amount)"/></em>
            </article>
        </section>

        <section class="ab_sales_dashboard__split">
            <article class="ab_sales_dashboard__panel">
                <div class="ab_sales_dashboard__panel_header">
                    <h2 t-esc="ui.medicineVsNonMedicine"/>
                    <span><t t-esc="decimal(medicinePct)"/> / <t t-esc="decimal(nonMedicinePct)"/></span>
                </div>
                <div class="ab_sales_dashboard__ratio">
                    <div class="ab_sales_dashboard__ratio_bar">
                        <span t-att-style="'width:' + medicinePct + '%'"/>
                    </div>
                    <div class="ab_sales_dashboard__ratio_values">
                        <div>
                            <span class="ab_sales_dashboard__ratio_label">
                                <i class="ab_sales_dashboard__ratio_marker ab_sales_dashboard__ratio_marker--medicine" aria-hidden="true"/>
                                <t t-esc="ui.medicineSales"/>
                            </span>
                            <strong t-esc="money(state.data.medicine_sales)"/>
                            <em><t t-esc="pct(medicinePct)"/> <t t-esc="ui.ofTotal"/></em>
                        </div>
                        <div>
                            <span class="ab_sales_dashboard__ratio_label">
                                <i class="ab_sales_dashboard__ratio_marker ab_sales_dashboard__ratio_marker--non_medicine" aria-hidden="true"/>
                                <t t-esc="ui.nonMedicineSales"/>
                            </span>
                            <strong t-esc="money(state.data.non_medicine_sales)"/>
                            <em><t t-esc="pct(nonMedicinePct)"/> <t t-esc="ui.ofTotal"/></em>
                        </div>
                    </div>
                </div>
            </article>
            <article class="ab_sales_dashboard__panel">
                <div class="ab_sales_dashboard__panel_header">
                    <h2 t-esc="ui.collectionMethodSales"/>
                    <span t-esc="ui.fourCategories"/>
                </div>
                <div class="ab_sales_dashboard__collection">
                    <t t-foreach="state.data.collection_lines" t-as="line" t-key="line.row_key || line.category || line_index">
                        <div class="ab_sales_dashboard__collection_card">
                            <span t-esc="collectionLabel(line.category)"/>
                            <strong t-esc="money(line.total_sales)"/>
                            <em><t t-esc="pct(line.pct_of_total)"/> <t t-esc="ui.ofTotal"/></em>
                        </div>
                    </t>
                </div>
            </article>
        </section>

        <section class="ab_sales_dashboard__tables">
            <article class="ab_sales_dashboard__panel">
                <div class="ab_sales_dashboard__panel_header">
                    <h2 t-esc="ui.salesByUsers"/>
                    <span t-esc="ui.rankedDescending"/>
                </div>
                <div t-if="sectionUnsupported('sales_by_user')" class="ab_sales_dashboard__section_note" t-esc="ui.notAvailableForSummary"/>
                <table>
                    <thead>
                        <tr><th>#</th><th t-esc="ui.user"/><th t-esc="ui.totalSales"/><th t-esc="ui.percentage"/></tr>
                    </thead>
                    <tbody>
                        <t t-foreach="state.data.user_lines" t-as="line" t-key="line.row_key || line.employee_eplus_id || line.employee_name || line_index">
                            <tr>
                                <td t-esc="line_index + 1"/>
                                <td t-esc="line.employee_name"/>
                                <td t-esc="money(line.total_sales)"/>
                                <td t-esc="pct(line.pct_of_total)"/>
                            </tr>
                        </t>
                    </tbody>
                </table>
            </article>

            <article class="ab_sales_dashboard__panel">
                <div class="ab_sales_dashboard__panel_header">
                    <h2 t-esc="ui.topSoldItems"/>
                    <span t-esc="ui.saleTimesCurrentBalance"/>
                </div>
                <div t-if="sectionUnsupported('top_items')" class="ab_sales_dashboard__section_note" t-esc="ui.notAvailableForSummary"/>
                <table>
                    <thead>
                        <tr><th>#</th><th t-esc="ui.item"/><th t-esc="ui.totalSales"/><th t-esc="ui.saleTimes"/><th t-esc="ui.currentBalance"/></tr>
                    </thead>
                    <tbody>
                        <t t-foreach="state.data.item_lines" t-as="line" t-key="line.row_key || line.eplus_item_id || line.eplus_item_code || line_index">
                            <tr>
                                <td t-esc="line_index + 1"/>
                                <td>
                                    <strong t-esc="line.product_name"/>
                                    <small t-esc="line.eplus_item_code"/>
                                </td>
                                <td t-esc="money(line.total_sales)"/>
                                <td t-esc="number(line.sale_times)"/>
                                <td><t t-esc="decimal(line.current_balance)"/> <t t-esc="ui.unit"/></td>
                            </tr>
                        </t>
                    </tbody>
                </table>
            </article>
        </section>

        <section class="ab_sales_dashboard__panel">
            <div class="ab_sales_dashboard__panel_header">
                <h2 t-esc="ui.customerSales"/>
                <span t-esc="ui.invoiceCustomerItems"/>
            </div>
            <div t-if="sectionUnsupported('customer_sales')" class="ab_sales_dashboard__section_note" t-esc="ui.notAvailableForSummary"/>
            <table>
                <thead>
                    <tr><th t-esc="ui.invoice"/><th t-esc="ui.customer"/><th t-esc="ui.items"/><th t-esc="ui.invoiceTotal"/></tr>
                </thead>
                <tbody>
                    <t t-foreach="state.data.invoice_lines" t-as="line" t-key="line.row_key || line.invoice_no || line_index">
                        <tr>
                            <td t-esc="line.invoice_no"/>
                            <td t-esc="line.customer_name"/>
                            <td t-esc="line.items_summary"/>
                            <td t-esc="money(line.invoice_total)"/>
                        </tr>
                    </t>
                </tbody>
            </table>
        </section>
        </t>
    </div>
</div>
`;

registry.category("actions").add("ab_sales_dashboard.dashboard", SalesDashboardAction);
