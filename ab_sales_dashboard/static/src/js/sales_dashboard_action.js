/** @odoo-module **/

import { Component, onWillStart, onWillUnmount, useState, xml } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { CoreInput, CoreSearchSelect, CoreSelect } from "@ab_core_ui/core_ui/components/input/input";

const COLLECTION_LABELS = {
    cash: _t("Cash"),
    delivery: _t("Delivery"),
    contract: _t("Contracts"),
    offer: _t("Offers"),
};

const FILTER_STORAGE_KEY = "ab_sales_dashboard.filters";
const SYNC_POLL_DELAY_MS = 750;
const DATE_FILTER_KEYS = new Set([
    "day",
    "yesterday",
    "last_7_days",
    "last_30_days",
    "last_90_days",
    "month",
    "year",
    "custom",
]);

const UI_TEXT = {
    title: _t("Sales Dashboard"),
    subtitle: _t("Abdin Pharmacies - complete overview of sales performance"),
    allStores: _t("All Stores"),
    refreshing: _t("Refreshing..."),
    refreshFromEplus: _t("Refresh from E-Plus"),
    filterByStore: _t("Filter by store"),
    showFilters: _t("Show filters"),
    hideFilters: _t("Hide filters"),
    dateFilter: _t("Date Filter"),
    daily: _t("Daily"),
    yesterday: _t("Yesterday"),
    last7Days: _t("Last 7 Days"),
    last30Days: _t("Last 30 Days"),
    last90Days: _t("Last 90 Days"),
    dateFrom: _t("Date From"),
    dateTo: _t("Date To"),
    month: _t("Month"),
    year: _t("Year"),
    search: _t("Search"),
    previousPage: _t("Previous"),
    nextPage: _t("Next"),
    page: _t("Page"),
    of: _t("of"),
    records: _t("records"),
    noRecords: _t("No records found."),
    sectionLoadFailed: _t("Could not load all records for this section."),
    limitedRows: _t("Only stored snapshot rows are available for this section."),
    loading: _t("Loading dashboard..."),
    syncing: _t("Syncing..."),
    syncStarted: _t("Dashboard sync started."),
    syncFinished: _t("Dashboard sync finished."),
    syncFailed: _t("Dashboard sync finished with failed days."),
    sourceUnavailable: _t("E-Plus is unavailable. Dashboard sync is paused; try again after the connection is restored."),
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
    static components = { CoreInput, CoreSearchSelect, CoreSelect };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.ui = UI_TEXT;
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
        const savedFilters = this.loadSavedFilters();
        this.state = useState({
            loading: true,
            refreshing: false,
            syncing: false,
            storeMenuOpen: false,
            mobileFiltersOpen: false,
            storeSearch: UI_TEXT.allStores,
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

    emptySectionPage() {
        return {
            rows: [],
            page: 1,
            pageSize: 20,
            totalCount: 0,
            totalPages: 1,
            search: "",
            loading: false,
            available: false,
            limited: false,
            error: false,
        };
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
                active_date_filter: DATE_FILTER_KEYS.has(saved.active_date_filter)
                    ? saved.active_date_filter
                    : "last_7_days",
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
            this.initializeSectionPages(data);
            this.loadAvailableSectionPages();
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

    onStoreSearchInput(valueOrEvent) {
        this.state.storeSearch = this.inputValue(valueOrEvent) || "";
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
        this.state.activeDateFilter = preset;
        this.persistFilters();
        return this.loadDashboard(false);
    }

    inputValue(valueOrEvent) {
        return typeof valueOrEvent === "object" && valueOrEvent && valueOrEvent.target
            ? valueOrEvent.target.value
            : valueOrEvent;
    }

    applyMonthSelection(valueOrEvent) {
        const value = this.inputValue(valueOrEvent);
        if (!value) {
            return;
        }
        const [year, month] = value.split("-").map((part) => Number(part));
        const dateFrom = new Date(year, month - 1, 1);
        const dateTo = this.clampToLatestReportDate(new Date(year, month, 0));
        this.state.activeDateFilter = "month";
        return this.applyExplicitDateRange(dateFrom, dateTo);
    }

    applyDaySelection(valueOrEvent) {
        const value = this.clampIsoToLatestReportDate(this.inputValue(valueOrEvent));
        if (!value) {
            return;
        }
        this.state.filters.date_from = value;
        this.state.filters.date_to = value;
        this.state.activeDateFilter = "day";
        this.persistFilters();
        return this.loadDashboard(false);
    }

    applyYearSelection(valueOrEvent) {
        const year = Number(this.inputValue(valueOrEvent) || 0);
        if (!year) {
            return;
        }
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

    initializeSectionPages(data) {
        const initialRows = {
            sales_by_user: data.user_lines || [],
            top_items: data.item_lines || [],
            customer_sales: data.invoice_lines || [],
        };
        const unsupported = new Set(((data.report_meta || {}).unsupported_sections) || []);
        for (const section of Object.keys(initialRows)) {
            const sectionState = this.state.sectionPages[section];
            Object.assign(sectionState, {
                rows: initialRows[section],
                page: 1,
                pageSize: 20,
                totalCount: initialRows[section].length,
                totalPages: 1,
                search: "",
                loading: false,
                available: Boolean(data.has_snapshot) && !unsupported.has(section),
                limited: false,
                error: false,
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
        const sectionState = this.state.sectionPages[section];
        if (!sectionState || !sectionState.available || this.unmounted) {
            return;
        }
        const requestVersion = (this.sectionRequestVersions[section] || 0) + 1;
        this.sectionRequestVersions[section] = requestVersion;
        sectionState.loading = true;
        sectionState.error = false;
        const filters = { ...this.state.filters };
        try {
            const result = await this.orm.call(
                "ab.sales.dashboard.snapshot",
                "get_dashboard_section_page",
                [filters, section, page, sectionState.search]
            );
            if (this.unmounted || this.sectionRequestVersions[section] !== requestVersion) {
                return;
            }
            let rows = result.rows || [];
            if (section === "top_items") {
                const balances = new Map(
                    ((this.state.data && this.state.data.item_lines) || []).map((row) => [
                        Number(row.eplus_item_id || 0),
                        row.current_balance,
                    ])
                );
                rows = rows.map((row) => balances.has(Number(row.eplus_item_id || 0))
                    ? { ...row, current_balance: balances.get(Number(row.eplus_item_id || 0)) }
                    : row);
            }
            Object.assign(sectionState, {
                rows,
                page: Number(result.page || 1),
                pageSize: Number(result.page_size || 20),
                totalCount: Number(result.total_count || 0),
                totalPages: Math.max(Number(result.total_pages || 1), 1),
                available: result.available !== false,
                limited: Boolean(result.limited),
                error: false,
            });
        } catch {
            if (this.sectionRequestVersions[section] === requestVersion) {
                sectionState.error = true;
            }
        } finally {
            if (this.sectionRequestVersions[section] === requestVersion) {
                sectionState.loading = false;
            }
        }
    }

    onSectionSearchInput(section, valueOrEvent) {
        const sectionState = this.state.sectionPages[section];
        sectionState.search = (this.inputValue(valueOrEvent) || "").slice(0, 100);
        clearTimeout(this.sectionSearchTimers[section]);
        this.sectionSearchTimers[section] = setTimeout(() => {
            this.loadSectionPage(section, 1);
        }, 300);
    }

    changeSectionPage(section, direction) {
        const sectionState = this.state.sectionPages[section];
        const nextPage = Math.min(Math.max(sectionState.page + direction, 1), sectionState.totalPages);
        if (!sectionState.loading && nextPage !== sectionState.page) {
            this.loadSectionPage(section, nextPage);
        }
    }

    sectionRowNumber(section, index) {
        const sectionState = this.state.sectionPages[section];
        return ((sectionState.page - 1) * sectionState.pageSize) + index + 1;
    }

    isDateFilterActive(filterKey) {
        return this.state.activeDateFilter === filterKey;
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
            if (progress.last_status === "source_unavailable") {
                this.notification.add(this.ui.sourceUnavailable, { type: "warning" });
            } else if (progress.failed_days) {
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

    toggleMobileFilters() {
        this.state.mobileFiltersOpen = !this.state.mobileFiltersOpen;
        if (!this.state.mobileFiltersOpen) {
            this.state.storeMenuOpen = false;
        }
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

    get monthOptions() {
        const latest = this.latestReportDate();
        const formatter = new Intl.DateTimeFormat(this.locale, { month: "long", year: "numeric" });
        const options = [];
        for (let offset = 0; offset < 36; offset++) {
            const month = new Date(latest.getFullYear(), latest.getMonth() - offset, 1);
            options.push({
                value: `${month.getFullYear()}-${String(month.getMonth() + 1).padStart(2, "0")}`,
                label: formatter.format(month),
            });
        }
        return options;
    }

    get yearOptions() {
        const latestYear = this.latestReportDate().getFullYear();
        return Array.from({ length: 10 }, (_value, index) => `${latestYear - index}`);
    }

    get selectedMonthValue() {
        const dateFrom = this.parseIsoDate(this.state.filters.date_from);
        const dateTo = this.parseIsoDate(this.state.filters.date_to);
        if (!dateFrom || !dateTo || dateFrom.getDate() !== 1) {
            return "";
        }
        const expectedEnd = this.clampToLatestReportDate(
            new Date(dateFrom.getFullYear(), dateFrom.getMonth() + 1, 0)
        );
        if (!this.sameDate(this.state.filters.date_to, expectedEnd)) {
            return "";
        }
        return `${dateFrom.getFullYear()}-${String(dateFrom.getMonth() + 1).padStart(2, "0")}`;
    }

    get selectedDayValue() {
        return this.state.filters.date_from === this.state.filters.date_to
            ? this.state.filters.date_from
            : "";
    }

    get selectedYearValue() {
        const dateFrom = this.parseIsoDate(this.state.filters.date_from);
        const dateTo = this.parseIsoDate(this.state.filters.date_to);
        if (!dateFrom || !dateTo || dateFrom.getMonth() !== 0 || dateFrom.getDate() !== 1) {
            return "";
        }
        const expectedEnd = this.clampToLatestReportDate(new Date(dateFrom.getFullYear(), 11, 31));
        return this.sameDate(this.state.filters.date_to, expectedEnd) ? String(dateFrom.getFullYear()) : "";
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
        const selectedStoreLabel = this.storeDisplayName(this.state.filters.store_id, stores).toLowerCase();
        if (!search || search === this.ui.allStores.toLowerCase() || search === selectedStoreLabel) {
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
    <div class="o_control_panel ab_sales_dashboard__control_panel"
         t-att-class="{'ab_sales_dashboard__control_panel--mobile_open': state.mobileFiltersOpen}">
        <div class="o_control_panel_main ab_sales_dashboard__toolbar">
            <div class="o_control_panel_breadcrumbs d-flex align-items-center gap-1">
                <div class="o_control_panel_main_buttons d-flex gap-1 d-empty-none d-print-none"/>
                <div class="o_breadcrumb d-flex gap-1 text-truncate">
                    <div class="o_last_breadcrumb_item active d-flex fs-4 min-w-0 align-items-center">
                        <span class="min-w-0 text-truncate" t-esc="ui.title"/>
                    </div>
                    <div class="o_control_panel_breadcrumbs_actions d-inline-flex d-print-none"/>
                </div>
                <div class="me-auto"/>
                <button type="button"
                        class="btn btn-outline-secondary ab_sales_dashboard__mobile_filter_toggle d-print-none"
                        aria-controls="ab_sales_dashboard_filters"
                        t-att-aria-expanded="state.mobileFiltersOpen"
                        t-att-aria-label="state.mobileFiltersOpen ? ui.hideFilters : ui.showFilters"
                        t-att-title="state.mobileFiltersOpen ? ui.hideFilters : ui.showFilters"
                        t-on-click="toggleMobileFilters">
                    <i t-att-class="state.mobileFiltersOpen ? 'fa fa-times' : 'fa fa-bars'" aria-hidden="true"/>
                </button>
            </div>
            <div id="ab_sales_dashboard_filters" class="o_control_panel_actions o_sp_dashboard_search ab_sales_dashboard__filters">
                <CoreSearchSelect className="'ab_sales_dashboard__store_search'"
                                  value="state.filters.store_id"
                                  searchValue="state.storeSearch"
                                  placeholder="ui.filterByStore"
                                  allLabel="ui.allStores"
                                  emptyText="ui.noRecords"
                                  resultsLabel="ui.records"
                                  clearLabel="ui.allStores"
                                  ariaLabel="ui.filterByStore"
                                  options="filteredStores"
                                  open="state.storeMenuOpen"
                                  disabled="state.refreshing"
                                  onInput="(value) => this.onStoreSearchInput(value)"
                                  onFocus="() => this.openStoreMenu()"
                                  onToggle="() => this.toggleStoreMenu()"
                                  onSelect="(storeId, storeName) => this.selectStore(storeId, storeName)"/>
                <div class="ab_sales_dashboard__date_inputs"
                     t-att-class="{'ab_sales_dashboard__date_inputs--active': isDateFilterActive('custom')}">
                    <CoreInput type="'date'"
                               label="ui.dateFrom"
                               className="'ab_sales_dashboard__date_field'"
                               value="state.filters.date_from"
                               max="latestReportDateIso"
                               disabled="state.refreshing"
                               onChange="(value) => this.updateCustomDate('date_from', value)"/>
                    <CoreInput type="'date'"
                               label="ui.dateTo"
                               className="'ab_sales_dashboard__date_field'"
                               value="state.filters.date_to"
                               max="latestReportDateIso"
                               disabled="state.refreshing"
                               onChange="(value) => this.updateCustomDate('date_to', value)"/>
                </div>
                <div class="ab_sales_dashboard__quick_ranges" role="group" t-att-aria-label="ui.dateFilter">
                    <CoreInput type="'date'"
                               bare="true"
                               inputClass="'ab_sales_dashboard__period_select ab_sales_dashboard__day_select' + (isDateFilterActive('day') ? ' ab_sales_dashboard__range_active' : '')"
                               ariaLabel="ui.daily"
                               title="ui.daily"
                               max="latestReportDateIso"
                               disabled="state.refreshing"
                               value="selectedDayValue"
                               onChange="(value) => this.applyDaySelection(value)"/>
                    <button class="btn btn-outline-secondary" t-att-class="{'ab_sales_dashboard__range_active': isDateFilterActive('yesterday')}" type="button" t-att-disabled="state.refreshing" t-on-click="() => this.applyDatePreset('yesterday')" t-esc="ui.yesterday"/>
                    <button class="btn btn-outline-secondary" t-att-class="{'ab_sales_dashboard__range_active': isDateFilterActive('last_7_days')}" type="button" t-att-disabled="state.refreshing" t-on-click="() => this.applyDatePreset('last_7_days')" t-esc="ui.last7Days"/>
                    <button class="btn btn-outline-secondary" t-att-class="{'ab_sales_dashboard__range_active': isDateFilterActive('last_30_days')}" type="button" t-att-disabled="state.refreshing" t-on-click="() => this.applyDatePreset('last_30_days')" t-esc="ui.last30Days"/>
                    <button class="btn btn-outline-secondary" t-att-class="{'ab_sales_dashboard__range_active': isDateFilterActive('last_90_days')}" type="button" t-att-disabled="state.refreshing" t-on-click="() => this.applyDatePreset('last_90_days')" t-esc="ui.last90Days"/>
                    <CoreSelect className="'ab_sales_dashboard__period_select_field'"
                                selectClass="'ab_sales_dashboard__period_select'"
                                variant="isDateFilterActive('month') ? 'active' : ''"
                                ariaLabel="ui.month"
                                placeholder="ui.month"
                                disabled="state.refreshing"
                                value="selectedMonthValue"
                                options="monthOptions"
                                onChange="(value) => this.applyMonthSelection(value)"/>
                    <CoreSelect className="'ab_sales_dashboard__period_select_field'"
                                selectClass="'ab_sales_dashboard__period_select'"
                                variant="isDateFilterActive('year') ? 'active' : ''"
                                ariaLabel="ui.year"
                                placeholder="ui.year"
                                disabled="state.refreshing"
                                value="selectedYearValue"
                                options="yearOptions"
                                onChange="(value) => this.applyYearSelection(value)"/>
                </div>
                <button type="button"
                        class="btn btn-primary ab_sales_dashboard__refresh_button"
                        t-on-click="onRefresh"
                        t-att-disabled="state.refreshing"
                        t-att-title="ui.refreshFromEplus">
                    <t t-if="state.refreshing" t-esc="ui.syncing"/>
                    <t t-else="" t-esc="ui.refreshFromEplus"/>
                </button>
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
                <div class="ab_sales_dashboard__panel_header ab_sales_dashboard__panel_header--table">
                    <h2 t-esc="ui.salesByUsers"/>
                    <CoreInput type="'search'"
                               className="'ab_sales_dashboard__table_search'"
                               icon="'oi oi-search'"
                               placeholder="ui.search"
                               ariaLabel="ui.search"
                               value="state.sectionPages.sales_by_user.search"
                               disabled="!state.sectionPages.sales_by_user.available"
                               onInput="(value) => this.onSectionSearchInput('sales_by_user', value)"/>
                    <span t-esc="ui.rankedDescending"/>
                </div>
                <div t-if="sectionUnsupported('sales_by_user')" class="ab_sales_dashboard__section_note" t-esc="ui.notAvailableForSummary"/>
                <div t-if="state.sectionPages.sales_by_user.error" class="ab_sales_dashboard__section_note" t-esc="ui.sectionLoadFailed"/>
                <div t-if="state.sectionPages.sales_by_user.limited" class="ab_sales_dashboard__section_note" t-esc="ui.limitedRows"/>
                <table t-att-aria-busy="state.sectionPages.sales_by_user.loading">
                    <thead>
                        <tr><th>#</th><th t-esc="ui.user"/><th t-esc="ui.totalSales"/><th t-esc="ui.percentage"/></tr>
                    </thead>
                    <tbody>
                        <t t-foreach="state.sectionPages.sales_by_user.rows" t-as="line" t-key="line.row_key || line.employee_eplus_id || line.employee_name || line_index">
                            <tr>
                                <td t-esc="sectionRowNumber('sales_by_user', line_index)"/>
                                <td t-esc="line.employee_name"/>
                                <td t-esc="money(line.total_sales)"/>
                                <td t-esc="pct(line.pct_of_total)"/>
                            </tr>
                        </t>
                        <tr t-if="!state.sectionPages.sales_by_user.rows.length">
                            <td colspan="4" class="text-center" t-esc="ui.noRecords"/>
                        </tr>
                    </tbody>
                </table>
                <div t-if="state.sectionPages.sales_by_user.available" class="ab_sales_dashboard__pagination">
                    <button type="button" class="btn btn-outline-secondary" t-att-title="ui.previousPage" t-att-aria-label="ui.previousPage" t-att-disabled="state.sectionPages.sales_by_user.loading || state.sectionPages.sales_by_user.page &lt;= 1" t-on-click="() => this.changeSectionPage('sales_by_user', -1)">
                        <i t-att-class="isRtl ? 'oi oi-chevron-right' : 'oi oi-chevron-left'"/>
                    </button>
                    <span><t t-esc="ui.page"/> <t t-esc="state.sectionPages.sales_by_user.page"/> <t t-esc="ui.of"/> <t t-esc="state.sectionPages.sales_by_user.totalPages"/> · <t t-esc="state.sectionPages.sales_by_user.totalCount"/> <t t-esc="ui.records"/></span>
                    <button type="button" class="btn btn-outline-secondary" t-att-title="ui.nextPage" t-att-aria-label="ui.nextPage" t-att-disabled="state.sectionPages.sales_by_user.loading || state.sectionPages.sales_by_user.page &gt;= state.sectionPages.sales_by_user.totalPages" t-on-click="() => this.changeSectionPage('sales_by_user', 1)">
                        <i t-att-class="isRtl ? 'oi oi-chevron-left' : 'oi oi-chevron-right'"/>
                    </button>
                </div>
            </article>

            <article class="ab_sales_dashboard__panel">
                <div class="ab_sales_dashboard__panel_header ab_sales_dashboard__panel_header--table">
                    <h2 t-esc="ui.topSoldItems"/>
                    <CoreInput type="'search'"
                               className="'ab_sales_dashboard__table_search'"
                               icon="'oi oi-search'"
                               placeholder="ui.search"
                               ariaLabel="ui.search"
                               value="state.sectionPages.top_items.search"
                               disabled="!state.sectionPages.top_items.available"
                               onInput="(value) => this.onSectionSearchInput('top_items', value)"/>
                    <span t-esc="ui.saleTimesCurrentBalance"/>
                </div>
                <div t-if="sectionUnsupported('top_items')" class="ab_sales_dashboard__section_note" t-esc="ui.notAvailableForSummary"/>
                <div t-if="state.sectionPages.top_items.error" class="ab_sales_dashboard__section_note" t-esc="ui.sectionLoadFailed"/>
                <div t-if="state.sectionPages.top_items.limited" class="ab_sales_dashboard__section_note" t-esc="ui.limitedRows"/>
                <table t-att-aria-busy="state.sectionPages.top_items.loading">
                    <thead>
                        <tr><th>#</th><th t-esc="ui.item"/><th t-esc="ui.totalSales"/><th t-esc="ui.saleTimes"/><th t-esc="ui.currentBalance"/></tr>
                    </thead>
                    <tbody>
                        <t t-foreach="state.sectionPages.top_items.rows" t-as="line" t-key="line.row_key || line.eplus_item_id || line.eplus_item_code || line_index">
                            <tr>
                                <td t-esc="sectionRowNumber('top_items', line_index)"/>
                                <td>
                                    <strong t-esc="line.product_name"/>
                                    <small t-esc="line.eplus_item_code"/>
                                </td>
                                <td t-esc="money(line.total_sales)"/>
                                <td t-esc="number(line.sale_times)"/>
                                <td>
                                    <t t-if="line.current_balance === false || line.current_balance === null">-</t>
                                    <t t-else=""><t t-esc="decimal(line.current_balance)"/> <t t-esc="ui.unit"/></t>
                                </td>
                            </tr>
                        </t>
                        <tr t-if="!state.sectionPages.top_items.rows.length">
                            <td colspan="5" class="text-center" t-esc="ui.noRecords"/>
                        </tr>
                    </tbody>
                </table>
                <div t-if="state.sectionPages.top_items.available" class="ab_sales_dashboard__pagination">
                    <button type="button" class="btn btn-outline-secondary" t-att-title="ui.previousPage" t-att-aria-label="ui.previousPage" t-att-disabled="state.sectionPages.top_items.loading || state.sectionPages.top_items.page &lt;= 1" t-on-click="() => this.changeSectionPage('top_items', -1)">
                        <i t-att-class="isRtl ? 'oi oi-chevron-right' : 'oi oi-chevron-left'"/>
                    </button>
                    <span><t t-esc="ui.page"/> <t t-esc="state.sectionPages.top_items.page"/> <t t-esc="ui.of"/> <t t-esc="state.sectionPages.top_items.totalPages"/> · <t t-esc="state.sectionPages.top_items.totalCount"/> <t t-esc="ui.records"/></span>
                    <button type="button" class="btn btn-outline-secondary" t-att-title="ui.nextPage" t-att-aria-label="ui.nextPage" t-att-disabled="state.sectionPages.top_items.loading || state.sectionPages.top_items.page &gt;= state.sectionPages.top_items.totalPages" t-on-click="() => this.changeSectionPage('top_items', 1)">
                        <i t-att-class="isRtl ? 'oi oi-chevron-left' : 'oi oi-chevron-right'"/>
                    </button>
                </div>
            </article>
        </section>

        <section class="ab_sales_dashboard__panel">
            <div class="ab_sales_dashboard__panel_header ab_sales_dashboard__panel_header--table">
                <h2 t-esc="ui.customerSales"/>
                <CoreInput type="'search'"
                           className="'ab_sales_dashboard__table_search'"
                           icon="'oi oi-search'"
                           placeholder="ui.search"
                           ariaLabel="ui.search"
                           value="state.sectionPages.customer_sales.search"
                           disabled="!state.sectionPages.customer_sales.available"
                           onInput="(value) => this.onSectionSearchInput('customer_sales', value)"/>
                <span t-esc="ui.invoiceCustomerItems"/>
            </div>
            <div t-if="sectionUnsupported('customer_sales')" class="ab_sales_dashboard__section_note" t-esc="ui.notAvailableForSummary"/>
            <div t-if="state.sectionPages.customer_sales.error" class="ab_sales_dashboard__section_note" t-esc="ui.sectionLoadFailed"/>
            <div t-if="state.sectionPages.customer_sales.limited" class="ab_sales_dashboard__section_note" t-esc="ui.limitedRows"/>
            <table t-att-aria-busy="state.sectionPages.customer_sales.loading">
                <thead>
                    <tr><th t-esc="ui.invoice"/><th t-esc="ui.customer"/><th t-esc="ui.items"/><th t-esc="ui.invoiceTotal"/></tr>
                </thead>
                <tbody>
                    <t t-foreach="state.sectionPages.customer_sales.rows" t-as="line" t-key="line.row_key || line.invoice_no || line_index">
                        <tr>
                            <td t-esc="line.invoice_no"/>
                            <td t-esc="line.customer_name"/>
                            <td t-esc="line.items_summary"/>
                            <td t-esc="money(line.invoice_total)"/>
                        </tr>
                    </t>
                    <tr t-if="!state.sectionPages.customer_sales.rows.length">
                        <td colspan="4" class="text-center" t-esc="ui.noRecords"/>
                    </tr>
                </tbody>
            </table>
            <div t-if="state.sectionPages.customer_sales.available" class="ab_sales_dashboard__pagination">
                <button type="button" class="btn btn-outline-secondary" t-att-title="ui.previousPage" t-att-aria-label="ui.previousPage" t-att-disabled="state.sectionPages.customer_sales.loading || state.sectionPages.customer_sales.page &lt;= 1" t-on-click="() => this.changeSectionPage('customer_sales', -1)">
                    <i t-att-class="isRtl ? 'oi oi-chevron-right' : 'oi oi-chevron-left'"/>
                </button>
                <span><t t-esc="ui.page"/> <t t-esc="state.sectionPages.customer_sales.page"/> <t t-esc="ui.of"/> <t t-esc="state.sectionPages.customer_sales.totalPages"/> · <t t-esc="state.sectionPages.customer_sales.totalCount"/> <t t-esc="ui.records"/></span>
                <button type="button" class="btn btn-outline-secondary" t-att-title="ui.nextPage" t-att-aria-label="ui.nextPage" t-att-disabled="state.sectionPages.customer_sales.loading || state.sectionPages.customer_sales.page &gt;= state.sectionPages.customer_sales.totalPages" t-on-click="() => this.changeSectionPage('customer_sales', 1)">
                    <i t-att-class="isRtl ? 'oi oi-chevron-left' : 'oi oi-chevron-right'"/>
                </button>
            </div>
        </section>
        </t>
    </div>
</div>
`;

registry.category("actions").add("ab_sales_dashboard.dashboard", SalesDashboardAction);
