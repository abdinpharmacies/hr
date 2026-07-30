/** @odoo-module **/

import { Component, onWillStart, onWillUnmount, onMounted, useState, useRef, xml } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { CoreInput, CoreSearchSelect, CoreSelect } from "@ab_core_ui/core_ui/components/input/input";
import { money, number, decimal, pct } from "./utils/formatters.js";
import { KpiCard } from "./components/kpi_card.js";
import { DonutChart } from "./components/donut_chart.js";
import { BarChart } from "./components/bar_chart.js";
import { RankingTable } from "./components/ranking_table.js";
import { DataTable } from "./components/data_table.js";
import { LoadingSkeleton } from "./components/loading_skeleton.js";
import { ThemeToggle } from "./components/theme_toggle.js";

const THEME_STORAGE_KEY = "ab_sales_dashboard.theme";
const COLLECTION_LABELS = {
    cash: _t("Cash"),
    delivery: _t("Delivery"),
    contract: _t("Contracts"),
    offer: _t("Offers"),
};

const FILTER_STORAGE_KEY = "ab_sales_dashboard.filters";
const SYNC_POLL_DELAY_MS = 750;
const DATE_FILTER_KEYS = new Set([
    "day", "yesterday", "last_7_days", "last_30_days", "last_90_days", "month", "year", "custom",
]);

const INVOICE_COLUMNS = [
    { field: "invoice_no", label: _t("Invoice") },
    { field: "customer_name", label: _t("Customer") },
    { field: "items_summary", label: _t("Items"), format: "truncate", maxLen: 50 },
    { field: "invoice_total", label: _t("Total"), format: "money" },
];

const FRONTEND_TRANSLATION_TERMS = [
    _t("% of Total"),
    _t("30 Days"),
    _t("7 Days"),
    _t("90 Days"),
    _t("Abdin Pharmacies"),
    _t("Abdin Pharmacies - performance overview"),
    _t("Active Stores"),
    _t("Avg. Daily Sales"),
    _t("Back to Reports"),
    _t("Balance"),
    _t("Bearing %"),
    _t("Browse, compare, and manage historical sales report snapshots."),
    _t("Code"),
    _t("Collection Analysis"),
    _t("Company:"),
    _t("Could not load all records."),
    _t("Customer Bearing"),
    _t("Customer Sales"),
    _t("Data Source"),
    _t("Date"),
    _t("Distribution"),
    _t("Filter by store"),
    _t("Growth"),
    _t("Invoice #"),
    _t("Invoice + Customer + Items"),
    _t("Invoice Details"),
    _t("Items / Invoice"),
    _t("Live Data"),
    _t("Loading report..."),
    _t("Medicine vs Non-Medicine"),
    _t("Monitor and execute coverage reconciliation tasks across branches."),
    _t("Month"),
    _t("No Report Data"),
    _t("No Snapshot"),
    _t("No collection data available."),
    _t("No invoice data available."),
    _t("No item data available."),
    _t("No records found."),
    _t("No snapshot found."),
    _t("No user data available."),
    _t("Non-Medicine Sales"),
    _t("Not available for summary range."),
    _t("Only stored snapshot rows are available."),
    _t("Page"),
    _t("Percentage"),
    _t("Prev:"),
    _t("Product Sales"),
    _t("Products / Store"),
    _t("Ranked descending"),
    _t("Reconciliation processors"),
    _t("Refresh from E-Plus"),
    _t("Sales + stock balance"),
    _t("Sales Performance Report"),
    _t("Sales Reports Library"),
    _t("Sales by Collection Method"),
    _t("Sales by User"),
    _t("Sales by Users"),
    _t("Sales reports archive"),
    _t("Search"),
    _t("Share"),
    _t("Syncing..."),
    _t("Top Sold Items"),
    _t("Unique Products"),
    _t("Year"),
    _t("branch-days synchronized"),
    _t("categories"),
    _t("invoices"),
    _t("items"),
    _t("of"),
    _t("records"),
    _t("users"),
    _t("vs previous period"),
];
void FRONTEND_TRANSLATION_TERMS;

class SalesDashboardAction extends Component {
    static components = {
        CoreInput, CoreSearchSelect, CoreSelect,
        KpiCard, DonutChart, BarChart, RankingTable, DataTable, LoadingSkeleton, ThemeToggle,
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.syncPollTimer = null;
        this.sectionSearchTimers = {};
        this.sectionRequestVersions = {};
        this.unmounted = false;
        this.updateFilter = this.updateFilter.bind(this);
        this.onRefresh = this.onRefresh.bind(this);
        this.applyDatePreset = this.applyDatePreset.bind(this);
        this.applyDaySelection = this.applyDaySelection.bind(this);
        this.onStoreSearchInput = this.onStoreSearchInput.bind(this);
        this.selectStore = this.selectStore.bind(this);
        this.toggleStoreMenu = this.toggleStoreMenu.bind(this);
        this.toggleMobileFilters = this.toggleMobileFilters.bind(this);
        this.openStoreMenu = this.openStoreMenu.bind(this);
        this.toggleTheme = this.toggleTheme.bind(this);
        this.rootRef = useRef("dashboardRoot");

        const savedFilters = this.loadSavedFilters();
        const savedTheme = this.loadSavedTheme();
        this.state = useState({
            loading: true,
            refreshing: false,
            syncing: false,
            storeMenuOpen: false,
            mobileFiltersOpen: false,
            storeSearch: _t("All Stores"),
            theme: savedTheme,
            activeDateFilter: savedFilters.active_date_filter,
            filters: {
                date_from: savedFilters.date_from,
                date_to: savedFilters.date_to,
                store_id: savedFilters.store_id,
            },
            data: null,
            syncProgress: null,
            sectionPages: {
                sales_by_user: this.emptySectionPage(),
                top_items: this.emptySectionPage(),
                customer_sales: this.emptySectionPage(),
            },
        });

        onWillStart(async () => {
            await this.loadDashboard(false);
            await this.refreshSyncProgress();
            this.resumeSyncPollingIfNeeded();
        });
        onWillUnmount(() => {
            this.unmounted = true;
            this.stopSyncPolling();
            for (const timer of Object.values(this.sectionSearchTimers)) {
                clearTimeout(timer);
            }
        });
    }

