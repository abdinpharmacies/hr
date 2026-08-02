/** @odoo-module **/

import { ListController } from "@web/views/list/list_controller";
import { ListRenderer } from "@web/views/list/list_renderer";
import { FormController } from "@web/views/form/form_controller";
import { X2ManyField } from "@web/views/fields/x2many/x2many_field";
import { patch } from "@web/core/utils/patch";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { Component, onMounted, onWillUnmount, xml } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { ReconciliationChunkDialog } from "./reconciliation_chunk_dialog";

const THEME_KEY = "ab_sales_dashboard.theme";
const RECON_MODEL = "ab_sales_dashboard_reconciliation_job";

function fmt(v) {
    if (!v && v !== 0) return "0";
    return new Intl.NumberFormat("en-US").format(v);
}

function esc(value) {
    return String(value ?? "").replace(/[&<>"']/g, (char) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
    }[char]));
}

function numberValue(value) {
    const parsed = Number(value || 0);
    return Number.isFinite(parsed) ? parsed : 0;
}

function dateValue(value) {
    if (!value) return "";
    if (typeof value === "string") return value;
    if (value.toISODate) return value.toISODate();
    return String(value);
}

function formatDate(value) {
    const raw = dateValue(value);
    if (!raw) return "\u2014";
    const date = new Date(`${raw}T00:00:00`);
    if (Number.isNaN(date.getTime())) return raw;
    const locale = (document.documentElement.lang || "en-US").replace("_", "-");
    return new Intl.DateTimeFormat(locale, { day: "2-digit", month: "short" }).format(date);
}

function arrowLabel() {
    return String.fromCharCode(8594);
}

function many2oneLabel(value) {
    if (!value) return "";
    if (typeof value === "object") return value.display_name || value.name || value[1] || "";
    return String(value);
}

const STATE_META = {
    draft: {
        label: _t("Draft"),
        icon: "fa-circle-o",
        cls: "draft",
        tooltip: _t("This reconciliation job has not started yet."),
    },
    analyzing: {
        label: _t("Analyzing"),
        icon: "fa-search",
        cls: "analyzing",
        tooltip: _t("Coverage analysis is currently running."),
    },
    ready: {
        label: _t("Ready"),
        icon: "fa-magic",
        cls: "ready",
        tooltip: _t("This job is ready to start reconciliation."),
    },
    running: {
        label: _t("Running"),
        icon: "fa-spinner fa-spin",
        cls: "running",
        tooltip: _t("Reconciliation chunks are currently running."),
    },
    partial: {
        label: _t("Partial"),
        icon: "fa-exclamation-circle",
        cls: "partial",
        tooltip: _t("Some chunks completed and some chunks failed."),
    },
    done: {
        label: _t("Done"),
        icon: "fa-check-circle",
        cls: "done",
        tooltip: _t("All chunks were completed successfully."),
    },
    failed: {
        label: _t("Failed"),
        icon: "fa-times-circle",
        cls: "failed",
        tooltip: _t("This job requires attention because reconciliation failed."),
    },
    cancelled: {
        label: _t("Cancelled"),
        icon: "fa-square",
        cls: "cancelled",
        tooltip: _t("This reconciliation job was cancelled."),
    },
};

function getStateMeta(state) {
    return STATE_META[state] || {
        label: state || "\u2014",
        icon: "fa-circle",
        cls: "default",
        tooltip: _t("Current reconciliation status."),
    };
}

function progressBucket(progress) {
    const bucket = Math.max(0, Math.min(100, Math.round(numberValue(progress) / 10) * 10));
    return `rcon-progress--p${bucket}`;
}

class ReconStateBadge extends Component {
    static template = xml`
        <span class="rcon-state rcon-widget"
              t-att-class="'rcon-state--' + getStateClass()"
              t-att-title="getStateTooltip()"
              t-att-data-state="state">
            <i class="fa" t-att-class="getStateIcon()"/>
            <span t-esc="getStateLabel()"/>
        </span>
    `;
    static props = { name: String, record: Object, readonly: Boolean };

