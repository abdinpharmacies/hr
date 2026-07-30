/** @odoo-module **/

import { Component, onWillStart, useState, useRef, xml } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { money, number, decimal, pct } from "./utils/formatters.js";

const THEME_KEY = "ab_sales_dashboard.theme";

const COLLECTION_LABELS = { cash: _t("Cash"), delivery: _t("Delivery"), contract: _t("Contracts"), offer: _t("Offers") };
const COLLECTION_COLORS = { cash: "emerald", delivery: "blue", contract: "violet", offer: "amber" };
const REPORT_TRANSLATION_TERMS = [
    _t("Collection"),
    _t("Data Source"),
    _t("Generated"),
    _t("Item Name"),
    _t("Sale Times"),
    _t("Snapshot"),
    _t("Sold Qty"),
    _t("Units Sold"),
];
void REPORT_TRANSLATION_TERMS;

// ─── Report Header ───────────────────────────────────────
class ReportHeader extends Component {
    static template = xml`
        <div class="rr-header">
            <div class="rr-header__brand">
                <span class="rr-header__icon"><i class="fa fa-bar-chart"/></span>
                <div class="rr-header__titles">
                    <span class="rr-header__title" t-esc="_t('Sales Performance Report')"/>
                    <span class="rr-header__subtitle" t-esc="_t('Abdin Pharmacies')"/>
                </div>
            </div>
            <div class="rr-header__meta">
                <span class="rr-chip" t-if="props.data">
                    <i class="fa fa-calendar"/>
                    <t t-esc="props.data.date_from"/> — <t t-esc="props.data.date_to"/>
                </span>
                <span class="rr-chip" t-if="props.data &amp;&amp; props.data.store_filter_label">
                    <i class="fa fa-map-marker"/>
                    <t t-esc="props.data.store_filter_label"/>
                </span>
                <span class="rr-chip rr-chip--ok" t-if="props.data &amp;&amp; props.data.has_snapshot">
                    <i class="fa fa-check-circle"/>
                    <t t-esc="_t('Live Data')"/>
                </span>
                <span class="rr-chip rr-chip--warn" t-else="">
                    <i class="fa fa-exclamation-triangle"/>
                    <t t-esc="_t('No Snapshot')"/>
                </span>
            </div>
            <div class="rr-header__actions">
                <button class="rr-btn" t-on-click="props.onRefresh" t-att-disabled="props.loading">
                    <i t-att-class="props.loading ? 'fa fa-spinner fa-spin' : 'fa fa-refresh'"/>
                </button>
                <button class="rr-btn" t-on-click="props.onBack">
                    <i class="fa fa-list"/>
                </button>
            </div>
        </div>
    `;
    _t = _t;
}

// ─── KPI Card ────────────────────────────────────────────
class ReportKpi extends Component {
    static template = xml`
        <div class="rr-kpi" t-att-class="'rr-kpi--' + (props.variant || 'default')">
            <div class="rr-kpi__label" t-esc="props.label"/>
            <div class="rr-kpi__value" t-esc="props.value"/>
            <div class="rr-kpi__sub" t-if="props.sub" t-esc="props.sub"/>
        </div>
    `;
}

// ─── Chapter Tabs ────────────────────────────────────────
class ChapterTabs extends Component {
    static template = xml`
        <nav class="rr-chapters">
            <button class="rr-chapters__tab"
                    t-att-class="{'rr-chapters__tab--active': props.active === 'collection'}"
                    t-on-click="() => props.onSelect('collection')">
                <i class="fa fa-credit-card"/><t t-esc="_t('Collection')"/>
                <span class="rr-chapters__badge" t-if="props.counts.collection" t-esc="props.counts.collection"/>
            </button>
            <button class="rr-chapters__tab"
                    t-att-class="{'rr-chapters__tab--active': props.active === 'users'}"
                    t-on-click="() => props.onSelect('users')">
                <i class="fa fa-users"/><t t-esc="_t('Users')"/>
                <span class="rr-chapters__badge" t-if="props.counts.users" t-esc="props.counts.users"/>
            </button>
            <button class="rr-chapters__tab"
                    t-att-class="{'rr-chapters__tab--active': props.active === 'items'}"
                    t-on-click="() => props.onSelect('items')">
                <i class="fa fa-cube"/><t t-esc="_t('Items')"/>
                <span class="rr-chapters__badge" t-if="props.counts.items" t-esc="props.counts.items"/>
            </button>
            <button class="rr-chapters__tab"
                    t-att-class="{'rr-chapters__tab--active': props.active === 'invoices'}"
                    t-on-click="() => props.onSelect('invoices')">
                <i class="fa fa-file-text-o"/><t t-esc="_t('Invoices')"/>
                <span class="rr-chapters__badge" t-if="props.counts.invoices" t-esc="props.counts.invoices"/>
            </button>
        </nav>
    `;
    _t = _t;
}

