/** @odoo-module **/

import { Component, useState, onMounted, useExternalListener } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { useService } from "@web/core/utils/hooks";

export class StorePreviewDialog extends Component {
    setup() {
        this.orm = useService("orm");
        this.state = useState({
            loading: true,
            store: null,
            error: null,
        });
        useExternalListener(window, "mousedown", this._onBackdropClick, { capture: true });
        onMounted(() => {
            this._applyThemeToDialog();
            this._loadStore();
        });
    }

    get store() {
        return this.state.store;
    }

    get hasIps() {
        return this.state.store?.store_ips?.length;
    }

    get statusCssModifier() {
        return this.state.store?.active ? "active" : "inactive";
    }

    get statusLabel() {
        return this.state.store?.active ? "Active" : "Inactive";
    }

    get storeTypeLabel() {
        const s = this.state.store;
        if (!s || !s.store_type) return "";
        return s.store_type
            .split("_")
            .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
            .join(" ");
    }

    get locationLabel() {
        return this.state.store?.location || "\u2014";
    }

    get telephoneLabel() {
        return this.state.store?.telephone || "\u2014";
    }

    get parentStoreLabel() {
        const s = this.state.store;
        if (!s || !s.parent_id) return "\u2014";
        return s.parent_id[1];
    }

    get maxTransferLabel() {
        const s = this.state.store;
        if (!s || !s.max_trans_value) return "\u2014";
        return s.max_trans_value.toLocaleString() + " EGP";
    }

    get featureFlags() {
        const s = this.state.store;
        if (!s) return [];
        return [
            { key: "allow_purchase", label: "Purchase", cssClass: s.allow_purchase ? "spd-flag--on" : "spd-flag--off" },
            { key: "allow_sale", label: "Sale", cssClass: s.allow_sale ? "spd-flag--on" : "spd-flag--off" },
            { key: "allow_transfer", label: "Transfer", cssClass: s.allow_transfer ? "spd-flag--on" : "spd-flag--off" },
            { key: "allow_replication", label: "Replication", cssClass: s.allow_replication ? "spd-flag--on" : "spd-flag--off" },
        ];
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

    async _loadStore() {
        try {
            const [store] = await this.orm.read(
                "ab_store",
                [this.props.storeId],
                [
                    "name", "code", "status", "store_type", "location", "telephone",
                    "active", "allow_purchase", "allow_sale", "allow_transfer",
                    "allow_replication", "ip1", "ip2", "ip3", "ip4",
                    "parent_id", "last_update_date", "max_trans_value",
                ]
            );
            const ips = [store.ip1, store.ip2, store.ip3, store.ip4].filter(Boolean);
            this.state.store = { ...store, store_ips: ips };
        } catch (e) {
            this.state.error = e.message || "Failed to load store data.";
        } finally {
            this.state.loading = false;
        }
    }

    close() {
        this.props.close();
    }
}

StorePreviewDialog.components = { Dialog };
StorePreviewDialog.template = "ab_sales_dashboard.StorePreviewDialog";