    get state() { return this.props.record.data[this.props.name] || ""; }
    getStateClass() { return getStateMeta(this.state).cls; }
    getStateIcon() { return getStateMeta(this.state).icon; }
    getStateLabel() { return getStateMeta(this.state).label; }
    getStateTooltip() { return getStateMeta(this.state).tooltip; }
}

class ReconJobIdentity extends Component {
    static template = xml`
        <div class="rcon-job rcon-widget">
            <span class="rcon-job__icon"><i class="fa fa-line-chart"/></span>
            <span class="rcon-job__body">
                <span class="rcon-job__title" t-esc="title"/>
                <span class="rcon-job__meta">
                    <i class="fa fa-calendar"/>
                    <t t-esc="dateRange"/>
                    <t t-if="state === 'draft'">
                        <span class="rcon-job__helper" t-esc="notStartedLabel"/>
                    </t>
                </span>
            </span>
        </div>
    `;
    static props = { name: String, record: Object, readonly: Boolean };

    get title() { return _t("Sales Dashboard Reconciliation"); }
    get state() { return this.props.record.data.state || ""; }
    get notStartedLabel() { return _t("Not started"); }
    get dateRange() {
        return `${formatDate(this.props.record.data.date_from)} ${arrowLabel()} ${formatDate(this.props.record.data.date_to)}`;
    }
}

class ReconBranchScope extends Component {
    static template = xml`
        <div class="rcon-scope rcon-widget" t-att-title="scopeLabel">
            <span class="rcon-scope__main">
                <i class="fa fa-building-o"/>
                <span t-esc="scopeLabel"/>
            </span>
        </div>
    `;
    static props = { name: String, record: Object, readonly: Boolean };

    get key() { return String(this.props.record.data[this.props.name] || "").trim(); }
    get keyParts() {
        if (!this.key || this.key === "all") return [];
        return this.key.split(",").map(v => v.trim()).filter(Boolean);
    }
    get scopeLabel() {
        if (!this.key || this.key === "all") return _t("All Stores");
        const count = this.keyParts.length;
        return count === 1 ? _t("1 Branch") : _t("%s Branches").replace("%s", fmt(count));
    }
}

const METRIC_META = {
    total_branch_days: { label: _t("Total"), icon: "fa-calendar-check-o", cls: "blue" },
    missing_branch_days: { label: _t("Missing"), icon: "fa-exclamation-triangle", cls: "amber" },
    processed_branch_days: { label: _t("Processed"), icon: "fa-check-circle", cls: "emerald" },
    failed_branch_days: { label: _t("Failed"), icon: "fa-times-circle", cls: "rose" },
    failed_chunk_count: { label: _t("Failed"), icon: "fa-times-circle", cls: "rose" },
    completed_chunk_count: { label: _t("Done"), icon: "fa-check-circle", cls: "emerald" },
};

class ReconMetricPill extends Component {
    static template = xml`
        <span class="rcon-metric-pill rcon-widget"
              t-att-class="'rcon-metric-pill--' + meta.cls + (value ? '' : ' rcon-metric-pill--zero')"
              t-att-title="meta.label">
            <i class="fa" t-att-class="meta.icon"/>
            <span class="rcon-metric-pill__body">
                <strong t-esc="displayValue"/>
                <small t-esc="meta.label"/>
            </span>
        </span>
    `;
    static props = { name: String, record: Object, readonly: Boolean };

    get meta() { return METRIC_META[this.props.name] || { label: this.props.name, icon: "fa-hashtag", cls: "blue" }; }
    get value() { return numberValue(this.props.record.data[this.props.name]); }
    get displayValue() { return this.value ? fmt(this.value) : "\u2014"; }
}