// ─── Section Header ──────────────────────────────────────
class SectionHeader extends Component {
    static template = xml`
        <div class="rr-section__head">
            <span class="rr-section__title" t-esc="props.title"/>
            <span class="rr-section__rule"/>
            <span class="rr-section__meta" t-if="props.meta" t-esc="props.meta"/>
        </div>
    `;
}

// ─── Collection Section ──────────────────────────────────
class CollectionSection extends Component {
    static template = xml`
        <SectionHeader title="_t('Collection Analysis')" meta="props.rows.length + ' ' + _t('categories')"/>
        <div class="rr-table-wrap">
            <table class="rr-table">
                <thead><tr>
                    <th t-esc="_t('Category')"/>
                    <th class="rr-table__r" t-esc="_t('Invoices')"/>
                    <th class="rr-table__r" t-esc="_t('Total Sales')"/>
                    <th class="rr-table__r" t-esc="_t('% of Total')"/>
                    <th class="rr-table__bar-h" t-esc="_t('Distribution')"/>
                </tr></thead>
                <tbody>
                    <t t-foreach="props.rows" t-as="row" t-key="row.category">
                        <tr>
                            <td>
                                <span class="rr-badge" t-att-class="'rr-badge--' + (colors[row.category] || 'default')"
                                      t-esc="labels[row.category] || row.category"/>
                            </td>
                            <td class="rr-table__r" t-esc="fmt.num(row.invoice_count)"/>
                            <td class="rr-table__r rr-table__r--bold" t-esc="fmt.money(row.total_sales)"/>
                            <td class="rr-table__r" t-esc="fmt.pct(row.pct_of_total)"/>
                            <td class="rr-table__bar-h">
                                <div class="rr-bar"><div class="rr-bar__fill" t-att-style="'width:' + (row.pct_of_total || 0) + '%'"/></div>
                            </td>
                        </tr>
                    </t>
                    <t t-if="!props.rows.length">
                        <tr><td colspan="5" class="rr-table__empty" t-esc="_t('No collection data available.')"/></tr>
                    </t>
                </tbody>
            </table>
        </div>
    `;
    static components = { SectionHeader };
    labels = COLLECTION_LABELS;
    colors = COLLECTION_COLORS;
    fmt = { num: number, money: money, pct: pct };
    _t = _t;
}

// ─── Users Section ───────────────────────────────────────
class UsersSection extends Component {
    static template = xml`
        <SectionHeader title="_t('Sales by User')" meta="props.rows.length + ' ' + _t('users')"/>
        <div class="rr-table-wrap">
            <table class="rr-table">
                <thead><tr>
                    <th class="rr-table__rank-h">#</th>
                    <th t-esc="_t('User')"/>
                    <th class="rr-table__r" t-esc="_t('Invoices')"/>
                    <th class="rr-table__r" t-esc="_t('Total Sales')"/>
                    <th class="rr-table__r" t-esc="_t('% of Total')"/>
                    <th class="rr-table__bar-h" t-esc="_t('Share')"/>
                </tr></thead>
                <tbody>
                    <t t-foreach="props.rows" t-as="row" t-key="row.employee_name">
                        <tr>
                            <td class="rr-table__rank" t-esc="idx + 1"/>
                            <td class="rr-table__name" t-esc="row.employee_name"/>
                            <td class="rr-table__r" t-esc="fmt.num(row.invoice_count)"/>
                            <td class="rr-table__r rr-table__r--bold" t-esc="fmt.money(row.total_sales)"/>
                            <td class="rr-table__r" t-esc="fmt.pct(row.pct_of_total)"/>
                            <td class="rr-table__bar-h">
                                <div class="rr-bar rr-bar--cyan"><div class="rr-bar__fill" t-att-style="'width:' + (row.pct_of_total || 0) + '%'"/></div>
                            </td>
                        </tr>
                    </t>
                    <t t-if="!props.rows.length">
                        <tr><td colspan="6" class="rr-table__empty" t-esc="_t('No user data available.')"/></tr>
                    </t>
                </tbody>
            </table>
        </div>
    `;
    static components = { SectionHeader };
    fmt = { num: number, money: money, pct: pct };
    _t = _t;
}

