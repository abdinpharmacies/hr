/** @odoo-module **/

import { ListController } from "@web/views/list/list_controller";
import { ListRenderer } from "@web/views/list/list_renderer";
import { FormController } from "@web/views/form/form_controller";
import { X2ManyField } from "@web/views/fields/x2many/x2many_field";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { onMounted, onWillUnmount } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { ReconciliationChunkDialog } from "./reconciliation_chunk_dialog";

const THEME_KEY = "ab_sales_dashboard.theme";
const RECON_MODEL = "ab.sales.dashboard.reconciliation.job";

function fmt(v) {
    if (!v && v !== 0) return "0";
    return new Intl.NumberFormat("en-US").format(v);
}

function buildReconHeroHTML() {
    return `
        <div class="rcon-hero">
            <div class="rcon-hero__content">
                <div class="rcon-hero__text">
                    <h1 class="rcon-hero__title">
                        <span class="rcon-hero__icon"><i class="fa fa-line-chart"></i></span>
                        ${_t("Reconciliation Jobs")}
                    </h1>
                    <p class="rcon-hero__subtitle">${_t("Reconciliation processors")}</p>
                    <p class="rcon-hero__desc">${_t("Monitor and execute coverage reconciliation tasks across branches.")}</p>
                </div>
            </div>
        </div>
    `;
}

function applyReconThemeToAction(action) {
    const theme = localStorage.getItem(THEME_KEY) || "dark";
    if (!action) return;
    const themeClass = theme === "light" ? "sd-theme-light" : "sd-theme-dark";
    const otherThemeClass = theme === "light" ? "sd-theme-dark" : "sd-theme-light";
    const needsUpdate = (
        !action.classList.contains(themeClass) ||
        action.classList.contains(otherThemeClass) ||
        !action.classList.contains("ab_sales_dashboard") ||
        !action.classList.contains("ab-recon-action")
    );
    if (!needsUpdate) return;
    action.classList.remove(otherThemeClass);
    action.classList.add(themeClass, "ab_sales_dashboard", "ab-recon-action");
}

function applyReconTheme(controller) {
    applyReconThemeToAction(controller.el?.closest(".o_action"));
}

function isReconController(controller) {
    const className = [
        controller.props?.className,
        controller.props?.archInfo?.className,
        controller.props?.archInfo?.class,
    ].filter(Boolean).join(" ");
    return controller.props?.resModel === RECON_MODEL
        || controller.model?.root?.resModel === RECON_MODEL
        || className.includes("ab-recon-list")
        || className.includes("ab-recon-form");
}