class ReconChunkSummary extends Component {
    static template = xml`
        <div class="rcon-chunks rcon-widget"
             t-att-class="'rcon-chunks--' + state"
             t-att-title="tooltip">
            <div class="rcon-chunks__line">
                <span class="rcon-chunks__icon"><i class="fa fa-puzzle-piece"/></span>
                <strong><t t-esc="fmt(completed)"/> / <t t-esc="fmt(total)"/></strong>
                <small t-esc="label"/>
            </div>
            <div class="rcon-progress"
                 t-if="state !== 'draft'"
                 t-att-class="progressClass">
                <span class="rcon-progress__fill"/>
            </div>
        </div>
    `;
    static props = { name: String, record: Object, readonly: Boolean };

    get total() { return numberValue(this.props.record.data.chunk_count); }
    get completed() { return numberValue(this.props.record.data.completed_chunk_count); }
    get state() { return this.props.record.data.state || ""; }
    get label() { return _t("Chunks"); }
    get tooltip() { return _t("Completed chunks over total chunks"); }
    getProgress() { return this.total ? (100 * this.completed / this.total) : (this.state === "done" ? 100 : 0); }
    get progress() { return this.getProgress(); }
    get progressClass() {
        const color = this.state === "failed" ? "rcon-progress--rose"
            : this.state === "partial" ? "rcon-progress--amber"
            : this.state === "running" ? "rcon-progress--violet"
            : "rcon-progress--emerald";
        return `${color} ${progressBucket(this.getProgress())}`;
    }
    fmt(value) { return fmt(value); }
}

class ReconDateRange extends Component {
    static template = xml`
        <span class="rcon-date-pill rcon-widget" t-att-title="tooltip">
            <i class="fa fa-calendar"/>
            <span t-esc="fromLabel"/>
            <span class="rcon-date-pill__arrow" t-esc="arrow"/>
            <span t-esc="toLabel"/>
        </span>
    `;
    static props = { name: String, record: Object, readonly: Boolean };
    get tooltip() { return _t("Reconciliation date range"); }
    get arrow() { return arrowLabel(); }
    get fromLabel() { return formatDate(this.props.record.data.date_from); }
    get toLabel() { return formatDate(this.props.record.data.date_to); }
}

class ReconCreator extends Component {
    static template = xml`
        <span class="rcon-creator rcon-widget" t-att-title="name">
            <span class="rcon-creator__avatar"><i class="fa fa-user"/></span>
            <span class="rcon-creator__name" t-esc="name || '\u2014'"/>
        </span>
    `;
    static props = { name: String, record: Object, readonly: Boolean };
    get name() { return many2oneLabel(this.props.record.data[this.props.name]); }
}

registry.category("fields").add("list.rcon_job", { component: ReconJobIdentity });
registry.category("fields").add("list.rcon_state", { component: ReconStateBadge });
registry.category("fields").add("list.rcon_scope", { component: ReconBranchScope });
registry.category("fields").add("list.rcon_metric", { component: ReconMetricPill });
registry.category("fields").add("list.rcon_chunks", { component: ReconChunkSummary });
registry.category("fields").add("list.rcon_date_range", { component: ReconDateRange });
registry.category("fields").add("list.rcon_creator", { component: ReconCreator });

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
            const stateBadge = stateCell.querySelector(".rcon-state[data-state]");
            const rawState = (stateBadge?.dataset.state || stateCell.textContent.trim()).toLowerCase();
            row.classList.add(`rcon-row--${rawState}`);
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
            if (!stateBadge) {
                const label = stateMap[rawState] || rawState;
                const meta = getStateMeta(rawState);
                stateCell.innerHTML = `<span class="rcon-state rcon-state--${esc(meta.cls)}" title="${esc(meta.tooltip)}" data-state="${esc(rawState)}"><i class="fa ${esc(meta.icon)}"></i><span>${esc(label)}</span></span>`;
            }
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
            if (cell.querySelector(".rcon-widget")) return;
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
            this.props.record.resModel === "ab_sales_dashboard_reconciliation_job" &&
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