// ─── Items Section ───────────────────────────────────────
class ItemsSection extends Component {
    static template = xml`
        <SectionHeader title="_t('Top Sold Items')" meta="props.rows.length + ' ' + _t('items')"/>
        <div class="rr-table-wrap rr-table-wrap--activity">
            <table class="rr-table rr-table--activity">
                <thead><tr>
                    <th class="rr-table__rank-h">#</th>
                    <th t-esc="_t('Code')"/>
                    <th t-esc="_t('Item Name')"/>
                    <th class="rr-table__r" t-esc="_t('Sale Times')"/>
                    <th class="rr-table__r" t-esc="_t('Sold Qty')"/>
                    <th class="rr-table__r" t-esc="_t('Total Sales')"/>
                    <th class="rr-table__r" t-esc="_t('Balance')"/>
                </tr></thead>
                <tbody>
                    <t t-foreach="props.rows" t-as="row" t-key="row_index">
                        <tr>
                            <td class="rr-table__rank" t-esc="idx + 1"/>
                            <td class="rr-table__code" t-esc="row.eplus_item_code"/>
                            <td class="rr-table__name" t-esc="row.item_name"/>
                            <td class="rr-table__r" t-esc="fmt.num(row.sale_times)"/>
                            <td class="rr-table__r" t-esc="fmt.num(row.sold_qty)"/>
                            <td class="rr-table__r rr-table__r--bold" t-esc="fmt.money(row.total_sales)"/>
                            <td class="rr-table__r" t-esc="fmt.num(row.current_balance)"/>
                        </tr>
                    </t>
                    <t t-if="!props.rows.length">
                        <tr><td colspan="7" class="rr-table__empty" t-esc="_t('No item data available.')"/></tr>
                    </t>
                </tbody>
            </table>
        </div>
    `;
    static components = { SectionHeader };
    fmt = { num: number, money: money, pct: pct };
    _t = _t;
}

// ─── Invoices Section ────────────────────────────────────
class InvoicesSection extends Component {
    static template = xml`
        <SectionHeader title="_t('Invoice Details')" meta="props.rows.length + ' ' + _t('invoices')"/>
        <div class="rr-table-wrap">
            <table class="rr-table">
                <thead><tr>
                    <th t-esc="_t('Invoice #')"/>
                    <th t-esc="_t('Date')"/>
                    <th t-esc="_t('Customer')"/>
                    <th class="rr-table__r" t-esc="_t('Total')"/>
                    <th class="rr-table__r" t-esc="_t('Items')"/>
                </tr></thead>
                <tbody>
                    <t t-foreach="props.rows" t-as="row" t-key="row_index">
                        <tr>
                            <td class="rr-table__code" t-esc="row.invoice_no"/>
                            <td class="rr-table__date" t-esc="row.invoice_date"/>
                            <td class="rr-table__name" t-esc="row.customer_name"/>
                            <td class="rr-table__r rr-table__r--bold" t-esc="fmt.money(row.invoice_total)"/>
                            <td class="rr-table__r" t-esc="fmt.num(row.item_count)"/>
                        </tr>
                    </t>
                    <t t-if="!props.rows.length">
                        <tr><td colspan="5" class="rr-table__empty" t-esc="_t('No invoice data available.')"/></tr>
                    </t>
                </tbody>
            </table>
        </div>
    `;
    static components = { SectionHeader };
    fmt = { num: number, money: money };
    _t = _t;
}

// ─── Report Footer ───────────────────────────────────────
class ReportFooter extends Component {
    static template = xml`
        <footer class="rr-footer">
            <div class="rr-footer__col">
                <span class="rr-footer__lbl" t-esc="_t('Data Source')"/>
                <span t-esc="sourceLabel(props.source)"/>
            </div>
            <div class="rr-footer__col rr-footer__col--center">
                <span class="rr-footer__lbl" t-esc="_t('Generated')"/>
                <span t-esc="props.refreshed || _t('N/A')"/>
            </div>
            <div class="rr-footer__col rr-footer__col--right">
                <span class="rr-footer__lbl" t-esc="_t('Snapshot')"/>
                <span t-esc="props.snapshotId || _t('N/A')"/>
            </div>
        </footer>
    `;
    sourceLabel(source) {
        const labels = {
            snapshot: _t("Snapshot"),
            none: _t("No Snapshot"),
        };
        return labels[source] || source || _t("N/A");
    }
    _t = _t;
}

