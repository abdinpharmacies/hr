/** @odoo-module **/

import { Component, useState, onMounted, useExternalListener } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { StorePreviewDialog } from "./store_preview_dialog";

const STATE_LABELS = {
    pending: "Pending",
    running: "Running",
    done: "Done",
    failed: "Failed",
    cancelled: "Cancelled",
};

const CHIP_LIMIT = 10;

function fmtDuration(ms) {
    if (!ms || ms <= 0) return "0ms";
    if (ms < 1000) return ms + "ms";
    if (ms < 10000) return (ms / 1000).toFixed(1) + "s";
    return Math.round(ms / 1000) + "s";
}

function formatDate(dateStr) {
    if (!dateStr) return "\u2014";
    const d = new Date(dateStr + "T00:00:00");
    const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    return `${d.getDate()} ${_t(months[d.getMonth()])} ${d.getFullYear()}`;
}

export class ReconciliationChunkDialog extends Component {
    _t = _t;

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.dialogService = useService("dialog");
        this.state = useState({
            loading: true,
            chunk: null,
            stores: [],
            error: null,
            branchSearch: "",
        });
        useExternalListener(window, "mousedown", this._onBackdropClick, { capture: true });
        onMounted(() => {
            this._applyThemeToDialog();
            this._loadChunk();
        });
    }

    get chunkLabel() {
        return `${_t("Chunk")} #${this.state.chunk?.sequence || "?"}`;
    }

    get statusLabel() {
        return _t(STATE_LABELS[this.state.chunk?.state] || "Pending");
    }

    get branchCount() {
        return this.state.stores.length;
    }

    get visibleChips() {
        return this.state.stores.slice(0, CHIP_LIMIT);
    }

    get remainingChipCount() {
        const count = this.state.stores.length - CHIP_LIMIT;
        return count > 0 ? count : 0;
    }

    get filteredStores() {
        const q = this.state.branchSearch.toLowerCase().trim();
        if (!q) return this.state.stores;
        return this.state.stores.filter(
            (s) =>
                (s.name && s.name.toLowerCase().includes(q)) ||
                (s.code && s.code.toLowerCase().includes(q))
        );
    }

    get formattedTotalTime() {
        const c = this.state.chunk;
        if (!c) return "\u2014";
        const total = (c.source_duration_ms || 0) + (c.persistence_duration_ms || 0);
        return total > 0 ? fmtDuration(total) : "\u2014";
    }

    get hasPerformance() {
        const c = this.state.chunk;
        return c && c.state !== "pending";
    }

    get hasError() {
        const c = this.state.chunk;
        return c && c.state === "failed" && c.error_message;
    }

    _applyThemeToDialog() {
        const theme = localStorage.getItem("ab_sales_dashboard.theme") || "dark";
        const dialogRoot = this.el?.closest(".o_dialog");
        if (dialogRoot) {
            dialogRoot.classList.remove("sd-theme-dark", "sd-theme-light");
            dialogRoot.classList.add(theme === "light" ? "sd-theme-light" : "sd-theme-dark");
        }
    }

    _onBackdropClick(ev) {
        const modal = this.el?.closest(".o_dialog");
        if (!modal) return;
        if (ev.target === modal || (modal.contains(ev.target) && !ev.target.closest(".modal-dialog"))) {
            this.props.close();
        }
    }

    onBranchSearch(ev) {
        this.state.branchSearch = ev.target.value;
    }

    clearBranchSearch() {
        this.state.branchSearch = "";
    }

    async _loadChunk() {
        try {
            const [chunk] = await this.orm.read(
                "ab.sales.dashboard.reconciliation.chunk",
                [this.props.chunkId],
                [
                    "sequence", "date_from", "date_to", "store_filter_key",
                    "branch_day_count", "state", "attempt_count",
                    "started_at", "completed_at", "error_message",
                    "source_duration_ms", "persistence_duration_ms", "store_ids",
                ]
            );
            this.state.chunk = chunk;

            if (chunk.store_ids && chunk.store_ids.length) {
                const storeIds = chunk.store_ids.map((s) =>
                    Array.isArray(s) ? s[0] : s
                );
                this.state.stores = await this.orm.read(
                    "ab_store",
                    storeIds,
                    ["code", "name", "eplus_serial"]
                );
            } else {
                this.state.stores = [];
            }
        } catch (e) {
            this.state.error = e.message || "Failed to load chunk data.";
        } finally {
            this.state.loading = false;
        }
    }

    onBranchClick(ev) {
        const row = ev.target.closest(".rcd-table__row");
        if (!row) return;
        const storeId = parseInt(row.dataset.storeId, 10);
        if (!storeId) return;
        this.dialogService.add(StorePreviewDialog, { storeId });
    }

    close() {
        this.props.close();
    }

    fmtDuration(ms) {
        return fmtDuration(ms);
    }

    formatDate(dateStr) {
        return formatDate(dateStr);
    }
}

ReconciliationChunkDialog.components = { Dialog, StorePreviewDialog };
ReconciliationChunkDialog.template = "ab_sales_dashboard.ReconciliationChunkDialog";
