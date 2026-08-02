/** @odoo-module **/

import { ListController } from "@web/views/list/list_controller";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { onMounted, onWillUnmount } from "@odoo/owl";

const THEME_KEY = "ab_sales_dashboard.theme";

const SNAPSHOT_MODEL = "ab_sales_dashboard_snapshot";
const TELEMETRY_MODEL = "ab_sales_dashboard_report_telemetry";
const PRODUCT_SALES_MODEL = "ab_sales_dashboard_product_sales_report";

const RL_ICON = {
    report: "fa-line-chart",
    calendar: "fa-calendar",
    revenue: "fa-money",
    invoices: "fa-file-text-o",
    units: "fa-cubes",
    branch: "fa-hospital-o",
    clock: "fa-clock-o",
    archive: "fa-archive",
    checkCircle: "fa-check-circle",
    products: "fa-medkit",
    stores: "fa-building-o",
};

function faIcon(key) {
    return `<i class="fa ${RL_ICON[key] || "fa-circle"}" aria-hidden="true"></i>`;
}

function esc(v) { return String(v || "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;"); }

function parseNumber(value) {
    const normalized = String(value || "0")
        .replace(/[٠-٩]/g, digit => String("٠١٢٣٤٥٦٧٨٩".indexOf(digit)))
        .replace(/[۰-۹]/g, digit => String("۰۱۲۳۴۵۶۷۸۹".indexOf(digit)));
    const clean = normalized.replace(/[^\d.-]/g, "");
    const parsed = Number(clean);
    return Number.isFinite(parsed) ? parsed : 0;
}

