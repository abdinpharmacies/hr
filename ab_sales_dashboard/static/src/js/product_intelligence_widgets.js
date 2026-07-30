/** @odoo-module **/

import { Component, xml } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

function fmt(v) {
    if (!v && v !== 0) return "0";
    return new Intl.NumberFormat("en-US").format(Math.round(v));
}

function fmtMoney(v) {
    const n = Number(v || 0);
    return new Intl.NumberFormat("en-US", {
        style: "currency",
        currency: "EGP",
        minimumFractionDigits: 0,
        maximumFractionDigits: 0,
    }).format(n);
}

function computeStatus(data) {
    const sales = Number(data.total_sales || 0);
    const qty = Number(data.units_sold || 0);
    const inv = Number(data.invoice_count || 0);
    if (sales >= 100000) return { label: _t("Best Seller"), clr: "emerald", icon: "fa-trophy" };
    if (sales >= 50000) return { label: _t("Top Seller"), clr: "emerald", icon: "fa-star" };
    if (qty >= 500) return { label: _t("Fast Moving"), clr: "blue", icon: "fa-bolt" };
    if (inv >= 100) return { label: _t("Popular"), clr: "violet", icon: "fa-heart" };
    if (sales >= 10000) return { label: _t("High Revenue"), clr: "cyan", icon: "fa-line-chart" };
    if (sales < 500) return { label: _t("Low Demand"), clr: "amber", icon: "fa-arrow-down" };
    return { label: _t("Active"), clr: "default", icon: "fa-circle" };
}

// ══════════════════════════════════════════════════════════════
// PRODUCT IDENTITY — Name + Code + Status badge
// ══════════════════════════════════════════════════════════════
class ProductIdentity extends Component {
    static template = xml`
        <div class="psi-identity">
            <div class="psi-identity__icon" t-att-class="'psi-identity__icon--' + itemType">
                <i class="fa" t-att-class="typeIcon"/>
            </div>
            <div class="psi-identity__body">
                <span class="psi-identity__name" t-esc="productName"/>
                <span class="psi-identity__code" t-esc="itemCode"/>
            </div>
            <span class="psi-identity__status" t-att-class="'psi-identity__status--' + status.clr">
                <i class="fa" t-att-class="status.icon"/>
                <t t-esc="status.label"/>
            </span>
        </div>
    `;
    static props = { name: String, record: Object, readonly: Boolean };

    get productName() { return this.props.record.data.product_name || _t("Unknown"); }
    get itemCode() { return this.props.record.data.item_code || ""; }
    get itemType() {
        const raw = (this.props.record.data.item_type || "").toLowerCase();
        return raw === "medicine" ? "medicine" : "general";
    }
    get typeIcon() {
        return this.itemType === "medicine" ? "fa-medkit" : "fa-cube";
    }
    get status() { return computeStatus(this.props.record.data); }
}

registry.category("fields").add("list.ps_identity", { component: ProductIdentity });

// ══════════════════════════════════════════════════════════════
// PRODUCT NAME — Simple bold name fallback
// ══════════════════════════════════════════════════════════════
class ProductName extends Component {
    static template = xml`
        <span class="psi-field-name" t-esc="value"/>
    `;
    static props = { name: String, record: Object, readonly: Boolean };
    get value() { return this.props.record.data[this.props.name] || ""; }
}

registry.category("fields").add("list.ps_name", { component: ProductName });

// ══════════════════════════════════════════════════════════════
// ITEM TYPE — Category badge
// ══════════════════════════════════════════════════════════════
class ProductItemType extends Component {
    static template = xml`
        <span class="psi-type" t-att-class="'psi-type--' + typeCls">
            <i class="fa" t-att-class="typeIcon"/>
            <t t-esc="label"/>
        </span>
    `;
    static props = { name: String, record: Object, readonly: Boolean };

    get label() {
        const v = this.props.record.data[this.props.name];
        if (!v) return _t("General");
        return String(v).replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
    }
    get typeCls() {
        const v = String(this.props.record.data[this.props.name] || "").toLowerCase();
        if (v === "medicine") return "medicine";
        return "general";
    }
    get typeIcon() {
        return this.typeCls === "medicine" ? "fa-medkit" : "fa-cube";
    }
}

