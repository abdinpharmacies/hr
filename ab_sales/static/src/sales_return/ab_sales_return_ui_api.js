/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillDestroy, onWillStart, useExternalListener, useState } from "@odoo/owl";

class AbSalesReturnUiApiAction extends Component {
    static template = "ab_sales.AbSalesReturnUiApiAction";
    static target = "new";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        this._recordRevisions = new WeakMap();
        const rawCall = this.orm.call.bind(this.orm);
        this.orm.call = async (model, method, args = [], kwargs = {}) => {
            if (model !== "ab_sales_return_ui_api" || method !== "get_state") {
                return rawCall(model, method, args, kwargs);
            }
            const revision = this._revision || 0;
            this.state.checking = true;
            const record = await rawCall(model, method, args, kwargs);
            if (record && typeof record === "object") this._recordRevisions.set(record, revision);
            return record;
        };

        this.returnHeaderId =
            this.props?.action?.params?.return_header_id ||
            this.props?.action?.context?.active_id ||
            null;

        this.state = useState({
            loading: true,
            busy: false,
            savingNotes: false,
            checking: false,
            record: null,
            notesDraft: "",
        });
        this._abandonRequested = false;
        this._destroyCleanupStarted = false;

        this.load = this.load.bind(this);
        this.close = this.close.bind(this);
        this.saveNotes = this.saveNotes.bind(this);
        this.reloadLines = this.reloadLines.bind(this);
        this.clearLines = this.clearLines.bind(this);
        this.totalReturnInvoice = this.totalReturnInvoice.bind(this);
        this.setPending = this.setPending.bind(this);
        this.pushToEplus = this.pushToEplus.bind(this);
        this.onQtyInput = this.onQtyInput.bind(this);
        this.onQtyBlur = this.onQtyBlur.bind(this);
        this.onQtyKeydown = this.onQtyKeydown.bind(this);
        this.onUomChange = this.onUomChange.bind(this);

        useExternalListener(window, "focus", () => { if (!this.state.busy) this.load(); });

        onWillStart(async () => {
            await this.load();
        });

