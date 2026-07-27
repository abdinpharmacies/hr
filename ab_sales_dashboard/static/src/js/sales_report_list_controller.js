/** @odoo-module **/

import { ListController } from "@web/views/list/list_controller";
import { patch } from "@web/core/utils/patch";
import { onMounted, onWillUnmount } from "@odoo/owl";

const THEME_KEY = "ab_sales_dashboard.theme";

function fmt(v) {
    if (!v && v !== 0) return "0";
    return new Intl.NumberFormat("en-US").format(v);
}

function fmtMoney(v) {
    if (!v && v !== 0) return "$0";
    return "$" + fmt(v);
}

function relativeTime(dateStr) {
    if (!dateStr) return { label: "Unknown", cls: "rl-status--muted", freshness: "old" };
    const d = new Date(dateStr);
    const now = new Date();
    const diffMs = now - d;
    const diffH = diffMs / 3600000;
    if (diffH < 1) return { label: "Just now", cls: "rl-status--fresh", freshness: "fresh" };
    if (diffH < 24) return { label: Math.floor(diffH) + "h ago", cls: "rl-status--fresh", freshness: "fresh" };
    const diffD = diffH / 24;
    if (diffD < 1) return { label: "Today", cls: "rl-status--today", freshness: "today" };
    if (diffD < 2) return { label: "Yesterday", cls: "rl-status--ok", freshness: "recent" };
    if (diffD < 7) return { label: Math.floor(diffD) + "d ago", cls: "rl-status--ok", freshness: "recent" };
    if (diffD < 30) return { label: Math.floor(diffD) + "d ago", cls: "rl-status--stale", freshness: "stale" };
    return { label: Math.floor(diffD) + "d old", cls: "rl-status--muted", freshness: "old" };
}

function buildHeroHTML(summary) {
    const kpis = [
        { icon: "fa-file-text-o", label: "Total Reports", value: fmt(summary.total_reports), accent: "rl-accent--cyan" },
        { icon: "fa-clock-o", label: "Latest", value: summary.latest_date ? summary.latest_date.split(" ")[1] || summary.latest_date : "N/A", accent: "rl-accent--emerald", sm: true },
        { icon: "fa-usd", label: "Total Sales", value: fmtMoney(summary.total_sales), accent: "rl-accent--emerald" },
        { icon: "fa-receipt", label: "Invoices", value: fmt(summary.total_invoices), accent: "rl-accent--blue" },
        { icon: "fa-building-o", label: "Branches", value: fmt(summary.unique_stores), accent: "rl-accent--violet" },
        { icon: "fa-line-chart", label: "Avg Daily", value: fmtMoney(summary.avg_daily_sales), accent: "rl-accent--amber" },
    ];

    const kpiHTML = kpis.map(k => `
        <div class="rl-kpi ${k.accent}">
            <div class="rl-kpi__icon"><i class="fa ${k.icon}"/></div>
            <div class="rl-kpi__body">
                <div class="rl-kpi__label">${k.label}</div>
                <div class="rl-kpi__value${k.sm ? ' rl-kpi__value--sm' : ''}">${k.value}</div>
            </div>
        </div>
    `).join("");

    return `
        <div class="rl-hero">
            <div class="rl-hero__content">
                <div class="rl-hero__text">
                    <h1 class="rl-hero__title">
                        <span class="rl-hero__icon"><i class="fa fa-line-chart"/></span>
                        Sales Reports Library
                    </h1>
                    <p class="rl-hero__subtitle">\u0645\u0643\u062A\u0628\u0629 \u0627\u0644\u062A\u0642\u0627\u0631\u064A\u0631 \u0627\u0644\u0645\u0628\u064A\u0639\u0627\u062A</p>
                    <p class="rl-hero__desc">Browse, compare, and manage historical sales report snapshots.</p>
                </div>
            </div>
            <div class="rl-kpi-row">${kpiHTML}</div>
        </div>
    `;
}

