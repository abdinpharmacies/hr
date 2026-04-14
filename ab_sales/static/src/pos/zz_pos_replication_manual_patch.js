/** @odoo-module **/

import {Component, onWillStart, useState} from "@odoo/owl";
import {Dialog} from "@web/core/dialog/dialog";
import {registry} from "@web/core/registry";
import {patch} from "@web/core/utils/patch";

function getRpcErrorMessage(err, fallback = "Failed to trigger cron.") {
    if (!err) {
        return fallback;
    }
    const data = err.data || err?.response?.data || {};
    const rpcArgs = data?.["arguments"];
    return (
        data?.message ||
        (Array.isArray(rpcArgs) && rpcArgs[0]) ||
        err.message ||
        fallback
    );
}

class AbSalesPosReplicationDialog extends Component {
    static template = "ab_sales.PosReplicationDialog";
    static components = {Dialog};
    static props = {
        loadCrons: Function,
        runCron: Function,
        close: Function,
    };

    setup() {
        this.state = useState({
            loading: true,
            running: false,
            crons: [],
            selectedCronId: 0,
            message: "",
        });
        this.loadCrons = this.loadCrons.bind(this);
        this.selectCron = this.selectCron.bind(this);
        this.runSelected = this.runSelected.bind(this);
        this.close = this.close.bind(this);

        onWillStart(async () => {
            await this.loadCrons();
        });
    }

    get selectedCron() {
        return (this.state.crons || []).find((row) => row.id === this.state.selectedCronId) || null;
    }

    async loadCrons() {
        this.state.loading = true;
        this.state.message = "";
        try {
            const rows = await this.props.loadCrons();
            this.state.crons = Array.isArray(rows) ? rows : [];
            if (!this.state.selectedCronId || !this.selectedCron) {
                this.state.selectedCronId = this.state.crons.length ? this.state.crons[0].id : 0;
            }
        } finally {
            this.state.loading = false;
        }
    }

    selectCron(cronId) {
        this.state.selectedCronId = parseInt(cronId || 0, 10) || 0;
        this.state.message = "";
    }

    async runSelected() {
        if (this.state.running || !this.state.selectedCronId) {
            return;
        }
        this.state.running = true;
        this.state.message = "";
        try {
            await this.props.runCron(this.state.selectedCronId);
            this.props.close();
        } catch (err) {
            this.state.message = getRpcErrorMessage(err, "Failed to trigger cron.");
        } finally {
            this.state.running = false;
        }
    }

    close() {
        this.props.close();
    }
}

const PosAction = registry.category("actions").get("ab_sales.pos");

if (PosAction) {
    patch(PosAction.prototype, {
        setup() {
            super.setup(...arguments);
            this.openReplicationDialog = this.openReplicationDialog.bind(this);
            this._loadReplicationCrons = this._loadReplicationCrons.bind(this);
            this._runReplicationCron = this._runReplicationCron.bind(this);
        },

        async _loadReplicationCrons() {
            return await this.orm.call("ab_sales_ui_api", "pos_replication_active_crons", [], {});
        },

        async _runReplicationCron(cronId) {
            const result = await this.orm.call("ab_sales_ui_api", "pos_replication_run_cron", [], {
                cron_id: cronId,
            });
            this.notification.add(result?.message || "Cron has been triggered.", {type: "success"});
            return result;
        },

        openReplicationDialog() {
            this.dialog.add(AbSalesPosReplicationDialog, {
                loadCrons: this._loadReplicationCrons,
                runCron: this._runReplicationCron,
            });
        },
    });
}
