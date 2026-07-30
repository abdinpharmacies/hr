/** @odoo-module **/

import { ListController } from "@web/views/list/list_controller";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { onMounted, onWillUnmount } from "@odoo/owl";

const THEME_KEY = "ab_sales_dashboard.theme";

const SNAPSHOT_MODEL = "ab.sales.dashboard.snapshot";
const TELEMETRY_MODEL = "ab.sales.dashboard.report.telemetry";
const PRODUCT_SALES_MODEL = "ab.sales.dashboard.product.sales.report";

// ─── Shared utilities ──────────────────────────────────────

function fmt(v) {
    if (!v && v !== 0) return "0";
    return new Intl.NumberFormat("en-US").format(v);
}

function fmtMoney(v) {
    if (!v && v !== 0) return "$0";
    return "$" + fmt(v);
}

function relativeTime(dateStr) {
    if (!dateStr) return { label: _t("Unknown"), cls: "rl-status--muted", freshness: "old" };
    const d = new Date(dateStr);
    const now = new Date();
    const diffMs = now - d;
    const diffH = diffMs / 3600000;
    if (diffH < 1) return { label: _t("Just now"), cls: "rl-status--fresh", freshness: "fresh" };
    if (diffH < 24) return { label: Math.floor(diffH) + " " + _t("hours ago"), cls: "rl-status--fresh", freshness: "fresh" };
    const diffD = diffH / 24;
    if (diffD < 1) return { label: _t("Today"), cls: "rl-status--today", freshness: "today" };
    if (diffD < 2) return { label: _t("Yesterday"), cls: "rl-status--ok", freshness: "recent" };
    if (diffD < 7) return { label: Math.floor(diffD) + " " + _t("days ago"), cls: "rl-status--ok", freshness: "recent" };
    if (diffD < 30) return { label: Math.floor(diffD) + " " + _t("days ago"), cls: "rl-status--stale", freshness: "stale" };
    return { label: Math.floor(diffD) + " " + _t("days old"), cls: "rl-status--muted", freshness: "old" };
}

// ─── Snapshot — Hero HTML builders ─────────────────────────

function buildSnapshotHeroHTML(summary) {
    const kpis = [
        { icon: "fa-file-text-o", label: _t("Total Reports"), value: fmt(summary.total_reports), accent: "rl-accent--cyan" },
        { icon: "fa-clock-o", label: _t("Latest"), value: summary.latest_date ? summary.latest_date.split(" ")[1] || summary.latest_date : _t("N/A"), accent: "rl-accent--emerald", sm: true },
        { icon: "fa-usd", label: _t("Total Sales"), value: fmtMoney(summary.total_sales), accent: "rl-accent--emerald" },
        { icon: "fa-receipt", label: _t("Invoices"), value: fmt(summary.total_invoices), accent: "rl-accent--blue" },
        { icon: "fa-building-o", label: _t("Branches"), value: fmt(summary.unique_stores), accent: "rl-accent--violet" },
        { icon: "fa-line-chart", label: _t("Avg Daily"), value: fmtMoney(summary.avg_daily_sales), accent: "rl-accent--amber" },
    ];

    return `
        <div class="rl-hero">
            <div class="rl-hero__content">
                <div class="rl-hero__text">
                    <h1 class="rl-hero__title">
                        <span class="rl-hero__icon"><i class="fa fa-line-chart"/></span>
                        ${_t("Sales Reports Library")}
                    </h1>
                    <p class="rl-hero__subtitle">${_t("Sales reports archive")}</p>
                    <p class="rl-hero__desc">${_t("Browse, compare, and manage historical sales report snapshots.")}</p>
                </div>
            </div>
            <div class="rl-kpi-row">${kpis.map(k => `
                <div class="rl-kpi ${k.accent}">
                    <div class="rl-kpi__icon"><i class="fa ${k.icon}"/></div>
                    <div class="rl-kpi__body">
                        <div class="rl-kpi__label">${k.label}</div>
                        <div class="rl-kpi__value${k.sm ? ' rl-kpi__value--sm' : ''}">${k.value}</div>
                    </div>
                </div>
            `).join("")}</div>
        </div>
    `;
}

