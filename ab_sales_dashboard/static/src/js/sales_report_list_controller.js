/** @odoo-module **/

import { ListController } from "@web/views/list/list_controller";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { onMounted, onWillUnmount } from "@odoo/owl";

const THEME_KEY = "ab_sales_dashboard.theme";

const SNAPSHOT_MODEL = "ab.sales.dashboard.snapshot";
const TELEMETRY_MODEL = "ab.sales.dashboard.report.telemetry";
const PRODUCT_SALES_MODEL = "ab.sales.dashboard.product.sales.report";

const RL_SVG = {
    report: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>',
    calendar: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>',
    arrowRight: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>',
    revenue: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>',
    invoices: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>',
    units: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg>',
    branch: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>',
    clock: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>',
    archive: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="21 8 21 21 3 21 3 8"/><rect x="1" y="3" width="22" height="5"/><line x1="10" y1="12" x2="14" y2="12"/></svg>',
    checkCircle: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>',
    history: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>',
};

function esc(v) { return String(v || "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;"); }

function formatDate(v) {
    if (!v) return "";
    const d = new Date(v);
    if (isNaN(d.getTime())) return v;
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

function buildReportCardHTML(data) {
    const {
        name, date_from, date_to, total_sales, invoice_count, total_units_sold,
        store_filter_label, refresh_date, archive_count, isLatest,
        freshnessLabel, freshnessCls,
    } = data;

    const dateRange = date_from && date_to
        ? `${formatDate(date_from)} — ${formatDate(date_to)}`
        : "";

    const fSales = fmtCurrency(total_sales);
    const fInvoices = fmt(invoice_count);
    const fUnits = fmt(total_units_sold);

    const statusBadges = [];
    if (isLatest) statusBadges.push(`<span class="rl-badge rl-badge--latest">${RL_SVG.checkCircle} ${_t("Latest")}</span>`);
    if (archive_count > 0) statusBadges.push(`<span class="rl-badge rl-badge--archived">${RL_SVG.archive} ${archive_count} ${_t("Archived")}</span>`);

    return `
        <div class="rl-card">
            <div class="rl-card__top">
                <div class="rl-card__head">
                    <div class="rl-card__icon">${RL_SVG.report}</div>
                    <div class="rl-card__name">${esc(name)}</div>
                </div>
                <div class="rl-card__badges">${statusBadges.join("")}</div>
            </div>
            <div class="rl-card__dates">
                <span class="rl-card__date-chip">${RL_SVG.calendar} ${esc(dateRange)}</span>
            </div>
            <div class="rl-card__kpis">
                <span class="rl-kpi-badge rl-kpi-badge--revenue">${RL_SVG.revenue} <strong>${fSales}</strong></span>
                <span class="rl-kpi-badge rl-kpi-badge--invoices">${RL_SVG.invoices} <strong>${fInvoices}</strong> ${_t("Invoices")}</span>
                <span class="rl-kpi-badge rl-kpi-badge--units">${RL_SVG.units} <strong>${fUnits}</strong> ${_t("Units")}</span>
            </div>
            <div class="rl-card__foot">
                <span class="rl-card__meta-chip">${RL_SVG.branch} ${esc(store_filter_label || _t("All Branches"))}</span>
                <span class="rl-card__meta-chip rl-card__meta-chip--time">${RL_SVG.clock} ${freshnessLabel}</span>
            </div>
        </div>
    `;
}

// ─── Shared utilities ──────────────────────────────────────

function fmt(v) {
    if (!v && v !== 0) return "0";
    return new Intl.NumberFormat("en-US").format(v);
}

function fmtMoney(v) {
    if (!v && v !== 0) return "$0";
    return "$" + fmt(v);
}

function fmtCurrency(v) {
    if (!v && v !== 0) return "0";
    return new Intl.NumberFormat("en-US", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    }).format(v);
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

// ─── Product Intelligence — HTML builders ──────────────

const KPI_SVG = {
    revenue: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2v20M17 6H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>',
    units: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg>',
    invoices: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M4 2v20l2-1 2 1 2-1 2 1 2-1 2 1 2-1 2 1V2l-2 1-2-1-2 1-2-1-2 1-2-1-2 1-2-1z"/><path d="M8 7h8M8 11h6M8 15h4"/></svg>',
};

function buildProductIntelligenceHeroHTML(s) {
    const cards = [
        {
            key: "revenue",
            label: _t("Total Sales"),
            value: fmtCurrency(s.total_revenue),
            unit: _t("EGP"),
        },
        {
            key: "units",
            label: _t("Units Sold"),
            value: fmt(s.total_units),
        },
        {
            key: "invoices",
            label: _t("Invoices"),
            value: fmt(s.total_invoices),
        },
    ];

    return `
        <div class="psi-hero">
            <div class="psi-hero__content">
                <div class="psi-hero__text">
                    <h1 class="psi-hero__title">
                        <span class="psi-hero__icon"><i class="fa fa-cube"/></span>
                        ${_t("Product Intelligence")}
                    </h1>
                    <p class="psi-hero__subtitle">${_t("Discover the products driving your business")}</p>
                    <p class="psi-hero__desc">${_t("Sales performance, trends, and insights across all branches.")}</p>
                </div>
                <div class="psi-hero__meta">
                    <span class="psi-hero__pill"><i class="fa fa-refresh"/> ${_t("Live")}</span>
                </div>
            </div>
            <div class="psi-kpi-strip">${cards.map(c => `
                <div class="psi-kpi-card psi-kpi-card--${c.key}">
                    <div class="psi-kpi-card__icon-wrap">${KPI_SVG[c.key]}</div>
                    <div class="psi-kpi-card__body">
                        <div class="psi-kpi-card__label">${c.label}</div>
                        <div class="psi-kpi-card__value">${c.value}</div>
                        ${c.unit ? `<div class="psi-kpi-card__unit">${c.unit}</div>` : ""}
                    </div>
                </div>
            `).join("")}</div>
        </div>
    `;
}

function buildProductLeaderboardHTML(products) {
    return `
        <div class="psi-leaderboard">
            <div class="psi-leaderboard__title">
                <i class="fa fa-trophy"/>
                ${_t("Top Products")}
                <span style="font-weight:400;opacity:0.5">·</span>
                <span style="font-weight:400;opacity:0.7;font-size:11px">${_t("By Revenue")}</span>
            </div>
            <div class="psi-leaderboard__grid">
                ${products.map((p, i) => {
                    const rank = i + 1;
                    const rankCls = rank <= 3 ? `psi-leader-card__rank--${rank}` : "";
                    const status = p.total_sales >= 100000 ? "emerald"
                        : p.total_sales >= 50000 ? "blue"
                        : p.total_sales >= 10000 ? "cyan"
                        : "default";
                    const statusLabel = p.total_sales >= 100000 ? _t("Best Seller")
                        : p.total_sales >= 50000 ? _t("Top")
                        : p.total_sales >= 10000 ? _t("Active")
                        : _t("Standard");
                    return `
                        <div class="psi-leader-card">
                            <div class="psi-leader-card__rank ${rankCls}">${rank}</div>
                            <div class="psi-leader-card__body">
                                <div class="psi-leader-card__name" title="${esc(p.product_name || "")}">${esc(p.product_name || _t("Unknown"))}</div>
                                <div class="psi-leader-card__meta">${esc(p.item_code || "")} · ${fmt(p.units_sold || 0)} ${_t("units")}</div>
                            </div>
                            <div class="psi-leader-card__revenue">${fmtMoney(p.total_sales)}</div>
                            <span class="psi-leader-card__status psi-leader-card__status--${status}">${statusLabel}</span>
                        </div>
                    `;
                }).join("")}
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

        let latestDate = "";
        rows.forEach(r => {
            const cell = r.querySelector('td[data-field="refresh_date"]');
            if (cell) {
                const d = cell.getAttribute("title") || cell.textContent.trim();
                if (d && d > latestDate) latestDate = d;
            }
        });

        rows.forEach(row => {
            if (row.querySelector(".rl-card-cell")) return;

            const data = {};
            row.querySelectorAll("td[data-field]").forEach(td => {
                data[td.dataset.field] = td.textContent.trim();
            });

            const refreshCell = row.querySelector('td[data-field="refresh_date"]');
            const rawDate = refreshCell?.getAttribute("title") || refreshCell?.textContent.trim() || "";
            const rt = relativeTime(rawDate);

            const isLatest = rawDate && rawDate === latestDate;

            const cardHtml = buildReportCardHTML({
                name: data.name || "",
                date_from: data.date_from || "",
                date_to: data.date_to || "",
                total_sales: parseFloat(data.total_sales) || 0,
                invoice_count: parseInt(data.invoice_count) || 0,
                total_units_sold: parseFloat(data.total_units_sold) || 0,
                store_filter_label: data.store_filter_label || "",
                refresh_date: rawDate,
                archive_count: parseInt(data.archive_count) || 0,
                isLatest,
                freshnessLabel: rt.label,
                freshnessCls: rt.cls,
            });

            const allTds = row.querySelectorAll("td");
            const cardColspan = Math.max(allTds.length - 1, 1);

            const cardTd = document.createElement("td");
            cardTd.setAttribute("colspan", String(cardColspan));
            cardTd.className = "rl-card-cell";
            cardTd.innerHTML = cardHtml;

            const firstDataCell = row.querySelector("td:not(.o_list_record_selector)");
            if (firstDataCell) {
                row.insertBefore(cardTd, firstDataCell);
            } else {
                row.appendChild(cardTd);
            }

            row.querySelectorAll("td:not(.o_list_record_selector):not(.rl-card-cell)").forEach(td => {
                td.style.display = "none";
            });
        });
    },

    _observeSnapshotChanges() {
        const action = this.el?.closest(".o_action");
        if (!action) return;
        const tbody = action.querySelector(".o_list_table > tbody");
        if (!tbody) return;

        this._rlObserver = new MutationObserver(() => {
            tbody.querySelectorAll("tr.o_data_row .rl-card-cell").forEach(c => c.remove());
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

    // ─── Product Intelligence ───────────────────────────

    _initProductSalesReport() {
        this._applyTheme("ab_product_sales_action");
        this._wrapTable("psi-table-wrap");
        this._injectProductHero();
        this._injectProductLeaderboard();
    },

    async _injectProductHero() {
        const content = this.el?.closest(".o_action")?.querySelector(".o_content");
        if (!content || content.querySelector(".psi-hero")) return;

        let summary;
        try {
            summary = await this.model.orm.call(PRODUCT_SALES_MODEL, "get_intelligence_summary", [[]]);
        } catch {
            summary = {
                total_products: 0, total_revenue: 0, total_units: 0,
                total_invoices: 0, avg_revenue: 0, medicine_count: 0,
                best_seller_name: "", best_seller_revenue: 0,
            };
        }

        const html = buildProductIntelligenceHeroHTML(summary);
        const tmp = document.createElement("div");
        tmp.innerHTML = html;
        content.prepend(tmp.firstElementChild);
    },

    async _injectProductLeaderboard() {
        const content = this.el?.closest(".o_action")?.querySelector(".o_content");
        if (!content) return;
        const existing = content.querySelector(".psi-leaderboard");
        if (existing) existing.remove();

        let topProducts;
        try {
            topProducts = await this.model.orm.call(PRODUCT_SALES_MODEL, "search_read", [[], [
                "product_name", "total_sales", "units_sold", "item_type", "item_code",
            ], 0, 12, "total_sales desc"]);
        } catch {
            return;
        }
        if (!topProducts || topProducts.length < 3) return;

        const kpiStrip = content.querySelector(".psi-kpi-strip");
        const insertAfter = kpiStrip || content.querySelector(".psi-hero");
        if (!insertAfter) return;

        const tmp = document.createElement("div");
        tmp.innerHTML = buildProductLeaderboardHTML(topProducts);
        insertAfter.after(tmp.firstElementChild);
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