patch(ListController.prototype, {
    setup() {
        super.setup(...arguments);
        if (this.props.resModel === "ab.sales.dashboard.snapshot") {
            this._rlObserver = null;
            onMounted(() => this._initReportLibrary());
            onWillUnmount(() => {
                if (this._rlObserver) this._rlObserver.disconnect();
            });
        }
    },

    _initReportLibrary() {
        this._applyTheme();
        this._wrapTable();
        this._injectHero();
        this._decorateRows();
        this._observeChanges();
    },

    _applyTheme() {
        const theme = localStorage.getItem(THEME_KEY) || "dark";
        const action = this.el?.closest(".o_action");
        if (!action) return;
        action.classList.remove("sd-theme-dark", "sd-theme-light", "ab_rl_action");
        action.classList.add(theme === "light" ? "sd-theme-light" : "sd-theme-dark");
        action.classList.add("ab_rl_action");
    },

    _wrapTable() {
        const content = this.el?.closest(".o_action")?.querySelector(".o_content");
        if (content && !content.classList.contains("rl-table-wrap")) {
            content.classList.add("rl-table-wrap");
        }
    },

    async _injectHero() {
        const content = this.el?.closest(".o_action")?.querySelector(".o_content");
        if (!content || content.querySelector(".rl-hero")) return;

        let summary;
        try {
            summary = await this.model.orm.call("ab.sales.dashboard.snapshot", "get_library_summary", []);
        } catch {
            summary = {
                total_reports: 0,
                latest_date: false,
                total_sales: 0,
                total_invoices: 0,
                unique_stores: 0,
                avg_daily_sales: 0,
            };
        }

        const tmp = document.createElement("div");
        tmp.innerHTML = buildHeroHTML(summary);
        content.prepend(tmp.firstElementChild);
    },

    _decorateRows() {
        const action = this.el?.closest(".o_action");
        if (!action) return;
        const tbody = action.querySelector(".o_list_table > tbody");
        if (!tbody) return;
        const rows = Array.from(tbody.querySelectorAll("tr.o_data_row"));
        if (!rows.length) return;

        // Compute sales rankings for the visible page
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

            // 1. Freshness stripe — class on the row tr, no DOM mutation inside cells
            const refreshCell = row.querySelector('td[data-field="refresh_date"]');
            if (refreshCell) {
                const rawDate = refreshCell.getAttribute("title") || refreshCell.textContent.trim();
                const rt = relativeTime(rawDate);
                row.classList.add("rl-freshness--" + rt.freshness);

                // Append a small freshness chip AFTER existing cell content
                const chip = document.createElement("span");
                chip.className = "rl-status " + rt.cls;
                chip.textContent = rt.label;
                refreshCell.appendChild(chip);
            }

            // 2. Rank badge — prepend a small numbered badge BEFORE existing name content
            const nameCell = row.querySelector('td[data-field="name"]');
            if (nameCell && rank >= 1 && rank <= 5) {
                const badge = document.createElement("span");
                badge.className = "rl-rank rl-rank--" + rank;
                badge.textContent = rank;
                badge.title = ["", "Top", "2nd", "3rd", "4th", "5th"][rank] + " Report";
                nameCell.prepend(badge);
            }

            // 3. Archive indicator — small amber dot for rows with archived reports
            const archiveCell = row.querySelector('td[data-field="archive_count"]');
            if (archiveCell && nameCell) {
                const archiveVal = parseInt(archiveCell.textContent.replace(/[^0-9]/g, ""), 10);
                if (archiveVal > 0 && !nameCell.querySelector(".rl-archived-dot")) {
                    const dot = document.createElement("span");
                    dot.className = "rl-archived-dot";
                    dot.title = archiveVal + " archived report(s)";
                    nameCell.appendChild(dot);
                }
            }
        });
    },

    _observeChanges() {
        const action = this.el?.closest(".o_action");
        if (!action) return;
        const tbody = action.querySelector(".o_list_table > tbody");
        if (!tbody) return;

        this._rlObserver = new MutationObserver(() => {
            const allRows = tbody.querySelectorAll("tr.o_data_row");
            allRows.forEach(r => { delete r.dataset.rlDecorated; });
            this._decorateRows();
        });
        this._rlObserver.observe(tbody, { childList: true, subtree: false });
    },

    async openRecord(record, options) {
        if (this.props.resModel === "ab.sales.dashboard.snapshot") {
            const action = await this.model.orm.call(
                "ab.sales.dashboard.snapshot",
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
