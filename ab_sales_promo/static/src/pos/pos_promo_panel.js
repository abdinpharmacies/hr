/** @odoo-module **/

import { Component } from "@odoo/owl";

export class AbSalesPosPromoPanel extends Component {
    static template = "ab_sales_promo.PosPromoPanel";
    static props = {
        promo: Object,
        onSelect: Function,
        onClear: Function,
    };

    chipClass(promo) {
        const appliedId = this.props.promo?.applied_id || null;
        const selectedId = this.props.promo?.selected_id || null;
        if (!promo) {
            return "";
        }
        if (promo.id === appliedId) {
            return "is-applied";
        }
        if (promo.id === selectedId) {
            return "is-selected";
        }
        return "";
    }

    statusClass() {
        if (this.props.promo?.applied_id) {
            return "is-active";
        }
        if (this.props.promo?.selected_id) {
            return "is-pending";
        }
        return "is-empty";
    }

    statusLabel() {
        if (this.props.promo?.applied_id) {
            return "Applied";
        }
        if (this.props.promo?.selected_id) {
            return "Needs Qty";
        }
        return "None";
    }

    clearDisabled() {
        return !this.props.promo?.applied_id && !this.props.promo?.selected_id;
    }

    formatQty(value) {
        const num = typeof value === "number" ? value : parseFloat(value ?? 0);
        if (!Number.isFinite(num)) {
            return "0";
        }
        const fixed = num.toFixed(2);
        return fixed.replace(/(?:\.0+|(\.\d*?)0+)$/, "$1");
    }
}
