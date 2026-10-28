/** @odoo-module **/

import {Component, onWillUnmount, onWillUpdateProps, useState} from "@odoo/owl";
import {registry} from "@web/core/registry";
import {useService} from "@web/core/utils/hooks";
import {_t} from "@web/core/l10n/translation";
import {deserializeDateTime, formatDateTime} from "@web/core/l10n/dates";
import {formatFloat} from "@web/views/fields/formatters";
import {standardFieldProps} from "@web/views/fields/standard_field_props";

export class StoreBalanceRows extends Component {
    static template = "ab_sales.StoreBalanceRows";
    static props = {...standardFieldProps};

    setup() {
        this.orm = useService("orm");
        this.alive = true;
        this.version = 0;
        this.data = this.props.record.data[this.props.name];
        this.state = useState({productId: false, rows: [], search: "", initialError: ""});
        this.setRows(this.data);
        onWillUpdateProps((props) => {
            const data = props.record.data[props.name];
            if (data !== this.data) {
                this.data = data;
                this.setRows(data);
            }
        });
        onWillUnmount(() => { this.alive = false; });
    }

    setRows(data) {
        this.version++;
        this.state.initialError = data?.initial_error || "";
        this.state.productId = data?.product_id || false;
        this.state.rows = (data?.rows || []).map((row) => ({...row, loading: false, error: ""}));
    }

    get visibleRows() {
        const terms = this.state.search.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
        return this.state.rows.filter((row) => {
            const text = `${row.store_name} ${row.store_code || ""}`.toLocaleLowerCase();
            return terms.every((term) => text.includes(term));
        });
    }

    get countLabel() {
        return _t("Showing %(visible)s of %(total)s branches", {
            visible: this.visibleRows.length, total: this.state.rows.length,
        });
    }

    formatBalance(value) {
        return Number.isFinite(value) ? formatFloat(Math.max(0, value), {digits: [16, 2]}) : "—";
    }

    sourceLabel(row) {
        if (row.source === "unavailable") return _t("Unavailable");
        if (row.source === "branch_api") return _t("Branch API");
        if (row.source === "eplus") return _t("E-Plus");
        return _t("Cached balance");
    }

    formattedTime(row) {
        if (!row.refreshed_at) return "";
        try { return formatDateTime(deserializeDateTime(row.refreshed_at)); }
        catch { return ""; }
    }

    async refreshBranch(row) {
        if (!this.alive || row.loading || !row.can_refresh || !this.state.productId) return;
        const productId = this.state.productId;
        const version = this.version;
        const isCurrent = () => this.alive && this.version === version &&
            this.state.productId === productId && this.state.rows.includes(row);
        row.loading = true;
        row.error = "";
        try {
            const result = await this.orm.call("ab_product_balance_wizard", "refresh_branch_balance", [], {
                product_id: productId, store_id: row.store_id,
            });
            if (!isCurrent()) return;
            if (result?.product_id !== productId || result?.store_id !== row.store_id ||
                    !["branch_api", "eplus", "cache"].includes(result.source) || !Number.isFinite(result.balance)) {
                throw new Error(_t("The branch returned invalid stock data."));
            }
            row.balance = result.balance;
            row.cached_fallback = false;
            row.source = result.source;
            row.refreshed_at = result.refreshed_at;
        } catch (error) {
            if (isCurrent()) {
                row.error = error?.data?.message || error?.message || _t("Branch balance refresh failed.");
            }
        } finally {
            if (isCurrent()) row.loading = false;
        }
    }
}

registry.category("fields").add("ab_sales_store_balance_rows", {
    component: StoreBalanceRows,
    supportedTypes: ["json"],
});