    // -- Section helpers --
    emptySectionPage() {
        return { rows: [], page: 1, pageSize: 20, totalCount: 0, totalPages: 1, search: "", loading: false, available: false, limited: false, error: false };
    }

    // -- Filter persistence --
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
                active_date_filter: DATE_FILTER_KEYS.has(saved.active_date_filter) ? saved.active_date_filter : "last_7_days",
            };
        } catch {
            return { ...defaults, active_date_filter: "last_7_days" };
        }
    }

    persistFilters() {
        try {
            if (window.localStorage) {
                window.localStorage.setItem(FILTER_STORAGE_KEY, JSON.stringify({
                    ...this.state.filters,
                    active_date_filter: this.state.activeDateFilter,
                }));
            }
        } catch { /* optional */ }
    }

    // -- Theme persistence --
    loadSavedTheme() {
        try {
            const raw = window.localStorage && window.localStorage.getItem(THEME_STORAGE_KEY);
            return raw === "light" ? "light" : "dark";
        } catch { return "dark"; }
    }

    persistTheme() {
        try {
            if (window.localStorage) {
                window.localStorage.setItem(THEME_STORAGE_KEY, this.state.theme);
            }
        } catch { /* optional */ }
    }

    toggleTheme(theme) {
        if (theme === this.state.theme) return;
        const el = this.rootRef.el;
        if (el) el.classList.add("sd-theme-transition");
        this.state.theme = theme;
        this.persistTheme();
        if (el) {
            setTimeout(() => el.classList.remove("sd-theme-transition"), 400);
        }
    }

    // -- Dashboard loading --
    async loadDashboard(refresh) {
        this.state.loading = !this.state.data;
        this.state.storeMenuOpen = false;
        if (refresh) { this.state.refreshing = true; }
        try {
            const data = await this.orm.call("ab.sales.dashboard.snapshot", "get_dashboard_data", [this.state.filters]);
            this.state.data = data;
            this.state.filters.date_from = data.date_from;
            this.state.filters.date_to = data.date_to;
            this.state.filters.store_id = data.store_id || 0;
            this.state.storeSearch = this.storeDisplayName(data.store_id, data.stores);
            this.persistFilters();
            this.initializeSectionPages(data);
            this.loadAvailableSectionPages();
        } finally {
            this.state.loading = false;
            if (refresh) { this.state.refreshing = false; }
        }
    }

    updateFilter(name, value) {
        this.state.filters[name] = name === "store_id" ? Number(value || 0) : value;
    }

    toggleStoreMenu() { this.state.storeMenuOpen = !this.state.storeMenuOpen; }
    openStoreMenu() { this.state.storeMenuOpen = true; }

    onStoreSearchInput(valueOrEvent) {
        this.state.storeSearch = this.inputValue(valueOrEvent) || "";
        this.state.storeMenuOpen = true;
    }

    selectStore(storeId, storeName) {
        this.state.filters.store_id = Number(storeId || 0);
        this.state.storeSearch = storeName || _t("All Stores");
        this.state.storeMenuOpen = false;
        this.persistFilters();
        return this.loadDashboard(false);
    }

    // -- Date presets --
    applyDatePreset(preset) {
        const latest = this.latestReportDate();
        let dateFrom = latest;
        if (preset === "yesterday") { dateFrom = latest; }
        else if (preset === "last_7_days") { dateFrom = this.addDays(latest, -6); }
        else if (preset === "last_30_days") { dateFrom = this.addDays(latest, -29); }
        else if (preset === "last_90_days") { dateFrom = this.addDays(latest, -89); }
        this.state.filters.date_from = this.toIsoDate(dateFrom);
        this.state.filters.date_to = this.toIsoDate(latest);
        this.state.activeDateFilter = preset;
        this.persistFilters();
        return this.loadDashboard(false);
    }

    inputValue(valueOrEvent) {
        return typeof valueOrEvent === "object" && valueOrEvent && valueOrEvent.target ? valueOrEvent.target.value : valueOrEvent;
    }

    applyMonthSelection(valueOrEvent) {
        const value = this.inputValue(valueOrEvent);
        if (!value) return;
        const [year, month] = value.split("-").map(Number);
        const dateFrom = new Date(year, month - 1, 1);
        const dateTo = this.clampToLatestReportDate(new Date(year, month, 0));
        this.state.activeDateFilter = "month";
        return this.applyExplicitDateRange(dateFrom, dateTo);
    }

    applyDaySelection(valueOrEvent) {
        const value = this.clampIsoToLatestReportDate(this.inputValue(valueOrEvent));
        if (!value) return;
        this.state.filters.date_from = value;
        this.state.filters.date_to = value;
        this.state.activeDateFilter = "day";
        this.persistFilters();
        return this.loadDashboard(false);
    }

    applyYearSelection(valueOrEvent) {
        const year = Number(this.inputValue(valueOrEvent) || 0);
        if (!year) return;
        const dateFrom = new Date(year, 0, 1);
        const dateTo = this.clampToLatestReportDate(new Date(year, 11, 31));
        this.state.activeDateFilter = "year";
        return this.applyExplicitDateRange(dateFrom, dateTo);
    }

    applyExplicitDateRange(dateFrom, dateTo) {
        this.state.filters.date_from = this.toIsoDate(dateFrom);
        this.state.filters.date_to = this.toIsoDate(dateTo);
        this.persistFilters();
        return this.loadDashboard(false);
    }

    updateCustomDate(name, value) {
        this.updateFilter(name, this.clampIsoToLatestReportDate(value));
        this.state.activeDateFilter = "custom";
        this.persistFilters();
        if (this.state.filters.date_from && this.state.filters.date_to) {
            return this.loadDashboard(false);
        }
    }

    // -- Refresh / Sync --
    async onRefresh() {
        if (this.state.refreshing) return;
        this.stopSyncPolling();
        this.state.refreshing = true;
        this.state.syncing = true;
        this.persistFilters();
        try {
            const progress = await this.orm.call("ab.sales.dashboard.snapshot", "start_dashboard_sync", [this.state.filters]);
            this.state.syncProgress = progress;
            this.notification.add(_t("Dashboard sync started."), { type: "info" });
            this.scheduleSyncPoll(0);
        } catch (error) {
            this.state.refreshing = false;
            this.state.syncing = false;
            throw error;
        }
    }

    // -- Section pagination --
    initializeSectionPages(data) {
        const initialRows = {
            sales_by_user: data.user_lines || [],
            top_items: data.item_lines || [],
            customer_sales: data.invoice_lines || [],
        };
        const unsupported = new Set(((data.report_meta || {}).unsupported_sections) || []);
        for (const section of Object.keys(initialRows)) {
            const s = this.state.sectionPages[section];
            Object.assign(s, {
                rows: initialRows[section], page: 1, pageSize: 20, totalCount: initialRows[section].length, totalPages: 1,
                search: "", loading: false, available: Boolean(data.has_snapshot) && !unsupported.has(section), limited: false, error: false,
            });
            this.sectionRequestVersions[section] = (this.sectionRequestVersions[section] || 0) + 1;
        }
    }

    loadAvailableSectionPages() {
        for (const section of Object.keys(this.state.sectionPages)) {
            if (this.state.sectionPages[section].available) {
                this.loadSectionPage(section, 1);
            }
        }
    }

    async loadSectionPage(section, page) {
        const s = this.state.sectionPages[section];
        if (!s || !s.available || this.unmounted) return;
        const ver = (this.sectionRequestVersions[section] || 0) + 1;
        this.sectionRequestVersions[section] = ver;
        s.loading = true;
        s.error = false;
        const filters = { ...this.state.filters };
        try {
            const result = await this.orm.call("ab.sales.dashboard.snapshot", "get_dashboard_section_page", [filters, section, page, s.search]);
            if (this.unmounted || this.sectionRequestVersions[section] !== ver) return;
            let rows = result.rows || [];
            if (section === "top_items") {
                const balances = new Map(((this.state.data && this.state.data.item_lines) || []).map(r => [Number(r.eplus_item_id || 0), r.current_balance]));
                rows = rows.map(r => balances.has(Number(r.eplus_item_id || 0)) ? { ...r, current_balance: balances.get(Number(r.eplus_item_id || 0)) } : r);
            }
            Object.assign(s, {
                rows, page: Number(result.page || 1), pageSize: Number(result.page_size || 20),
                totalCount: Number(result.total_count || 0), totalPages: Math.max(Number(result.total_pages || 1), 1),
                available: result.available !== false, limited: Boolean(result.limited), error: false,
            });
        } catch {
            if (this.sectionRequestVersions[section] === ver) s.error = true;
        } finally {
            if (this.sectionRequestVersions[section] === ver) s.loading = false;
        }
    }

    onSectionSearchInput(section, valueOrEvent) {
        const s = this.state.sectionPages[section];
        s.search = (this.inputValue(valueOrEvent) || "").slice(0, 100);
        clearTimeout(this.sectionSearchTimers[section]);
        this.sectionSearchTimers[section] = setTimeout(() => this.loadSectionPage(section, 1), 300);
    }

    changeSectionPage(section, direction) {
        const s = this.state.sectionPages[section];
        const nextPage = Math.min(Math.max(s.page + direction, 1), s.totalPages);
        if (!s.loading && nextPage !== s.page) this.loadSectionPage(section, nextPage);
    }

    sectionRowNumber(section, index) {
        const s = this.state.sectionPages[section];
        return ((s.page - 1) * s.pageSize) + index + 1;
    }

    sectionUnsupported(section) {
        return ((this.reportMeta && this.reportMeta.unsupported_sections) || []).includes(section);
    }

    // -- Sync progress --
    async refreshSyncProgress() {
        if (!this.state.filters.date_from || !this.state.filters.date_to) { this.state.syncProgress = null; return null; }
        const progress = await this.orm.call("ab.sales.dashboard.snapshot", "get_dashboard_sync_progress", [this.state.filters]);
        this.state.syncProgress = progress && progress.has_sync_state ? progress : null;
        return this.state.syncProgress;
    }

    resumeSyncPollingIfNeeded() {
        const p = this.state.syncProgress;
        if (p && p.is_active) { this.state.refreshing = true; this.state.syncing = true; this.scheduleSyncPoll(0); }
    }

    scheduleSyncPoll(delay = SYNC_POLL_DELAY_MS) {
        this.stopSyncPolling();
        if (this.unmounted) return;
        this.syncPollTimer = setTimeout(() => this.pollDashboardSync(), delay);
    }

    stopSyncPolling() { if (this.syncPollTimer) { clearTimeout(this.syncPollTimer); this.syncPollTimer = null; } }

    async pollDashboardSync() {
        if (this.unmounted) return;
        try {
            const progress = await this.orm.call("ab.sales.dashboard.snapshot", "process_dashboard_sync_day", [this.state.filters]);
            this.state.syncProgress = progress;
            if (progress.is_active) { this.scheduleSyncPoll(); return; }
            this.state.refreshing = false;
            this.state.syncing = false;
            await this.loadDashboard(false);
            await this.refreshSyncProgress();
            if (progress.last_status === "source_unavailable") {
                this.notification.add(_t("E-Plus is unavailable. Dashboard sync is paused; try again after the connection is restored."), { type: "warning" });
            } else if (progress.failed_days) {
                this.notification.add(_t("Dashboard sync finished with failed days."), { type: "warning" });
            } else if (progress.is_complete) {
                this.notification.add(_t("Dashboard sync finished."), { type: "success" });
            }
        } catch (error) {
            this.state.refreshing = false;
            this.state.syncing = false;
            this.stopSyncPolling();
            const message = (error && error.message) || String(error || "");
            this.notification.add(message || _t("Dashboard sync failed."), { type: "danger" });
        }
    }

    // -- Date helpers --
    addDays(date, days) { const r = new Date(date); r.setDate(r.getDate() + days); return r; }
    latestReportDate() { return this.addDays(new Date(), -1); }
    get latestReportDateIso() { return this.toIsoDate(this.latestReportDate()); }

    get monthOptions() {
        const latest = this.latestReportDate();
        const formatter = new Intl.DateTimeFormat(this.locale, { month: "long", year: "numeric" });
        const options = [];
        for (let i = 0; i < 36; i++) {
            const m = new Date(latest.getFullYear(), latest.getMonth() - i, 1);
            options.push({ value: `${m.getFullYear()}-${String(m.getMonth() + 1).padStart(2, "0")}`, label: formatter.format(m) });
        }
        return options;
    }

    get yearOptions() { const y = this.latestReportDate().getFullYear(); return Array.from({ length: 10 }, (_, i) => `${y - i}`); }

    get selectedMonthValue() {
        const f = this.parseIsoDate(this.state.filters.date_from);
        const t = this.parseIsoDate(this.state.filters.date_to);
        if (!f || !t || f.getDate() !== 1) return "";
        const exp = this.clampToLatestReportDate(new Date(f.getFullYear(), f.getMonth() + 1, 0));
        return this.sameDate(this.state.filters.date_to, exp) ? `${f.getFullYear()}-${String(f.getMonth() + 1).padStart(2, "0")}` : "";
    }

    get selectedDayValue() { return this.state.filters.date_from === this.state.filters.date_to ? this.state.filters.date_from : ""; }

    get selectedYearValue() {
        const f = this.parseIsoDate(this.state.filters.date_from);
        const t = this.parseIsoDate(this.state.filters.date_to);
        if (!f || !t || f.getMonth() !== 0 || f.getDate() !== 1) return "";
        return this.sameDate(this.state.filters.date_to, this.clampToLatestReportDate(new Date(f.getFullYear(), 11, 31))) ? String(f.getFullYear()) : "";
    }

    clampToLatestReportDate(date) { const l = this.latestReportDate(); return !date || date > l ? l : date; }
    clampIsoToLatestReportDate(value) { return value ? this.toIsoDate(this.clampToLatestReportDate(this.parseIsoDate(value))) : value; }
    toIsoDate(date) { return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 10); }
    sameDate(left, right) { return left === this.toIsoDate(right); }
    sameRange(df, dt, s, e) { return this.sameDate(df, s) && this.sameDate(dt, e); }
    parseIsoDate(v) { if (!v) return null; const [y, m, d] = v.split("-").map(Number); return (!y || !m || !d) ? null : new Date(y, m - 1, d); }
    storeDisplayName(id, stores) { const c = Number(id || 0); if (!c) return _t("All Stores"); const s = (stores || []).find(i => Number(i.id) === c); return s ? s.name : _t("All Stores"); }

    get filteredStores() {
        const stores = (this.state.data && this.state.data.stores) || [];
        const search = (this.state.storeSearch || "").trim().toLowerCase();
        const sel = this.storeDisplayName(this.state.filters.store_id, stores).toLowerCase();
        if (!search || search === _t("All Stores").toLowerCase() || search === sel) return stores.slice(0, 50);
        return stores.filter(s => (s.name || "").toLowerCase().includes(search)).slice(0, 50);
    }

    isDateFilterActive(k) { return this.state.activeDateFilter === k; }

    get dateFilterLabel() {
        const { date_from, date_to } = this.state.filters;
        const latest = this.latestReportDate();
        if (this.sameDate(date_to, latest)) {
            if (this.sameDate(date_from, latest)) return _t("Yesterday");
            if (this.sameDate(date_from, this.addDays(latest, -6))) return _t("Last 7 Days");
            if (this.sameDate(date_from, this.addDays(latest, -29))) return _t("Last 30 Days");
            if (this.sameDate(date_from, this.addDays(latest, -89))) return _t("Last 90 Days");
        }
        if (date_from && date_to) return `${date_from} — ${date_to}`;
        return _t("Date Filter");
    }

    get isRtl() { const h = document.documentElement; return h.dir === "rtl" || (h.lang || "").toLowerCase().startsWith("ar"); }
    get direction() { return this.isRtl ? "rtl" : "ltr"; }
    get locale() { return this.isRtl ? "ar-EG" : ((document.documentElement.lang || "").replace("_", "-") || "en-US"); }

    toggleMobileFilters() { this.state.mobileFiltersOpen = !this.state.mobileFiltersOpen; if (!this.state.mobileFiltersOpen) this.state.storeMenuOpen = false; }

    // -- Formatting --
    money(v) { return money(v); }
    number(v) { return number(v); }
    decimal(v) { return decimal(v); }
    pct(v) { return pct(v); }
    abs(v) { return Math.abs(Number(v || 0)); }
    toN(v) { return Number(v || 0); }
    collectionLabel(c) { return COLLECTION_LABELS[c] || c; }
    _t = _t;

    // -- Computed properties --
    get reportMeta() { return (this.state.data && this.state.data.report_meta) || {}; }

    get reportStatusTone() {
        const m = this.reportMeta;
        if (m.coverage_state === "unavailable") return "danger";
        if (m.coverage_state === "partial") return "warning";
        return "";
    }

    get reportStatusMessage() {
        const m = this.reportMeta;
        if (!m.mode) return "";
        if (m.coverage_state === "unavailable") return _t("Report data unavailable for this range. Run shorter E-Plus refreshes first to build daily facts.");
        if (m.coverage_state === "partial") return `${_t("Partial stored summary")}: ${this.number(m.covered_store_days)} / ${this.number(m.expected_store_days)} ${_t("branch-days synchronized")}.`;
        return "";
    }

    get cacheProgressVisible() { return Boolean(this.progressTotalDays); }
    get activeSyncProgress() { const p = this.state.syncProgress; return p && p.has_sync_state ? p : null; }
    get progressDoneDays() { const p = this.activeSyncProgress; return p ? Number(p.done_days || 0) : Number(this.reportMeta.fully_covered_days || 0); }
    get progressTotalDays() { const p = this.activeSyncProgress; return p ? Number(p.requested_days || 0) : Number(this.reportMeta.requested_days || 0); }

    get cacheProgressPct() {
        const p = this.activeSyncProgress;
        if (p) return Math.max(0, Math.min(100, Number(p.progress_pct || 0)));
        return this.progressTotalDays ? Math.max(0, Math.min(100, (100 * this.progressDoneDays) / this.progressTotalDays)) : 0;
    }

    get cacheProgressStyle() { return `width: ${this.cacheProgressPct.toFixed(2)}%;`; }
    get cacheProgressComplete() { return this.cacheProgressVisible && this.cacheProgressPct >= 100; }
    get cacheProgressLabel() {
        const label = this.activeSyncProgress ? _t("Synced days") : _t("Cached days");
        return `${label}: ${this.number(this.progressDoneDays)} / ${this.number(this.progressTotalDays)} (${this.pct(this.cacheProgressPct)})`;
    }

    get medicineTotal() { const d = this.state.data || {}; return Number(d.medicine_sales || 0) + Number(d.non_medicine_sales || 0); }
    get medicinePct() { return this.medicineTotal ? (100 * Number((this.state.data || {}).medicine_sales || 0)) / this.medicineTotal : 0; }
    get nonMedicinePct() { return this.medicineTotal ? (100 * Number((this.state.data || {}).non_medicine_sales || 0)) / this.medicineTotal : 0; }

    userRowKey(row, index) { return row.row_key || row.employee_eplus_id || index; }
    itemRowKey(row, index) { return row.row_key || row.eplus_item_id || index; }
    invoiceRowKey(row, index) { return row.row_key || row.invoice_no || index; }
}