function formatDate(v) {
    if (!v) return "";
    const d = new Date(v);
    if (isNaN(d.getTime())) return v;
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

function rangeDays(dateFrom, dateTo) {
    const from = new Date(dateFrom);
    const to = new Date(dateTo);
    if (isNaN(from.getTime()) || isNaN(to.getTime())) return 0;
    return Math.max(1, Math.round((to - from) / 86400000) + 1);
}

function reportRangeMeta(dateFrom, dateTo) {
    const days = rangeDays(dateFrom, dateTo);
    const range = dateFrom && dateTo ? `${formatDate(dateFrom)} → ${formatDate(dateTo)}` : _t("Date range unavailable");
    if (days <= 1) return { label: _t("Daily Report"), detail: range, cls: "daily" };
    if (days > 30) return { label: _t("Long Range"), detail: range, cls: "long" };
    return { label: _t("Range Report"), detail: range, cls: "range" };
}

function revenueMeta(value) {
    if (value >= 1000000) return { label: _t("High Revenue"), cls: "high" };
    if (value >= 250000) return { label: _t("Strong Sales"), cls: "strong" };
    if (value >= 50000) return { label: _t("Moderate Revenue"), cls: "moderate" };
    return { label: _t("Low Revenue"), cls: "low" };
}

function activityMeta(value) {
    if (value >= 500) return { label: _t("High Activity"), cls: "high" };
    if (value <= 25) return { label: _t("Low Activity"), cls: "low" };
    return { label: _t("Active"), cls: "active" };
}

function unitsMeta(value) {
    if (value >= 10000) return { label: _t("Heavy Movement"), cls: "heavy" };
    if (value >= 1000) return { label: _t("Good Movement"), cls: "good" };
    return { label: _t("Light Movement"), cls: "light" };
}

function productMixMeta(value) {
    if (value >= 250) return { label: _t("Wide Product Mix"), cls: "wide" };
    if (value <= 25) return { label: _t("Limited Product Mix"), cls: "limited" };
    return { label: _t("Product Mix"), cls: "normal" };
}

function branchScopeMeta(label, storesWithSales) {
    const raw = String(label || "").trim();
    const lower = raw.toLowerCase();
    if (!raw || lower.includes("all") || raw.includes("كل")) {
        return { label: _t("All Branches"), detail: storesWithSales ? _t("%s Active Stores").replace("%s", fmt(storesWithSales)) : "", cls: "all" };
    }
    const parts = raw.split(/[,،]/).map(part => part.trim()).filter(Boolean);
    if (parts.length > 1) {
        return { label: _t("Multi Branches"), detail: _t("%s Branches").replace("%s", fmt(storesWithSales || parts.length)), cls: "multi" };
    }
    if (storesWithSales > 1) {
        return { label: _t("Multi Branches"), detail: _t("%s Branches").replace("%s", fmt(storesWithSales)), cls: "multi" };
    }
    return { label: _t("Single Branch"), detail: raw, cls: "single" };
}

function archiveMeta(count) {
    if (count > 3) return { label: _t("%s Archives").replace("%s", fmt(count)), cls: "vaulted" };
    if (count > 1) return { label: _t("%s Archives").replace("%s", fmt(count)), cls: "archived" };
    if (count === 1) return { label: _t("Archived"), cls: "archived" };
    return { label: _t("No Archive"), cls: "none" };
}

function generatedDetail(dateStr) {
    if (!dateStr) return "";
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return dateStr;
    const date = d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
    const time = d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", hour12: true });
    return _t("Generated %s").replace("%s", `${date} · ${time}`);
}

function buildReportCardHTML(data) {
    const {
        name, date_from, date_to, total_sales, invoice_count, total_units_sold,
        unique_products_sold, stores_with_sales, store_filter_label, refresh_date, archive_count, isLatest,
        freshnessLabel, freshnessCls,
    } = data;

    const range = reportRangeMeta(date_from, date_to);
    const revenue = revenueMeta(total_sales);
    const activity = activityMeta(invoice_count);
    const units = unitsMeta(total_units_sold);
    const productMix = productMixMeta(unique_products_sold);
    const branch = branchScopeMeta(store_filter_label, stores_with_sales);
    const archive = archiveMeta(archive_count);
    const generated = generatedDetail(refresh_date);
    const fSales = fmtCurrency(total_sales);
    const fInvoices = fmt(invoice_count);
    const fUnits = fmt(total_units_sold);
    const fProducts = fmt(unique_products_sold);
    const fStores = fmt(stores_with_sales);

    const statusBadges = [];
    if (isLatest) statusBadges.push(`<span class="rl-badge rl-badge--latest">${faIcon("checkCircle")} ${_t("Latest")}</span>`);
    statusBadges.push(`<span class="rl-badge rl-badge--${archive.cls}">${faIcon("archive")} ${archive.label}</span>`);
    statusBadges.push(`<span class="rl-badge ${freshnessCls}">${faIcon("clock")} ${freshnessLabel}</span>`);

    return `
        <div class="rl-card">
            <div class="rl-card__top">
                <div class="rl-card__head">
                    <div class="rl-card__icon">${faIcon("report")}</div>
                    <div class="rl-card__identity">
                        <div class="rl-card__name">${esc(name || _t("Sales Dashboard Report"))}</div>
                        <div class="rl-card__subtitle">${_t("Generated Snapshot")}</div>
                    </div>
                </div>
                <div class="rl-card__badges">${statusBadges.join("")}</div>
            </div>
            <div class="rl-card__body">
                <div class="rl-card__revenue">
                    <span class="rl-card__revenue-label">${_t("Revenue")}</span>
                    <span class="rl-card__revenue-value">${_t("EGP")} ${fSales}</span>
                    <span class="rl-smart-badge rl-smart-badge--revenue-${revenue.cls}">${faIcon("revenue")} ${revenue.label}</span>
                </div>
                <div class="rl-card__meta-grid">
                    <span class="rl-card__date-chip rl-card__date-chip--${range.cls}">${faIcon("calendar")}<strong>${range.label}</strong><em>${esc(range.detail)}</em></span>
                    <span class="rl-card__scope rl-card__scope--${branch.cls}">${faIcon("branch")}<strong>${branch.label}</strong><em>${esc(branch.detail || "")}</em></span>
                    <span class="rl-card__generated">${faIcon("clock")}<strong>${freshnessLabel}</strong><em>${esc(generated)}</em></span>
                </div>
            </div>
            <div class="rl-card__kpis">
                <span class="rl-kpi-badge rl-kpi-badge--invoices">${faIcon("invoices")}<strong>${fInvoices}</strong><small>${_t("Invoices")}</small><em>${activity.label}</em></span>
                <span class="rl-kpi-badge rl-kpi-badge--units">${faIcon("units")}<strong>${fUnits}</strong><small>${_t("Units")}</small><em>${units.label}</em></span>
                <span class="rl-kpi-badge rl-kpi-badge--products">${faIcon("products")}<strong>${fProducts}</strong><small>${_t("Products")}</small><em>${productMix.label}</em></span>
                <span class="rl-kpi-badge rl-kpi-badge--stores">${faIcon("stores")}<strong>${fStores}</strong><small>${_t("Active Stores")}</small></span>
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

function fmtEgp(v) {
    if (!v && v !== 0) return _t("EGP") + " 0";
    return _t("EGP") + " " + fmt(v);
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
    if (diffH < 24) return { label: _t("%s hours ago").replace("%s", Math.floor(diffH)), cls: "rl-status--fresh", freshness: "fresh" };
    const diffD = diffH / 24;
    if (diffD < 1) return { label: _t("Today"), cls: "rl-status--today", freshness: "today" };
    if (diffD < 2) return { label: _t("Yesterday"), cls: "rl-status--ok", freshness: "recent" };
    if (diffD < 7) return { label: _t("%s days ago").replace("%s", Math.floor(diffD)), cls: "rl-status--ok", freshness: "recent" };
    if (diffD < 30) return { label: _t("%s days ago").replace("%s", Math.floor(diffD)), cls: "rl-status--stale", freshness: "stale" };
    return { label: _t("Old Report"), cls: "rl-status--muted", freshness: "old" };
}

// ─── Snapshot — Hero HTML builders ─────────────────────────

function buildSnapshotHeroHTML(summary) {
    const kpis = [
        { icon: "fa-file-text-o", label: _t("Saved Reports"), value: fmt(summary.total_reports), accent: "rl-accent--cyan" },
        { icon: "fa-clock-o", label: _t("Latest Snapshot"), value: summary.latest_date ? formatDate(summary.latest_date) : _t("N/A"), accent: "rl-accent--blue", sm: true },
        { icon: "fa-money", label: _t("Total Revenue"), value: fmtEgp(summary.total_sales || 0), accent: "rl-accent--emerald" },
        { icon: "fa-line-chart", label: _t("Average Revenue"), value: fmtEgp(summary.average_revenue || 0), accent: "rl-accent--emerald" },
    ];

    return `
        <div class="rl-hero">
            <div class="rl-hero__content">
                <div class="rl-hero__text">
                    <h1 class="rl-hero__title">
                        <span class="rl-hero__icon"><i class="fa fa-line-chart"/></span>
                        ${_t("Reports Library")}
                    </h1>
                    <p class="rl-hero__subtitle">${_t("Business Snapshot Library")}</p>
                    <p class="rl-hero__desc">${_t("Browse historical Sales Dashboard snapshots and compare previous business performance.")}</p>
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
                        ${_t("Reporting Analytics")}
                    </h1>
                    <p class="ac-hero__subtitle">${_t("Monitoring Console")}</p>
                    <p class="ac-hero__desc">${_t("Audit trail of dashboard reads, refreshes, report modes, coverage, performance, and data-source usage.")}</p>
                </div>
            </div>
            <div class="ac-kpi-row">
                <div class="ac-kpi ac-accent--cyan">
                    <div class="ac-kpi__icon"><i class="fa fa-clock-o"/></div>
                    <div class="ac-kpi__body">
                        <div class="ac-kpi__label">${_t("Today Events")}</div>
                        <div class="ac-kpi__value">${fmt(summary.today_events || 0)}</div>
                    </div>
                </div>
                <div class="ac-kpi ac-accent--blue">
                    <div class="ac-kpi__icon"><i class="fa fa-tachometer"/></div>
                    <div class="ac-kpi__body">
                        <div class="ac-kpi__label">${_t("Average Duration")}</div>
                        <div class="ac-kpi__value ac-kpi__value--sm">${summary.avg_duration ? fmt(summary.avg_duration) + " ms" : "—"}</div>
                    </div>
                </div>
                <div class="ac-kpi ac-accent--rose">
                    <div class="ac-kpi__icon"><i class="fa fa-times-circle"/></div>
                    <div class="ac-kpi__body">
                        <div class="ac-kpi__label">${_t("Failed Operations")}</div>
                        <div class="ac-kpi__value">${fmt(summary.failed_count || 0)}</div>
                    </div>
                </div>
                <div class="ac-kpi ac-accent--amber">
                    <div class="ac-kpi__icon"><i class="fa fa-exclamation-triangle"/></div>
                    <div class="ac-kpi__body">
                        <div class="ac-kpi__label">${_t("Coverage Issues")}</div>
                        <div class="ac-kpi__value">${fmt(summary.issue_count || 0)}</div>
                    </div>
                </div>
                <div class="ac-kpi ac-accent--violet">
                    <div class="ac-kpi__icon"><i class="fa fa-bolt"/></div>
                    <div class="ac-kpi__body">
                        <div class="ac-kpi__label">${_t("Total Events")}</div>
                        <div class="ac-kpi__value">${fmt(summary.total_events || 0)}</div>
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
            summary.average_revenue = summary.total_reports
                ? parseNumber(summary.total_sales) / parseNumber(summary.total_reports)
                : 0;
        } catch {
            summary = {
                total_reports: 0, latest_date: false,
                total_sales: 0, total_invoices: 0,
                unique_stores: 0, avg_daily_sales: 0,
                today_reports: 0, archived_reports: 0, average_revenue: 0,
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
                total_sales: parseNumber(data.total_sales),
                invoice_count: parseNumber(data.invoice_count),
                total_units_sold: parseNumber(data.total_units_sold),
                unique_products_sold: parseNumber(data.unique_products_sold),
                stores_with_sales: parseNumber(data.stores_with_sales),
                store_filter_label: data.store_filter_label || "",
                refresh_date: rawDate,
                archive_count: parseNumber(data.archive_count),
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
            const failed = data.filter(r => r.coverage_state === "unavailable").length;
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
                failed_count: failed,
                issue_count: issues,
                avg_duration: avgDuration,
            };
        } catch {
            summary = { total_events: 0, today_events: 0, complete_count: 0, failed_count: 0, issue_count: 0, avg_duration: 0 };
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