        onWillDestroy(() => {
            this._abandonOnDestroy();
        });
    }

    get lines() {
        return this.state.record?.lines || [];
    }

    formatNumber(value, digits = 2) {
        const num = Number(value || 0);
        return Number.isFinite(num) ? num.toFixed(digits) : "0.00";
    }

    _messageFromError(error, fallback) {
        return (
            error?.data?.message ||
            error?.data?.arguments?.[0] ||
            error?.message ||
            fallback
        );
    }

    _applyRecord(record) {
        const revision = this._recordRevisions?.get(record);
        if (revision !== undefined && revision !== (this._revision || 0)) return;
        this.state.checking = false;
        this.state.record = record || null;
        this.state.notesDraft = record?.notes || "";
        this.returnHeaderId = record?.id || this.returnHeaderId;
    }

    async load() {
        const revision = this._revision || 0;
        this.state.checking = true;
        this.state.loading = !this.state.record;
        try {
            const record = await this.orm.call("ab_sales_return_ui_api", "get_state", [], {
                return_header_id: this.returnHeaderId,
            });
            if (revision === (this._revision || 0)) {
                this._applyRecord(record);
                this.state.checking = false;
            }
        } catch (error) {
            this.notification.add(this._messageFromError(error, "Failed to load sales return."), {
                type: "danger",
            });
        } finally {
            this.state.loading = false;
        }
    }

    async close() {
        await this._abandonReturn();
        await this.action.doAction({ type: "ir.actions.act_window_close" });
    }

    _shouldAbandonReturn() {
        return Boolean(
            this.returnHeaderId &&
            this.state.record &&
            this.state.record.status === "prepending" &&
            !this.state.record.submission_attempted && !this.state.busy && !this.state.checking
        );
    }

    async _abandonReturn() {
        if (!this._shouldAbandonReturn() || this._abandonRequested) {
            return;
        }
        this._abandonRequested = true;
        try {
            await this.orm.call("ab_sales_return_ui_api", "abandon_return", [], {
                return_header_id: this.returnHeaderId,
            });
        } catch {
            this._abandonRequested = false;
        }
    }

    _abandonOnDestroy() {
        if (!this._shouldAbandonReturn() || this._destroyCleanupStarted || this._abandonRequested) {
            return;
        }
        this._destroyCleanupStarted = true;
        this._abandonRequested = true;
        Promise.resolve(
            this.orm.call("ab_sales_return_ui_api", "abandon_return", [], {
                return_header_id: this.returnHeaderId,
            })
        ).catch(() => {});
    }

    get editable() {
        return !!this.state.record?.can_edit && !this.state.busy && !this.state.checking;
    }

    async _runAction(method, fallbackMessage, params = {}, successMessage = "") {
        if (this.state.busy) {
            return;
        }
        this._revision = (this._revision || 0) + 1;
        this.state.busy = true;
        try {
            const record = await this.orm.call("ab_sales_return_ui_api", method, [], {
                return_header_id: this.returnHeaderId,
                ...params,
            });
            this._applyRecord(record);
            if (method === "push_to_eplus" && record?.status !== "saved") {
                this.notification.add(record?.push_message || _t("Return submission needs attention. Use Retry."), {type: "warning"});
            } else if (successMessage) {
                this.notification.add(successMessage, { type: "success" });
            }
        } catch (error) {
            this.notification.add(this._messageFromError(error, fallbackMessage), {
                type: "danger",
            });
            await this.load();
        } finally {
            this.state.busy = false;
        }
    }

    async saveNotes() {
        if (!this.editable || this.state.savingNotes) {
            return;
        }
        this._revision = (this._revision || 0) + 1;
        this.state.savingNotes = true;
        this.state.busy = true;
        try {
            const record = await this.orm.call("ab_sales_return_ui_api", "save_notes", [], {
                return_header_id: this.returnHeaderId,
                notes: this.state.notesDraft || "",
            });
            this._applyRecord(record);
            this.notification.add("Notes saved.", { type: "success" });
        } catch (error) {
            this.notification.add(this._messageFromError(error, "Failed to save notes."), {
                type: "danger",
            });
        } finally {
            this.state.savingNotes = false;
            this.state.busy = false;
        }
    }

    async reloadLines() {
        if (!this.editable) return;
        await this._runAction("reload_lines", "Failed to load lines.", {}, "Lines loaded.");
    }

    async clearLines() {
        if (!this.editable) return;
        await this._runAction("clear_lines", "Failed to clear lines.", {}, "Lines cleared.");
    }

    async totalReturnInvoice() {
        if (!this.editable) return;
        await this._runAction(
            "total_return_invoice",
            "Failed to mark invoice as total return.",
            {},
            "Invoice marked as total return."
        );
    }

    async setPending() {
        if (!this.editable) return;
        await this._runAction("set_pending", "Failed to set return pending.", {}, "Return moved to pending.");
    }

    async pushToEplus() {
        if (this.state.checking) {
            await this.load();
            if (this.state.checking) return;
        }
        await this._runAction("push_to_eplus", "Failed to push return to E-Plus.", {}, "Return pushed to E-Plus.");
    }

    _findLine(lineId) {
        return this.lines.find((line) => line.id === lineId) || null;
    }

    onQtyInput(lineId, ev) {
        if (!this.editable) return;
        const line = this._findLine(lineId);
        if (line) {
            line.qty_str = ev.target.value;
        }
    }

    async _saveLine(lineId, extra = {}) {
        if (!this.editable) return;
        const line = this._findLine(lineId);
        if (!line) {
            return;
        }
        if (this.state.busy) {
            return;
        }
        this.state.busy = true;
        try {
            const record = await this.orm.call("ab_sales_return_ui_api", "update_line", [], {
                return_header_id: this.returnHeaderId,
                line_id: lineId,
                qty_str: line.qty_str || "0",
                uom_id: extra.uom_id !== undefined ? extra.uom_id : false,
            });
            this._applyRecord(record);
        } catch (error) {
            this.notification.add(this._messageFromError(error, "Failed to update line."), {
                type: "danger",
            });
            await this.load();
        } finally {
            this.state.busy = false;
        }
    }

    async onQtyBlur(lineId) {
        await this._saveLine(lineId);
    }

    async onQtyKeydown(lineId, ev) {
        if (ev.key !== "Enter") {
            return;
        }
        ev.preventDefault();
        await this._saveLine(lineId);
    }

    async onUomChange(lineId, ev) {
        if (!this.editable) return;
        const uomId = Number.parseInt(ev.target.value, 10) || false;
        const line = this._findLine(lineId);
        if (!line) {
            return;
        }
        line.uom_id = uomId;
        await this._saveLine(lineId, { uom_id: uomId });
    }
}

registry.category("actions").add("ab_sales.return_ui", AbSalesReturnUiApiAction);