function decorateReconRows(action) {
    if (!action) return false;
    const table = action.querySelector(".o_list_table");
    const tbody = table?.querySelector("tbody");
    if (!table || !tbody) return false;
    const rows = Array.from(tbody.querySelectorAll("tr.o_data_row"));
    if (!rows.length) return false;
    let didDecorate = false;

    rows.forEach((row) => {
        if (row.dataset.rconDecorated) return;
        row.dataset.rconDecorated = "1";
        didDecorate = true;

        const stateCell = row.querySelector('td[data-field="state"]');
        if (stateCell) {
            const rawState = stateCell.textContent.trim().toLowerCase();
            const stateMap = {
                draft: _t("Draft"),
                analyzing: _t("Analyzing"),
                ready: _t("Ready"),
                running: _t("Running"),
                partial: _t("Partial"),
                done: _t("Done"),
                failed: _t("Failed"),
                cancelled: _t("Cancelled"),
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
    if (didDecorate) {
        table.dispatchEvent(new CustomEvent("ab-recon-rows-decorated", { bubbles: true }));
    }
    return didDecorate;
}

function bindReconTableScroll(content) {
    if (!content) return;
    const updateScrolledState = () => {
        content.classList.toggle("rcon-table-wrap--scrolled", content.scrollTop > 0);
    };
    if (!content.dataset.rconScrollBound) {
        content.addEventListener("scroll", updateScrolledState, { passive: true });
        content.dataset.rconScrollBound = "1";
        updateScrolledState();
    }
}

function enhanceReconDom() {
    const actions = new Set(Array.from(document.querySelectorAll(".o_action.ab-recon-list")));
    document.querySelectorAll(".o_action .ab-recon-form").forEach((form) => {
        const action = form.closest(".o_action");
        if (action) actions.add(action);
    });

    actions.forEach((action) => {
        applyReconThemeToAction(action);
        const content = action.querySelector(".o_content");
        if (content && action.classList.contains("ab-recon-list")) {
            content.classList.add("rcon-table-wrap");
            bindReconTableScroll(content);
            if (!content.querySelector(".rcon-hero")) {
                const tmp = document.createElement("div");
                tmp.innerHTML = buildReconHeroHTML();
                content.prepend(tmp.firstElementChild);
            }
            if (action.querySelector(".o_list_table > tbody > tr.o_data_row:not([data-rcon-decorated])")) {
                decorateReconRows(action);
            }
        }
    });
}

let reconEnhanceQueued = false;
function queueReconDomEnhancement() {
    if (reconEnhanceQueued) return;
    if (!document.querySelector(".o_action.ab-recon-list, .o_action .ab-recon-form")) return;
    reconEnhanceQueued = true;
    requestAnimationFrame(() => {
        reconEnhanceQueued = false;
        enhanceReconDom();
    });
}

patch(ListController.prototype, {
    setup() {
        super.setup(...arguments);
        if (isReconController(this)) {
            this._rconObserver = null;
            this._rconThemeStorageHandler = (event) => {
                if (!event || event.key === THEME_KEY) {
                    applyReconTheme(this);
                }
            };
            onMounted(() => this._queueReconInit());
            onMounted(() => window.addEventListener("storage", this._rconThemeStorageHandler));
            onWillUnmount(() => {
                if (this._rconFrame) cancelAnimationFrame(this._rconFrame);
                if (this._rconObserver) this._rconObserver.disconnect();
                window.removeEventListener("storage", this._rconThemeStorageHandler);
            });
        }
    },

    _queueReconInit() {
        this._initReconConsole();
        this._rconFrame = requestAnimationFrame(() => this._initReconConsole());
    },

    _initReconConsole() {
        this._applyReconTheme();
        this._wrapReconTable();
        this._injectReconHero();
        this._decorateReconRows();
        this._observeReconChanges();
    },

    _applyReconTheme() {
        applyReconTheme(this);
    },

    _injectReconHero() {
        const content = this.el?.closest(".o_action")?.querySelector(".o_content");
        if (!content || content.querySelector(".rcon-hero")) return;
        const tmp = document.createElement("div");
        tmp.innerHTML = buildReconHeroHTML();
        content.prepend(tmp.firstElementChild);
    },

    _wrapReconTable() {
        const content = this.el?.closest(".o_action")?.querySelector(".o_content");
        if (content) {
            content.classList.add("rcon-table-wrap");
            bindReconTableScroll(content);
        }
    },

    _decorateReconRows() {
        const action = this.el?.closest(".o_action");
        decorateReconRows(action);
    },

    _observeReconChanges() {
        const action = this.el?.closest(".o_action");
        if (!action) return;
        const tbody = action.querySelector(".o_list_table > tbody");
        if (!tbody) return;
        if (this._rconObserver) this._rconObserver.disconnect();
        this._rconObserver = new MutationObserver(() => {
            const allRows = tbody.querySelectorAll("tr.o_data_row");
            allRows.forEach(r => { delete r.dataset.rconDecorated; });
            this._decorateReconRows();
        });
        this._rconObserver.observe(tbody, { childList: true, subtree: false });
    },
});

patch(ListRenderer.prototype, {
    setup() {
        super.setup(...arguments);
        this._rconColumnWidthResetHandler = () => this._queueReconColumnWidthReset();
        onMounted(() => {
            const table = this.tableRef?.el;
            if (!table?.closest(".o_action.ab-recon-list")) return;
            table.addEventListener("ab-recon-rows-decorated", this._rconColumnWidthResetHandler);
            if (table.querySelector("tbody tr.o_data_row[data-rcon-decorated]")) {
                this._queueReconColumnWidthReset();
            }
        });
        onWillUnmount(() => {
            if (this._rconColumnWidthFrame) cancelAnimationFrame(this._rconColumnWidthFrame);
            const table = this.tableRef?.el;
            table?.removeEventListener("ab-recon-rows-decorated", this._rconColumnWidthResetHandler);
        });
    },

    _queueReconColumnWidthReset() {
        if (this._rconColumnWidthFrame) cancelAnimationFrame(this._rconColumnWidthFrame);
        this._rconColumnWidthFrame = requestAnimationFrame(() => {
            this._rconColumnWidthFrame = null;
            const table = this.tableRef?.el;
            if (!table?.isConnected || !table.closest(".o_action.ab-recon-list")) return;
            this.columnWidths?.resetWidths?.();
        });
    },
});

patch(FormController.prototype, {
    setup() {
        super.setup(...arguments);
        if (isReconController(this)) {
            this._rconThemeStorageHandler = (event) => {
                if (!event || event.key === THEME_KEY) {
                    applyReconTheme(this);
                }
            };
            onMounted(() => applyReconTheme(this));
            onMounted(() => window.addEventListener("storage", this._rconThemeStorageHandler));
            onWillUnmount(() => window.removeEventListener("storage", this._rconThemeStorageHandler));
        }
    },
});

patch(X2ManyField.prototype, {
    setup() {
        super.setup(...arguments);
        this.dialogService = useService("dialog");
    },

    async openRecord(record) {
        if (
            this.props.record.resModel === "ab.sales.dashboard.reconciliation.job" &&
            this.props.name === "chunk_ids"
        ) {
            const chunkId = record.resId;
            if (chunkId) {
                this.dialogService.add(ReconciliationChunkDialog, {
                    chunkId,
                });
                return;
            }
        }
        return super.openRecord(...arguments);
    },
});

function startReconDomEnhancement() {
    enhanceReconDom();
    const reconDomObserver = new MutationObserver(() => queueReconDomEnhancement());
    reconDomObserver.observe(document.body, { childList: true, subtree: true });
    setTimeout(enhanceReconDom, 0);
    setTimeout(enhanceReconDom, 300);
    setTimeout(enhanceReconDom, 1000);
}

if (document.body) {
    startReconDomEnhancement();
} else {
    window.addEventListener("DOMContentLoaded", startReconDomEnhancement, { once: true });
}
window.addEventListener("storage", (event) => {
    if (!event || event.key === THEME_KEY) {
        enhanceReconDom();
    }
});