// ============================================================================
// Template
// ============================================================================
SalesDashboardAction.template = xml`
<div class="ab_sales_dashboard"
     t-ref="dashboardRoot"
     t-att-dir="direction"
     t-att-class="{'sd-theme-dark': state.theme === 'dark', 'sd-theme-light': state.theme === 'light'}">

    <!-- Control Panel / Header -->
    <div class="o_control_panel ab_sales_dashboard__control_panel"
         t-att-class="{'ab_sales_dashboard__control_panel--mobile_open': state.mobileFiltersOpen}">
        <div class="ab_sales_dashboard__toolbar">
            <div class="o_control_panel_breadcrumbs d-flex align-items-center gap-1">
                <div class="o_control_panel_main_buttons d-flex gap-1 d-empty-none d-print-none"/>
                <div class="o_breadcrumb d-flex gap-1 text-truncate">
                    <div class="o_last_breadcrumb_item active d-flex fs-4 min-w-0 align-items-center">
                        <div class="ab_sales_dashboard__title_area">
                            <div class="ab_sales_dashboard__header_row">
                                <span class="sd-title" t-esc="_t('Sales Dashboard')"/>
                                <ThemeToggle theme="state.theme" onToggle="toggleTheme"/>
                            </div>
                            <span class="sd-subtitle" t-esc="_t('Abdin Pharmacies - performance overview')"/>
                        </div>
                    </div>
                    <div class="o_control_panel_breadcrumbs_actions d-inline-flex d-print-none"/>
                </div>
                <div class="me-auto"/>
                <button type="button"
                        class="btn ab_sales_dashboard__mobile_filter_toggle d-print-none"
                        t-on-click="toggleMobileFilters">
                    <i t-att-class="state.mobileFiltersOpen ? 'fa fa-times' : 'fa fa-bars'"/>
                </button>
            </div>
            <div class="ab_sales_dashboard__filters">
                <CoreSearchSelect className="'ab_sales_dashboard__store_search'"
                                  value="state.filters.store_id"
                                  searchValue="state.storeSearch"
                                  placeholder="_t('Filter by store')"
                                  allLabel="_t('All Stores')"
                                  emptyText="_t('No records found.')"
                                  resultsLabel="_t('records')"
                                  clearLabel="_t('All Stores')"
                                  ariaLabel="_t('Filter by store')"
                                  options="filteredStores"
                                  open="state.storeMenuOpen"
                                  disabled="state.refreshing"
                                  onInput="(v) => this.onStoreSearchInput(v)"
                                  onFocus="() => this.openStoreMenu()"
                                  onToggle="() => this.toggleStoreMenu()"
                                  onSelect="(id, name) => this.selectStore(id, name)"/>
                <div class="ab_sales_dashboard__date_inputs"
                     t-att-class="{'ab_sales_dashboard__date_inputs--active': isDateFilterActive('custom')}">
                    <CoreInput type="'date'"
                               label="_t('Date From')"
                               className="'ab_sales_dashboard__date_field'"
                               value="state.filters.date_from"
                               max="latestReportDateIso"
                               disabled="state.refreshing"
                               onChange="(v) => this.updateCustomDate('date_from', v)"/>
                    <CoreInput type="'date'"
                               label="_t('Date To')"
                               className="'ab_sales_dashboard__date_field'"
                               value="state.filters.date_to"
                               max="latestReportDateIso"
                               disabled="state.refreshing"
                               onChange="(v) => this.updateCustomDate('date_to', v)"/>
                </div>
                <div class="ab_sales_dashboard__quick_ranges" role="group" t-att-aria-label="_t('Date Filter')">
                    <CoreInput type="'date'" bare="true"
                               inputClass="'ab_sales_dashboard__period_select ab_sales_dashboard__day_select' + (isDateFilterActive('day') ? ' ab_sales_dashboard__range_active' : '')"
                               max="latestReportDateIso"
                               disabled="state.refreshing"
                               value="selectedDayValue"
                               onChange="(v) => this.applyDaySelection(v)"/>
                    <button class="btn" t-att-class="{'ab_sales_dashboard__range_active': isDateFilterActive('yesterday')}" type="button" t-att-disabled="state.refreshing" t-on-click="() => this.applyDatePreset('yesterday')" t-esc="_t('Yesterday')"/>
                    <button class="btn" t-att-class="{'ab_sales_dashboard__range_active': isDateFilterActive('last_7_days')}" type="button" t-att-disabled="state.refreshing" t-on-click="() => this.applyDatePreset('last_7_days')" t-esc="_t('7 Days')"/>
                    <button class="btn" t-att-class="{'ab_sales_dashboard__range_active': isDateFilterActive('last_30_days')}" type="button" t-att-disabled="state.refreshing" t-on-click="() => this.applyDatePreset('last_30_days')" t-esc="_t('30 Days')"/>
                    <button class="btn" t-att-class="{'ab_sales_dashboard__range_active': isDateFilterActive('last_90_days')}" type="button" t-att-disabled="state.refreshing" t-on-click="() => this.applyDatePreset('last_90_days')" t-esc="_t('90 Days')"/>
                    <CoreSelect className="'ab_sales_dashboard__period_select_field'"
                                selectClass="'ab_sales_dashboard__period_select'"
                                variant="isDateFilterActive('month') ? 'active' : ''"
                                placeholder="_t('Month')"
                                disabled="state.refreshing"
                                value="selectedMonthValue"
                                options="monthOptions"
                                onChange="(v) => this.applyMonthSelection(v)"/>
                    <CoreSelect className="'ab_sales_dashboard__period_select_field'"
                                selectClass="'ab_sales_dashboard__period_select'"
                                variant="isDateFilterActive('year') ? 'active' : ''"
                                placeholder="_t('Year')"
                                disabled="state.refreshing"
                                value="selectedYearValue"
                                options="yearOptions"
                                onChange="(v) => this.applyYearSelection(v)"/>
                </div>
                <button type="button"
                        class="btn btn-primary ab_sales_dashboard__refresh_button"
                        t-on-click="onRefresh"
                        t-att-disabled="state.refreshing">
                    <t t-if="state.refreshing"><i class="fa fa-spinner fa-spin me-1"/><t t-esc="_t('Syncing...')"/></t>
                    <t t-else=""><i class="fa fa-refresh me-1"/><t t-esc="_t('Refresh from E-Plus')"/></t>
                </button>
            </div>
        </div>
    </div>

    <!-- Dashboard Body -->
    <div class="ab_sales_dashboard__body">

        <!-- Loading State -->
        <t t-if="state.loading &amp;&amp; !state.data">
            <LoadingSkeleton/>
        </t>

        <!-- Dashboard Content -->
        <t t-elif="state.data">

            <!-- Sync Progress -->
            <div t-if="cacheProgressVisible" class="ab_sales_dashboard__cache_progress sd-animate-in">
                <div class="ab_sales_dashboard__cache_progress_header">
                    <span t-esc="cacheProgressLabel"/>
                    <span t-if="cacheProgressComplete"
                          class="ab_sales_dashboard__cache_progress_complete"
                          t-att-title="_t('Synced')"
                          t-att-aria-label="_t('Synced')">
                        100%
                    </span>
                </div>
                <div class="ab_sales_dashboard__cache_progress_track">
                    <div class="ab_sales_dashboard__cache_progress_bar" t-att-style="cacheProgressStyle"/>
                </div>
            </div>

            <!-- Status Notice -->
            <div t-if="reportStatusMessage"
                 t-att-class="'ab_sales_dashboard__notice ab_sales_dashboard__notice--' + reportStatusTone + ' sd-animate-in'">
                <t t-esc="reportStatusMessage"/>
            </div>

            <!-- KPI Cards -->
            <section class="ab_sales_dashboard__kpis">
                <KpiCard label="_t('Total Sales')"
                         value="money(state.data.total_sales)"
                         icon="'&lt;i class=&quot;fa fa-line-chart&quot;&gt;&lt;/i&gt;'"
                         variant="'amber'"
                         trend="state.data.avg_daily_growth_pct"
                         trendLabel="_t('vs previous period')"
                         formatter="(v) => pct(abs(v))"
                         delay="0"/>
                <KpiCard label="_t('Avg. Daily Sales')"
                         value="money(state.data.avg_daily_sales)"
                         icon="'&lt;i class=&quot;fa fa-calendar&quot;&gt;&lt;/i&gt;'"
                         variant="'cyan'"
                         sub="_t('Prev:') + ' ' + money(state.data.prev_avg_daily_sales)"
                         delay="60"/>
                <KpiCard label="_t('Invoices')"
                         value="number(state.data.invoice_count)"
                         icon="'&lt;i class=&quot;fa fa-file-text-o&quot;&gt;&lt;/i&gt;'"
                         sub="state.data.store_filter_label"
                         delay="120"/>
                <KpiCard label="_t('Bearing %')"
                         value="pct(state.data.bearing_pct)"
                         icon="'&lt;i class=&quot;fa fa-pie-chart&quot;&gt;&lt;/i&gt;'"
                         variant="'violet'"
                         sub="_t('Company:') + ' ' + money(state.data.company_part_amount)"
                         delay="180"/>
            </section>

            <!-- Medicine Split + Collection Methods -->
            <section class="ab_sales_dashboard__split">
                <article class="ab_sales_dashboard__panel">
                    <div class="ab_sales_dashboard__panel_header">
                        <h2 t-esc="_t('Medicine vs Non-Medicine')"/>
                        <span t-esc="decimal(medicinePct) + ' / ' + decimal(nonMedicinePct)"/>
                    </div>
                    <DonutChart valueA="toN(state.data.medicine_sales)"
                                valueB="toN(state.data.non_medicine_sales)"
                                labelA="_t('Medicine Sales')"
                                labelB="_t('Non-Medicine Sales')"
                                colorA="'#10b981'"
                                colorB="'#475569'"
                                delay="250"/>
                </article>
                <article class="ab_sales_dashboard__panel">
                    <div class="ab_sales_dashboard__panel_header">
                        <h2 t-esc="_t('Sales by Collection Method')"/>
                        <span t-esc="state.data.collection_lines.length + ' ' + _t('categories')"/>
                    </div>
                    <BarChart items="state.data.collection_lines"
                              labelFormatter="(cat) => this.collectionLabel(cat)"
                              delay="310"/>
                </article>
            </section>

            <!-- User Ranking + Top Items -->
            <section class="ab_sales_dashboard__tables">
                <article class="ab_sales_dashboard__panel">
                    <div class="ab_sales_dashboard__panel_header ab_sales_dashboard__panel_header--table">
                        <h2 t-esc="_t('Sales by Users')"/>
                        <CoreInput type="'search'"
                                   className="'ab_sales_dashboard__table_search'"
                                   icon="'oi oi-search'"
                                   placeholder="_t('Search')"
                                   value="state.sectionPages.sales_by_user.search"
                                   disabled="!state.sectionPages.sales_by_user.available"
                                   onInput="(v) => this.onSectionSearchInput('sales_by_user', v)"/>
                        <span t-esc="_t('Ranked descending')"/>
                    </div>
                    <div t-if="sectionUnsupported('sales_by_user')" class="ab_sales_dashboard__section_note ab_sales_dashboard__section_note--info">
                        <i class="fa fa-info-circle"/>
                        <span t-esc="_t('Not available for summary range.')"/>
                    </div>
                    <div t-if="state.sectionPages.sales_by_user.error" class="ab_sales_dashboard__section_note ab_sales_dashboard__section_note--warning">
                        <i class="fa fa-exclamation-triangle"/>
                        <span t-esc="_t('Could not load all records.')"/>
                    </div>
                    <div t-if="state.sectionPages.sales_by_user.limited" class="ab_sales_dashboard__section_note ab_sales_dashboard__section_note--muted">
                        <i class="fa fa-database"/>
                        <span t-esc="_t('Only stored snapshot rows are available.')"/>
                    </div>
                    <RankingTable rows="state.sectionPages.sales_by_user.rows"
                                  nameLabel="_t('User')"
                                  valueLabel="_t('Total Sales')"
                                  pctLabel="_t('Percentage')"
                                  nameField="'employee_name'"
                                  loading="state.sectionPages.sales_by_user.loading"
                                  delay="380"/>
                    <div t-if="state.sectionPages.sales_by_user.available" class="ab_sales_dashboard__pagination">
                        <button type="button" class="btn"
                                t-att-disabled="state.sectionPages.sales_by_user.loading || state.sectionPages.sales_by_user.page &lt;= 1"
                                t-on-click="() => this.changeSectionPage('sales_by_user', -1)">
                            <i t-att-class="isRtl ? 'oi oi-chevron-right' : 'oi oi-chevron-left'"/>
                        </button>
                        <span><t t-esc="_t('Page')"/> <t t-esc="state.sectionPages.sales_by_user.page"/> <t t-esc="_t('of')"/> <t t-esc="state.sectionPages.sales_by_user.totalPages"/> · <t t-esc="state.sectionPages.sales_by_user.totalCount"/> <t t-esc="_t('records')"/></span>
                        <button type="button" class="btn"
                                t-att-disabled="state.sectionPages.sales_by_user.loading || state.sectionPages.sales_by_user.page &gt;= state.sectionPages.sales_by_user.totalPages"
                                t-on-click="() => this.changeSectionPage('sales_by_user', 1)">
                            <i t-att-class="isRtl ? 'oi oi-chevron-left' : 'oi oi-chevron-right'"/>
                        </button>
                    </div>
                </article>

                <article class="ab_sales_dashboard__panel">
                    <div class="ab_sales_dashboard__panel_header ab_sales_dashboard__panel_header--table">
                        <h2 t-esc="_t('Top Sold Items')"/>
                        <CoreInput type="'search'"
                                   className="'ab_sales_dashboard__table_search'"
                                   icon="'oi oi-search'"
                                   placeholder="_t('Search')"
                                   value="state.sectionPages.top_items.search"
                                   disabled="!state.sectionPages.top_items.available"
                                   onInput="(v) => this.onSectionSearchInput('top_items', v)"/>
                        <span t-esc="_t('Sales + stock balance')"/>
                    </div>
                    <div t-if="sectionUnsupported('top_items')" class="ab_sales_dashboard__section_note ab_sales_dashboard__section_note--info">
                        <i class="fa fa-info-circle"/>
                        <span t-esc="_t('Not available for summary range.')"/>
                    </div>
                    <div t-if="state.sectionPages.top_items.error" class="ab_sales_dashboard__section_note ab_sales_dashboard__section_note--warning">
                        <i class="fa fa-exclamation-triangle"/>
                        <span t-esc="_t('Could not load all records.')"/>
                    </div>
                    <div t-if="state.sectionPages.top_items.limited" class="ab_sales_dashboard__section_note ab_sales_dashboard__section_note--muted">
                        <i class="fa fa-database"/>
                        <span t-esc="_t('Only stored snapshot rows are available.')"/>
                    </div>
                    <RankingTable rows="state.sectionPages.top_items.rows"
                                  nameLabel="_t('Item')"
                                  valueLabel="_t('Total Sales')"
                                  pctLabel="_t('Sale Times')"
                                  nameField="'product_name'"
                                  subNameField="'eplus_item_code'"
                                  loading="state.sectionPages.top_items.loading"
                                  delay="440"/>
                    <div t-if="state.sectionPages.top_items.available" class="ab_sales_dashboard__pagination">
                        <button type="button" class="btn"
                                t-att-disabled="state.sectionPages.top_items.loading || state.sectionPages.top_items.page &lt;= 1"
                                t-on-click="() => this.changeSectionPage('top_items', -1)">
                            <i t-att-class="isRtl ? 'oi oi-chevron-right' : 'oi oi-chevron-left'"/>
                        </button>
                        <span><t t-esc="_t('Page')"/> <t t-esc="state.sectionPages.top_items.page"/> <t t-esc="_t('of')"/> <t t-esc="state.sectionPages.top_items.totalPages"/> · <t t-esc="state.sectionPages.top_items.totalCount"/> <t t-esc="_t('records')"/></span>
                        <button type="button" class="btn"
                                t-att-disabled="state.sectionPages.top_items.loading || state.sectionPages.top_items.page &gt;= state.sectionPages.top_items.totalPages"
                                t-on-click="() => this.changeSectionPage('top_items', 1)">
                            <i t-att-class="isRtl ? 'oi oi-chevron-left' : 'oi oi-chevron-right'"/>
                        </button>
                    </div>
                </article>
            </section>

            <!-- Customer Sales Table -->
            <section class="ab_sales_dashboard__panel sd-animate-in sd-animate-in-7">
                <div class="ab_sales_dashboard__panel_header ab_sales_dashboard__panel_header--table">
                    <h2 t-esc="_t('Customer Sales')"/>
                    <CoreInput type="'search'"
                               className="'ab_sales_dashboard__table_search'"
                               icon="'oi oi-search'"
                               placeholder="_t('Search')"
                               value="state.sectionPages.customer_sales.search"
                               disabled="!state.sectionPages.customer_sales.available"
                               onInput="(v) => this.onSectionSearchInput('customer_sales', v)"/>
                    <span t-esc="_t('Invoice + Customer + Items')"/>
                </div>
                <div t-if="sectionUnsupported('customer_sales')" class="ab_sales_dashboard__section_note ab_sales_dashboard__section_note--info">
                    <i class="fa fa-info-circle"/>
                    <span t-esc="_t('Not available for summary range.')"/>
                </div>
                <div t-if="state.sectionPages.customer_sales.error" class="ab_sales_dashboard__section_note ab_sales_dashboard__section_note--warning">
                    <i class="fa fa-exclamation-triangle"/>
                    <span t-esc="_t('Could not load all records.')"/>
                </div>
                <div t-if="state.sectionPages.customer_sales.limited" class="ab_sales_dashboard__section_note ab_sales_dashboard__section_note--muted">
                    <i class="fa fa-database"/>
                    <span t-esc="_t('Only stored snapshot rows are available.')"/>
                </div>
                <DataTable rows="state.sectionPages.customer_sales.rows"
                           columns="invoiceColumns"
                           loading="state.sectionPages.customer_sales.loading"
                           delay="500"/>
                <div t-if="state.sectionPages.customer_sales.available" class="ab_sales_dashboard__pagination">
                    <button type="button" class="btn"
                            t-att-disabled="state.sectionPages.customer_sales.loading || state.sectionPages.customer_sales.page &lt;= 1"
                            t-on-click="() => this.changeSectionPage('customer_sales', -1)">
                        <i t-att-class="isRtl ? 'oi oi-chevron-right' : 'oi oi-chevron-left'"/>
                    </button>
                    <span><t t-esc="_t('Page')"/> <t t-esc="state.sectionPages.customer_sales.page"/> <t t-esc="_t('of')"/> <t t-esc="state.sectionPages.customer_sales.totalPages"/> · <t t-esc="state.sectionPages.customer_sales.totalCount"/> <t t-esc="_t('records')"/></span>
                    <button type="button" class="btn"
                            t-att-disabled="state.sectionPages.customer_sales.loading || state.sectionPages.customer_sales.page &gt;= state.sectionPages.customer_sales.totalPages"
                            t-on-click="() => this.changeSectionPage('customer_sales', 1)">
                        <i t-att-class="isRtl ? 'oi oi-chevron-left' : 'oi oi-chevron-right'"/>
                    </button>
                </div>
            </section>

        </t>
    </div>
</div>
`;

// Expose invoiceColumns as a getter on the class
Object.defineProperty(SalesDashboardAction.prototype, "invoiceColumns", {
    get() { return INVOICE_COLUMNS; },
});

registry.category("actions").add("ab_sales_dashboard.dashboard", SalesDashboardAction);