registry.category("fields").add("list.ps_type", { component: ProductItemType });

// ══════════════════════════════════════════════════════════════
// REVENUE — Currency value with accent
// ══════════════════════════════════════════════════════════════
class ProductRevenue extends Component {
    static template = xml`
        <span class="psi-revenue" t-att-class="revenueCls" t-esc="formatted"/>
    `;
    static props = { name: String, record: Object, readonly: Boolean };

    get raw() { return Number(this.props.record.data[this.props.name] || 0); }
    get formatted() { return fmtMoney(this.raw); }
    get revenueCls() {
        if (this.raw >= 100000) return "psi-revenue--high";
        if (this.raw >= 10000) return "psi-revenue--mid";
        if (this.raw >= 1000) return "psi-revenue--low";
        return "";
    }
}

registry.category("fields").add("list.ps_revenue", { component: ProductRevenue });

// ══════════════════════════════════════════════════════════════
// AVERAGE PRICE — Muted currency
// ══════════════════════════════════════════════════════════════
class ProductAvgPrice extends Component {
    static template = xml`
        <span class="psi-avg-price" t-esc="formatted"/>
    `;
    static props = { name: String, record: Object, readonly: Boolean };
    get formatted() { return fmtMoney(this.props.record.data[this.props.name]); }
}

registry.category("fields").add("list.ps_avg_price", { component: ProductAvgPrice });

// ══════════════════════════════════════════════════════════════
// METRIC — Number with icon chip
// ══════════════════════════════════════════════════════════════
const METRIC_ICONS = {
    units_sold: "fa-shopping-cart",
    invoice_count: "fa-file-text-o",
    branches_sold_in: "fa-building-o",
    sale_times: "fa-bolt",
};

class ProductMetric extends Component {
    static template = xml`
        <span class="psi-chip">
            <i class="fa" t-att-class="chipIcon"/>
            <t t-esc="formatted"/>
        </span>
    `;
    static props = { name: String, record: Object, readonly: Boolean };

    get raw() { return Number(this.props.record.data[this.props.name] || 0); }
    get formatted() { return fmt(this.raw); }
    get chipIcon() { return METRIC_ICONS[this.props.name] || "fa-hashtag"; }
}

registry.category("fields").add("list.ps_metric", { component: ProductMetric });

// ══════════════════════════════════════════════════════════════
// DATE — Formatted date with icon
// ══════════════════════════════════════════════════════════════
class ProductDate extends Component {
    static template = xml`
        <span class="psi-date">
            <i class="fa fa-calendar psi-date__icon"/>
            <t t-esc="formatted"/>
        </span>
    `;
    static props = { name: String, record: Object, readonly: Boolean };

    get formatted() {
        const raw = this.props.record.data[this.props.name];
        if (!raw) return "";
        try {
            const d = new Date(raw);
            return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
        } catch { return String(raw); }
    }
}

registry.category("fields").add("list.ps_date", { component: ProductDate });

// ══════════════════════════════════════════════════════════════
// STORE — Store name chip
// ══════════════════════════════════════════════════════════════
class ProductStore extends Component {
    static template = xml`
        <span class="psi-chip psi-chip--store">
            <i class="fa fa-building-o"/>
            <t t-esc="display"/>
        </span>
    `;
    static props = { name: String, record: Object, readonly: Boolean };

    get display() {
        const raw = this.props.record.data[this.props.name];
        if (!raw) return "";
        if (typeof raw === "object" && raw !== null) {
            return raw.display_name || raw.name || raw[1] || "";
        }
        return String(raw);
    }
}

registry.category("fields").add("list.ps_store", { component: ProductStore });

// ══════════════════════════════════════════════════════════════
// ITEM CODE — SKU badge
// ══════════════════════════════════════════════════════════════
class ProductSku extends Component {
    static template = xml`
        <span class="psi-sku" t-esc="value"/>
    `;
    static props = { name: String, record: Object, readonly: Boolean };
    get value() { return this.props.record.data[this.props.name] || ""; }
}

registry.category("fields").add("list.ps_sku", { component: ProductSku });