// ─── Main Report Action ──────────────────────────────────
class SalesReportAction extends Component {
    static components = {
        ReportHeader, ReportKpi, ChapterTabs,
        CollectionSection, UsersSection, ItemsSection, InvoicesSection,
        ReportFooter,
    };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.rootRef = useRef("root");
        this.state = useState({
            loading: true,
            data: null,
            chapter: "collection",
            theme: this._loadTheme(),
        });
        onWillStart(() => this._load());
    }

    async _load() {
        const id = this.props.context?.snapshot_id
                || this.props.action?.context?.snapshot_id
                || this.props.active_id;
        if (!id) { this.state.loading = false; return; }
        try {
            this.state.data = await this.orm.call(
                "ab.sales.dashboard.snapshot", "get_report_data", [id],
            );
        } catch {
            this.notification.add(_t("Failed to load report."), { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    _loadTheme() {
        try { return localStorage.getItem(THEME_KEY) === "light" ? "light" : "dark"; }
        catch { return "dark"; }
    }

    async onRefresh() {
        this.state.loading = true;
        await this._load();
    }

    async onBack() {
        try {
            await this.action.loadViews("ab.sales.dashboard.snapshot", { search: 1, list: 1 });
            this.action.doAction({
                type: "ir.actions.act_window",
                res_model: "ab.sales.dashboard.snapshot",
                view_mode: "list",
                target: "current",
            });
        } catch { window.history.back(); }
    }

    get themeClass() {
        return this.state.theme === "dark" ? "sd-theme-dark rr-theme-dark" : "sd-theme-light rr-theme-light";
    }

    get counts() {
        const d = this.state.data;
        if (!d) return {};
        return {
            collection: (d.collection_lines || []).length,
            users: (d.user_lines || []).length,
            items: (d.item_lines || []).length,
            invoices: (d.invoice_lines || []).length,
        };
    }

    f(name) { return money(this.state.data?.[name]); }
    n(name) { return number(this.state.data?.[name]); }
    d(name) { return decimal(this.state.data?.[name]); }
    p(name) { return pct(this.state.data?.[name]); }
    _t = _t;
}

SalesReportAction.template = xml`
<div class="ab-sales-report rr-report" t-ref="root" t-att-class="themeClass">

    <t t-if="state.loading">
        <div class="rr-loading">
            <i class="fa fa-spinner fa-spin fa-3x"/>
            <span t-esc="_t('Loading report...')"/>
        </div>
    </t>

    <t t-elif="!state.data || state.data.error">
        <div class="rr-empty">
            <i class="fa fa-exclamation-triangle fa-3x"/>
            <div class="rr-empty__title" t-esc="_t('No Report Data')"/>
            <div class="rr-empty__text" t-esc="_t('No snapshot found.')"/>
            <button class="rr-btn rr-btn--primary" t-on-click="onBack" t-esc="_t('Back to Reports')"/>
        </div>
    </t>

    <t t-else="">
        <ReportHeader data="state.data" loading="state.loading"
                      onRefresh="() => this.onRefresh()"
                      onBack="() => this.onBack()"/>

        <main class="rr-body">
            <section class="rr-summary">
                <div class="rr-summary__head">
                    <span class="rr-summary__title" t-esc="_t('Executive Summary')"/>
                    <span class="rr-summary__rule"/>
                </div>
                <div class="rr-kpi-grid">
                    <ReportKpi label="_t('Total Sales')" value="f('total_sales')" variant="'primary'"/>
                    <ReportKpi label="_t('Invoices')" value="n('invoice_count')"/>
                    <ReportKpi label="_t('Units Sold')" value="n('total_units_sold')"/>
                    <ReportKpi label="_t('Unique Products')" value="n('unique_products_sold')"/>
                    <ReportKpi label="_t('Avg. Daily Sales')" value="f('avg_daily_sales')"
                               sub="_t('Prev:') + ' ' + f('prev_avg_daily_sales')"/>
                    <ReportKpi label="_t('Growth')" value="p('avg_daily_growth_pct')"
                               sub="_t('vs previous period')"/>
                    <ReportKpi label="_t('Customer Bearing')" value="p('bearing_pct')" variant="'violet'"/>
                    <ReportKpi label="_t('Items / Invoice')" value="d('avg_products_per_invoice')"/>
                    <ReportKpi label="_t('Active Stores')" value="n('stores_with_sales')"/>
                    <ReportKpi label="_t('Product Sales')" value="f('total_product_sales')"/>
                    <ReportKpi label="_t('Products / Store')" value="d('avg_products_sold_per_store')"/>
                </div>
            </section>

            <ChapterTabs active="state.chapter" counts="counts" onSelect="(k) => state.chapter = k"/>

            <section class="rr-chapter" t-if="state.chapter === 'collection'">
                <CollectionSection rows="state.data.collection_lines"/>
            </section>
            <section class="rr-chapter" t-if="state.chapter === 'users'">
                <UsersSection rows="state.data.user_lines"/>
            </section>
            <section class="rr-chapter" t-if="state.chapter === 'items'">
                <ItemsSection rows="state.data.item_lines"/>
            </section>
            <section class="rr-chapter" t-if="state.chapter === 'invoices'">
                <InvoicesSection rows="state.data.invoice_lines"/>
            </section>
        </main>

        <ReportFooter source="state.data.data_source"
                      refreshed="state.data.refresh_date"
                      snapshotId="state.data.snapshot_id"/>
    </t>
</div>
`;

registry.category("actions").add("ab_sales_dashboard.report", SalesReportAction);
