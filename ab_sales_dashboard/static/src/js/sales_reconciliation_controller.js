/** @odoo-module **/

import { ListController } from "@web/views/list/list_controller";
import { patch } from "@web/core/utils/patch";
import { onMounted, onWillUnmount } from "@odoo/owl";

const THEME_KEY = "ab_sales_dashboard.theme";

function fmt(v) {
    if (!v && v !== 0) return "0";
    return new Intl.NumberFormat("en-US").format(v);
}

function buildReconHeroHTML() {
    return `
        <div class="rcon-hero">
            <div class="rcon-hero__content">
                <div class="rcon-hero__text">
                    <h1 class="rcon-hero__title">\u2699\uFE0F Reconciliation Jobs</h1>
                    <p class="rcon-hero__subtitle">\u0645\u0639\u0627\u0644\u062C\u0627\u062A \u0627\u0644\u0645\u0635\u0627\u062D\u0628\u0629</p>
                    <p class="rcon-hero__desc">Monitor and execute coverage reconciliation tasks across branches.</p>
                </div>
            </div>
        </div>
    `;
}

patch(ListController.prototype, {
    setup() {
        super.setup(...arguments);
        if (this.props.resModel === "ab.sales.dashboard.reconciliation.job") {
            this._rconObserver = null;
            onMounted(() => this._initReconConsole());
            onWillUnmount(() => { if (this._rconObserver) this._rconObserver.disconnect(); });
        }
    },

    _initReconConsole() {
        this._applyReconTheme();
        this._injectReconHero();
        this._decorateReconRows();
        this._observeReconChanges();
    },

    _applyReconTheme() {
        const theme = localStorage.getItem(THEME_KEY) || "dark";
        const action = this.el?.closest(".o_action");
        if (!action) return;
        action.classList.remove("sd-theme-dark", "sd-theme-light", "ab-recon-action");
        action.classList.add(theme === "light" ? "sd-theme-light" : "sd-theme-dark");
        action.classList.add("ab-recon-action");
    },

    _injectReconHero() {
        const content = this.el?.closest(".o_action")?.querySelector(".o_content");
        if (!content || content.querySelector(".rcon-hero")) return;
        const tmp = document.createElement("div");
        tmp.innerHTML = buildReconHeroHTML();
        content.prepend(tmp.firstElementChild);
    },

    _decorateReconRows() {
        const action = this.el?.closest(".o_action");
        if (!action) return;
        const tbody = action.querySelector(".o_list_table > tbody");
        if (!tbody) return;
        const rows = Array.from(tbody.querySelectorAll("tr.o_data_row"));
        if (!rows.length) return;

        rows.forEach((row) => {
            if (row.dataset.rconDecorated) return;
            row.dataset.rconDecorated = "1";

            const stateCell = row.querySelector('td[data-field="state"]');
            if (stateCell) {
                const rawState = stateCell.textContent.trim().toLowerCase();
                const stateMap = {
                    draft: "Draft",
                    analyzing: "Analyzing",
                    ready: "Ready",
                    running: "Running",
                    partial: "Partial",
                    done: "Done",
                    failed: "Failed",
                    cancelled: "Cancelled",
                };
                const label = stateMap[rawState] || rawState;
                stateCell.innerHTML = `<span class="rcon-state rcon-state--${rawState}">${label}</span>`;
            }

            const numericFields = {
                total_branch_days: "rcon-badge--blue",
                missing_branch_days: "rcon-badge--amber",
                processed_branch_days: "rcon-badge--emerald",
                failed_branch_days: "rcon-badge--rose",
                chunk_count: "rcon-badge--violet",
                completed_chunk_count: "rcon-badge--emerald",
                failed_chunk_count: "rcon-badge--rose",
            };
            Object.keys(numericFields).forEach(fieldName => {
                const cell = row.querySelector(`td[data-field="${fieldName}"]`);
                if (!cell) return;
                const val = cell.textContent.trim();
                const color = numericFields[fieldName];
                const isZero = !val || val === "0";
                cell.innerHTML = `<span class="rcon-badge ${color}${isZero ? ' rcon-badge--zero' : ''}">${isZero ? "\u2014" : fmt(parseInt(val, 10))}</span>`;
            });
        });
    },

    _observeReconChanges() {
        const action = this.el?.closest(".o_action");
        if (!action) return;
        const tbody = action.querySelector(".o_list_table > tbody");
        if (!tbody) return;
        this._rconObserver = new MutationObserver(() => {
            const allRows = tbody.querySelectorAll("tr.o_data_row");
            allRows.forEach(r => { delete r.dataset.rconDecorated; });
            this._decorateReconRows();
        });
        this._rconObserver.observe(tbody, { childList: true, subtree: false });
    },
});