function buildTelemetryHeroHTML(summary) {
    return `
        <div class="ac-hero">
            <div class="ac-hero__content">
                <div class="ac-hero__text">
                    <h1 class="ac-hero__title">
                        <span class="ac-hero__icon"><i class="fa fa-bolt"/></span>
                        ${_t("Report Activity")}
                    </h1>
                    <p class="ac-hero__subtitle">${_t("Activity Center")}</p>
                    <p class="ac-hero__desc">${_t("Audit history of dashboard executions and analytics jobs.")}</p>
                </div>
            </div>
            <div class="ac-kpi-row">
                <div class="ac-kpi ac-accent--violet">
                    <div class="ac-kpi__icon"><i class="fa fa-bolt"/></div>
                    <div class="ac-kpi__body">
                        <div class="ac-kpi__label">${_t("Total Events")}</div>
                        <div class="ac-kpi__value">${fmt(summary.total_events || 0)}</div>
                    </div>
                </div>
                <div class="ac-kpi ac-accent--cyan">
                    <div class="ac-kpi__icon"><i class="fa fa-clock-o"/></div>
                    <div class="ac-kpi__body">
                        <div class="ac-kpi__label">${_t("Today")}</div>
                        <div class="ac-kpi__value ac-kpi__value--sm">${fmt(summary.today_events || 0)}</div>
                    </div>
                </div>
                <div class="ac-kpi ac-accent--emerald">
                    <div class="ac-kpi__icon"><i class="fa fa-check-circle"/></div>
                    <div class="ac-kpi__body">
                        <div class="ac-kpi__label">${_t("Complete")}</div>
                        <div class="ac-kpi__value">${fmt(summary.complete_count || 0)}</div>
                    </div>
                </div>
                <div class="ac-kpi ac-accent--amber">
                    <div class="ac-kpi__icon"><i class="fa fa-exclamation-triangle"/></div>
                    <div class="ac-kpi__body">
                        <div class="ac-kpi__label">${_t("Issues")}</div>
                        <div class="ac-kpi__value">${fmt(summary.issue_count || 0)}</div>
                    </div>
                </div>
                <div class="ac-kpi ac-accent--rose">
                    <div class="ac-kpi__icon"><i class="fa fa-tachometer"/></div>
                    <div class="ac-kpi__body">
                        <div class="ac-kpi__label">${_t("Avg Duration")}</div>
                        <div class="ac-kpi__value ac-kpi__value--sm">${summary.avg_duration ? fmt(summary.avg_duration) + " ms" : "—"}</div>
                    </div>
                </div>
            </div>
        </div>
    `;
}

// ══════════════════════════════════════════════════════════════
// LIST CONTROLLER PATCH
// ══════════════════════════════════════════════════════════════

