/** @odoo-module **/

import {Component, onWillDestroy, useEffect, useState} from "@odoo/owl";
import {registry} from "@web/core/registry";
import {useService} from "@web/core/utils/hooks";
import {_t} from "@web/core/l10n/translation";
import "@ab_sales/pos/pos_action";

const preparations = new Map();

export function prepareCentralStore(orm, storeId) {
    if (!preparations.has(storeId)) {
        const pending = orm.call("ab_sales_pos_api", "pos_central_prepare", [], {store_id: storeId});
        preparations.set(storeId, pending);
        const release = () => {
            if (preparations.get(storeId) === pending) preparations.delete(storeId);
        };
        pending.then(release, release);
    }
    return preparations.get(storeId);
}

export class BranchCentralStatus extends Component {
    static template = "ab_branch_sync.CentralStatus";
    static props = {
        storeId: Number,
        sessionToken: String,
        requiresLogin: Boolean,
        onSynced: Function,
    };

    setup() {
        this.orm = useService("orm");
        this.state = useState({status: "waiting", message: "", busy: false});
        this.generation = 0;
        this.destroyed = false;
        useEffect(() => {
            const generation = ++this.generation;
            this.state.busy = false;
            this.state.status = "waiting";
            this.state.message = "";
            this.syncIssue = false;
            this.check(true, generation);
            clearInterval(this.syncTimer);
            this.syncTimer = null;
            this.setSyncInterval(10, generation);
            return () => {
                clearInterval(this.syncTimer);
                ++this.generation;
            };
        }, () => [this.props.storeId, this.props.sessionToken, this.props.requiresLogin]);
        onWillDestroy(() => {
            this.destroyed = true;
            clearInterval(this.syncTimer);
            ++this.generation;
        });
    }

    setSyncInterval(seconds, generation = this.generation) {
        const parsed = Number(seconds);
        const interval = Number.isFinite(parsed) && parsed >= 1 && parsed <= 86400 ? parsed : 10;
        if (this.syncTimer && this.intervalSeconds === interval) return;
        clearInterval(this.syncTimer);
        this.intervalSeconds = interval;
        this.syncTimer = setInterval(() => this.check(true, generation), interval * 1000);
    }

    get label() {
        if (!this.props.storeId) return _t("Central: select branch");
        if (this.state.busy) return _t("Central: syncing");
        if (this.props.requiresLogin && !this.props.sessionToken
                && ["online", "waiting"].includes(this.state.status)) return _t("Central: sign in");
        return {
            online: _t("Central: online"),
            offline: _t("Central: offline"),
            attention: _t("Central: needs attention"),
            not_configured: _t("Central: not connected"),
            waiting: _t("Central: checking"),
        }[this.state.status];
    }

    get color() {
        if (this.state.busy || this.state.status === "waiting") return "text-bg-secondary";
        if (this.state.status === "online") return "text-bg-success";
        if (this.state.status === "offline") return "text-bg-warning";
        return "text-bg-danger";
    }

    get title() {
        return this.state.message || _t("Synchronize with central");
    }

    async check(synchronize = true, generation = this.generation) {
        if (this.destroyed || generation !== this.generation || this.inFlight === generation
                || !this.props.storeId) return;
        this.inFlight = generation;
        // Reconnect by installing a fresh snapshot, not merely changing the label.
        synchronize = synchronize || this.state.status === "offline" || this.syncIssue;
        if (synchronize) this.state.busy = true;
        try {
            const storeId = this.props.storeId;
            const preparation = await prepareCentralStore(this.orm, storeId);
            if (this.destroyed || generation !== this.generation) return;
            const needsLogin = this.props.requiresLogin && !this.props.sessionToken;
            const result = !preparation.ready || preparation.synced || needsLogin ? preparation
                : await this.orm.call("ab_sales_pos_api", "pos_central_sync", [], {
                    store_id: storeId,
                    session_token: this.props.sessionToken,
                    synchronize,
                });
            if (this.destroyed || generation !== this.generation) return;
            this.setSyncInterval(result.interval_seconds, generation);
            this.state.status = result.state;
            this.state.message = result.message;
            if (synchronize) this.syncIssue = !result.synced;
            if (result.synced) this.props.onSynced();
        } catch (error) {
            if (this.destroyed || generation !== this.generation) return;
            this.state.status = "attention";
            this.syncIssue = true;
            this.state.message = _t("Connection status could not be checked. Retry synchronization.");
        } finally {
            if (!this.destroyed && generation === this.generation) this.state.busy = false;
            if (this.inFlight === generation) this.inFlight = null;
        }
    }

    synchronize() {
        return this.check(true);
    }
}

const PosAction = registry.category("actions").get("ab_sales.pos");

export class BranchSyncPosAction extends PosAction {
    static components = {...PosAction.components, BranchCentralStatus};

    async abBranchSyncPrepareSelection(storeId, generation) {
        try {
            const result = await prepareCentralStore(this.orm, storeId);
            if (this._balanceRefreshUnmounted || generation !== this._abBranchSelectionGeneration) return false;
            if (!result.ready) this.notification.add(result.message, {type: "warning"});
            return result.ready;
        } catch {
            if (!this._balanceRefreshUnmounted && generation === this._abBranchSelectionGeneration) {
                this.notification.add(_t("Connection status could not be checked. Retry synchronization."), {type: "warning"});
            }
            return false;
        }
    }

    async createNewBill(storeId) {
        const generation = this._abBranchSelectionGeneration = (this._abBranchSelectionGeneration || 0) + 1;
        if (storeId && !await this.abBranchSyncPrepareSelection(storeId, generation)) return false;
        return super.createNewBill(...arguments);
    }

    async onStoreM2OUpdate(value) {
        const generation = this._abBranchSelectionGeneration = (this._abBranchSelectionGeneration || 0) + 1;
        const bill = this.currentBill;
        if (value?.id && !await this.abBranchSyncPrepareSelection(value.id, generation)) return;
        if (this.currentBill !== bill) return;
        return super.onStoreM2OUpdate(...arguments);
    }

    async loadCache() {
        const result = await super.loadCache(...arguments);
        const storeId = this.currentBill?.header?.store_id || this.state.abSalesHr?.selectedStoreId;
        if (storeId) {
            // Restored drafts need the same preparation before mounted stock
            // reads. The status component displays failures and offers retry.
            try { await prepareCentralStore(this.orm, storeId); } catch { /* Status handles failures. */ }
        }
        return result;
    }

    abBranchSyncRefreshBalances() {
        this.scheduleLinePosBalanceRefresh(this.currentBill);
        // Update displayed availability without changing draft quantities or prices.
        this._refreshPosBalancesForResults(this.state.productResults,
            this.currentBill?.header?.store_id, this._posBalanceRequestId);
    }
}

registry.category("actions").add("ab_sales.pos", BranchSyncPosAction, {force: true});
