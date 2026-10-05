/** @odoo-module **/
import { Component, onWillStart, onWillUnmount, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";
import { deserializeDateTime, formatDateTime } from "@web/core/l10n/dates";

function displayTime(value) {
    return value ? formatDateTime(deserializeDateTime(value)) : "";
}

class ExecutionDetails extends Component {
    static template = "ab_queue_monitor.ExecutionDetails";
    static components = { Dialog };
    static props = ["data", "close"];
    setup() { this.action = useService("action"); }
    get title() { return _t("Job Execution"); }
    get metrics() {
        const labels = { total_products: _t("Products"), processed_products: _t("Processed"),
            classified_products: _t("Classified"), needs_review_count: _t("Needs Review"),
            failed_count: _t("Failures"), total_count: _t("Products"), processed_count: _t("Processed") };
        return Object.entries(this.props.data.context?.metrics || {}).map(([key, value]) => ({ key, label: labels[key] || key, value }));
    }
    openContext() {
        const context = this.props.data.context;
        this.props.close();
        this.action.doAction({ type: "ir.actions.act_window", res_model: context.model, res_id: context.id, views: [[false, "form"]], target: "current" });
    }
    openDefinition() {
        this.props.close();
        this.action.doAction({ type: "ir.actions.act_window", res_model: "ab_queue_monitor_definition", res_id: this.props.data.definition.id, views: [[false, "form"]] });
    }
}

export class QueueMonitor extends Component {
    static template = "ab_queue_monitor.Dashboard";
    static props = ["*"];
    setup() {
        this.orm = useService("orm"); this.action = useService("action");
        this.dialog = useService("dialog"); this.notification = useService("notification");
        const params = this.props.action.params || {};
        this.state = useState({ data: null, loading: true, busy: false, error: "", scan: null, offset: 0,
            tab: params.tab || "definitions", filters: { module: params.module || "", definition_id: params.definition_id || false,
                search: "", status: "", runtime_state: "", channel: "", discovery: "", date: "", error: false, active: true } });
        this.alive = true; this.sequence = 0;
        onWillStart(() => this.refresh());
        onWillUnmount(() => { this.alive = false; });
    }
    get kpis() {
        const counts = this.state.data?.kpis || {};
        return [{ key: "modules", label: _t("Modules with Jobs"), icon: "fa-cubes", tone: "neutral" },
            { key: "definitions", label: _t("Job Definitions"), icon: "fa-code", tone: "info" },
            { key: "running", label: _t("Running"), icon: "fa-play-circle", tone: "info" },
            { key: "pending", label: _t("Pending"), icon: "fa-clock-o", tone: "warning" },
            { key: "failed", label: _t("Failed"), icon: "fa-exclamation-circle", tone: "danger" },
            { key: "completed", label: _t("Completed Today"), icon: "fa-check-circle", tone: "success" }
        ].map(item => ({ ...item, value: counts[item.key] || 0 }));
    }
    label(status) { return this.state.data?.statuses.find(s => s.value === status)?.label || status; }
    get runtimeStates() { return [...new Map(Object.values(this.state.data?.runtime_states || {}).flat()).entries()]; }
    async refresh() {
        const sequence = ++this.sequence;
        this.state.loading = true;
        try {
            const data = await this.orm.call("ab_queue_monitor", "dashboard", [], {
                filters: { ...this.state.filters }, offset: this.state.offset, tab: this.state.tab });
            for (const row of data.rows) if (row.created) row.created = displayTime(row.created);
            data.runner.last_activity = displayTime(data.runner.last_activity);
            if (data.session) data.session.started_at = displayTime(data.session.started_at);
            if (this.alive && sequence === this.sequence) { this.state.data = data; this.state.error = ""; }
        } catch (error) {
            if (this.alive) this.state.error = error.data?.message || _t("The monitor could not be refreshed.");
        } finally { if (this.alive && sequence === this.sequence) this.state.loading = false; }
    }
    async filter() { this.state.offset = 0; this.state.filters.definition_id = false; await this.refresh(); }
    async setTab(tab) { this.state.tab = tab; this.state.offset = 0; await this.refresh(); }
    async module(name) { this.state.filters.module = name; await this.filter(); }
    async page(delta) { this.state.offset = Math.max(0, this.state.offset + delta * 40); await this.refresh(); }
    async clear() { Object.assign(this.state.filters, { module: "", definition_id: false, search: "", status: "", runtime_state: "", channel: "", discovery: "", date: "", error: false, active: true }); await this.filter(); }
    async discover() {
        if (this.state.busy) return;
        this.state.busy = true;
        this.pauseRequested = false;
        try {
            this.state.scan = await this.orm.call("ab_queue_monitor_session", "start_scan", []);
            while (this.alive && !this.pauseRequested && this.state.scan.state === "scanning") {
                this.state.scan = await this.orm.call("ab_queue_monitor_session", "scan_step", [[this.state.scan.id]]);
            }
            if (this.alive) await this.refresh();
        } catch (error) {
            this.notification.add(error.data?.message || _t("Discovery paused. Resume to continue."), { type: "warning" });
        } finally { if (this.alive) this.state.busy = false; }
    }
    pause() { this.pauseRequested = true; }
    async cancel() {
        this.state.busy = false;
        const id = this.state.scan?.id || this.state.data.session.id;
        this.state.scan = await this.orm.call("ab_queue_monitor_session", "cancel_scan", [[id]]);
        await this.refresh();
    }
    async open(row) {
        if (this.state.loading) return;
        if (this.state.tab === "definitions") {
            return this.action.doAction({ type: "ir.actions.act_window", res_model: "ab_queue_monitor_definition", res_id: row.id, views: [[false, "form"]] });
        }
        try {
            const data = await this.orm.call("ab_queue_monitor", "execution_details", [row.backend, row.id]);
            for (const field of ["created", "started", "finished"]) data[field] = displayTime(data[field]);
            this.dialog.add(ExecutionDetails, { data });
        } catch (error) { this.notification.add(error.data?.message || _t("Execution details are unavailable."), { type: "warning" }); }
    }
    history() { this.action.doAction("ab_queue_monitor.sessions_action"); }
}
registry.category("actions").add("ab_queue_monitor.dashboard", QueueMonitor);