patch(ListController.prototype, {
    setup() {
        super.setup(...arguments);
        if (this.props.resModel === SNAPSHOT_MODEL) {
            this._rlObserver = null;
            onMounted(() => this._initReportLibrary());
            onWillUnmount(() => {
                if (this._rlObserver) this._rlObserver.disconnect();
            });
        }
        if (this.props.resModel === TELEMETRY_MODEL) {
            onMounted(() => this._initActivityCenter());
        }
        if (this.props.resModel === PRODUCT_SALES_MODEL) {
            onMounted(() => this._initProductSalesReport());
        }
    },

    // ─── Shared ────────────────────────────────────────────

    _applyTheme(extraClass) {
        const theme = localStorage.getItem(THEME_KEY) || "dark";
        const action = this.el?.closest(".o_action");
        if (!action) return;
        action.classList.remove("sd-theme-dark", "sd-theme-light", "ab_rl_action", "ab_activity_center", "ab_product_sales_action");
        action.classList.add(theme === "light" ? "sd-theme-light" : "sd-theme-dark");
        if (extraClass) action.classList.add(extraClass);
    },

    // ─── Snapshots (Reports Library) ───────────────────────

    _initReportLibrary() {
        this._applyTheme("ab_rl_action");
        this._wrapTable("rl-table-wrap");
        this._injectSnapshotHero();
        this._decorateSnapshotRows();
        this._observeSnapshotChanges();
    },

    _wrapTable(wrapClass) {
        const content = this.el?.closest(".o_action")?.querySelector(".o_content");
        if (content && !content.classList.contains(wrapClass)) {
            content.classList.add(wrapClass);
        }
    },

    async _injectSnapshotHero() {
        const content = this.el?.closest(".o_action")?.querySelector(".o_content");
        if (!content || content.querySelector(".rl-hero")) return;

        let summary;
        try {
            summary = await this.model.orm.call(SNAPSHOT_MODEL, "get_library_summary", []);
        } catch {
            summary = {
                total_reports: 0, latest_date: false,
                total_sales: 0, total_invoices: 0,
                unique_stores: 0, avg_daily_sales: 0,
            };
        }

        const tmp = document.createElement("div");
        tmp.innerHTML = buildSnapshotHeroHTML(summary);
        content.prepend(tmp.firstElementChild);
    },

    _decorateSnapshotRows() {
        const action = this.el?.closest(".o_action");
        if (!action) return;
        const tbody = action.querySelector(".o_list_table > tbody");
        if (!tbody) return;
        const rows = Array.from(tbody.querySelectorAll("tr.o_data_row"));
        if (!rows.length) return;

        const salesValues = rows.map(r => {
            const cell = r.querySelector('td[data-field="total_sales"]');
            return cell ? parseFloat(cell.textContent.replace(/[^0-9.\-]/g, "")) || 0 : 0;
        });
        const sorted = [...salesValues].map((v, i) => ({ v, i })).sort((a, b) => b.v - a.v);
        const rankMap = {};
        sorted.forEach((item, idx) => { rankMap[item.i] = idx + 1; });

        rows.forEach((row, idx) => {
            if (row.dataset.rlDecorated) return;
            row.dataset.rlDecorated = "1";

            const rank = rankMap[idx] || 0;

            const refreshCell = row.querySelector('td[data-field="refresh_date"]');
            if (refreshCell) {
                const rawDate = refreshCell.getAttribute("title") || refreshCell.textContent.trim();
                const rt = relativeTime(rawDate);
                row.classList.add("rl-freshness--" + rt.freshness);
                const chip = document.createElement("span");
                chip.className = "rl-status " + rt.cls;
                chip.textContent = rt.label;
                refreshCell.appendChild(chip);
            }

            const nameCell = row.querySelector('td[data-field="name"]');
            if (nameCell && rank >= 1 && rank <= 5) {
                const badge = document.createElement("span");
                badge.className = "rl-rank rl-rank--" + rank;
                badge.textContent = rank;
                badge.title = ["", _t("Top"), _t("2nd"), _t("3rd"), _t("4th"), _t("5th")][rank] + " " + _t("Report");
                nameCell.prepend(badge);
            }

            const archiveCell = row.querySelector('td[data-field="archive_count"]');
            if (archiveCell && nameCell) {
                const archiveVal = parseInt(archiveCell.textContent.replace(/[^0-9]/g, ""), 10);
                if (archiveVal > 0 && !nameCell.querySelector(".rl-archived-dot")) {
                    const dot = document.createElement("span");
                    dot.className = "rl-archived-dot";
                    dot.title = archiveVal + " " + _t("archived report(s)");
                    nameCell.appendChild(dot);
                }
            }
        });
    },

    _observeSnapshotChanges() {
        const action = this.el?.closest(".o_action");
        if (!action) return;
        const tbody = action.querySelector(".o_list_table > tbody");
        if (!tbody) return;

        this._rlObserver = new MutationObserver(() => {
            const allRows = tbody.querySelectorAll("tr.o_data_row");
            allRows.forEach(r => { delete r.dataset.rlDecorated; });
            this._decorateSnapshotRows();
        });
        this._rlObserver.observe(tbody, { childList: true, subtree: false });
    },

    // ─── Telemetry (Activity Center) ───────────────────────

    _initActivityCenter() {
        this._applyTheme("ab_activity_center");
        this._wrapTable("ac-table-wrap");
        this._injectTelemetryHero();
    },

    // ─── Product Sales Report ─────────────────────────────

    _initProductSalesReport() {
        this._applyTheme("ab_product_sales_action");
        this._wrapTable("psr-table-wrap");
    },

    async _injectTelemetryHero() {
        const content = this.el?.closest(".o_action")?.querySelector(".o_content");
        if (!content || content.querySelector(".ac-hero")) return;

        let summary;
        try {
            const data = await this.model.orm.call(TELEMETRY_MODEL, "search_read", [[], [
                "coverage_state", "duration_ms", "event_date",
            ]]);
            const total = data.length;
            const today = new Date().toISOString().slice(0, 10);
            const todayEvents = data.filter(r =>
                r.event_date && String(r.event_date).slice(0, 10) === today
            ).length;
            const complete = data.filter(r => r.coverage_state === "complete").length;
            const issues = data.filter(r =>
                r.coverage_state === "partial" || r.coverage_state === "unavailable"
            ).length;
            const durations = data.map(r => r.duration_ms || 0).filter(Boolean);
            const avgDuration = durations.length
                ? Math.round(durations.reduce((a, b) => a + b, 0) / durations.length)
                : 0;
            summary = {
                total_events: total,
                today_events: todayEvents,
                complete_count: complete,
                issue_count: issues,
                avg_duration: avgDuration,
            };
        } catch {
            summary = { total_events: 0, today_events: 0, complete_count: 0, issue_count: 0, avg_duration: 0 };
        }

        const tmp = document.createElement("div");
        tmp.innerHTML = buildTelemetryHeroHTML(summary);
        content.prepend(tmp.firstElementChild);
    },

    // ─── Open Record ───────────────────────────────────────

    async openRecord(record, options) {
        if (this.props.resModel === SNAPSHOT_MODEL) {
            const action = await this.model.orm.call(
                SNAPSHOT_MODEL,
                "action_open_report",
                [record.resId],
            );
            if (action) {
                await this.actionService.doAction(action);
            }
            return;
        }
        return super.openRecord(record, options);
    },
});
