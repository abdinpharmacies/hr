/** @odoo-module **/

import { Component, onWillStart, useState, xml } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

const COLLECTION_LABELS = {
    cash: _t("Cash"),
    delivery: _t("Delivery"),
    contract: _t("Contracts"),
    offer: _t("Offers"),
};

class SalesDashboardAction extends Component {
    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.updateFilter = this.updateFilter.bind(this);
        this.onApplyFilters = this.onApplyFilters.bind(this);
        this.onRefresh = this.onRefresh.bind(this);
        this.state = useState({
            loading: true,
            refreshing: false,
            filters: {
                date_from: "",
                date_to: "",
                store_id: 0,
            },
            data: null,
        });
        onWillStart(async () => this.loadDashboard(false));
    }

    async loadDashboard(refresh) {
        this.state.loading = true;
        if (refresh) {
            this.state.refreshing = true;
        }
        try {
            const method = refresh ? "refresh_dashboard_data" : "get_dashboard_data";
            const data = await this.orm.call("ab.sales.dashboard.snapshot", method, [this.state.filters]);
            this.state.data = data;
            this.state.filters.date_from = data.date_from;
            this.state.filters.date_to = data.date_to;
            this.state.filters.store_id = data.store_id || 0;
            if (refresh) {
                this.notification.add(_t("Sales dashboard refreshed."), { type: "success" });
            }
        } finally {
            this.state.loading = false;
            this.state.refreshing = false;
        }
    }

    updateFilter(name, value) {
        this.state.filters[name] = name === "store_id" ? Number(value || 0) : value;
    }

    async onApplyFilters() {
        await this.loadDashboard(false);
    }

    async onRefresh() {
        await this.loadDashboard(true);
    }

    money(value) {
        return new Intl.NumberFormat("ar-EG", {
            style: "currency",
            currency: "EGP",
            maximumFractionDigits: 0,
        }).format(Number(value || 0));
    }

    number(value) {
        return new Intl.NumberFormat("ar-EG", { maximumFractionDigits: 0 }).format(Number(value || 0));
    }

    decimal(value) {
        return new Intl.NumberFormat("ar-EG", { maximumFractionDigits: 2 }).format(Number(value || 0));
    }

    pct(value) {
        return `${this.decimal(value)}%`;
    }

    abs(value) {
        return Math.abs(Number(value || 0));
    }

    collectionLabel(category) {
        return COLLECTION_LABELS[category] || category;
    }

    get medicineTotal() {
        const data = this.state.data || {};
        return Number(data.medicine_sales || 0) + Number(data.non_medicine_sales || 0);
    }

    get medicinePct() {
        return this.medicineTotal ? (100 * Number(this.state.data.medicine_sales || 0)) / this.medicineTotal : 0;
    }

    get nonMedicinePct() {
        return this.medicineTotal ? (100 * Number(this.state.data.non_medicine_sales || 0)) / this.medicineTotal : 0;
    }
}

SalesDashboardAction.template = xml`
<div class="ab_sales_dashboard" dir="rtl">
    <div class="ab_sales_dashboard__toolbar">
        <div>
            <h1>داشبورد المبيعات</h1>
            <p>صيدليات عابدين - نظرة شاملة على أداء المبيعات</p>
        </div>
        <div class="ab_sales_dashboard__filters">
            <input type="date"
                   t-att-value="state.filters.date_from"
                   t-on-change="(ev) => updateFilter('date_from', ev.target.value)"/>
            <input type="date"
                   t-att-value="state.filters.date_to"
                   t-on-change="(ev) => updateFilter('date_to', ev.target.value)"/>
            <select t-att-value="state.filters.store_id" t-on-change="(ev) => updateFilter('store_id', ev.target.value)">
                <option value="0">كل الفروع</option>
                <t t-foreach="(state.data &amp;&amp; state.data.stores) || []" t-as="store" t-key="store.id">
                    <option t-att-value="store.id" t-esc="store.name"/>
                </t>
            </select>
            <button type="button" class="btn btn-secondary" t-on-click="onApplyFilters" t-att-disabled="state.loading">تطبيق</button>
            <button type="button" class="btn btn-primary" t-on-click="onRefresh" t-att-disabled="state.refreshing">
                <t t-if="state.refreshing">جاري التحديث...</t>
                <t t-else="">تحديث من E-Plus</t>
            </button>
        </div>
    </div>

    <t t-if="state.loading &amp;&amp; !state.data">
        <div class="ab_sales_dashboard__empty">جاري تحميل الداشبورد...</div>
    </t>
    <t t-elif="state.data">
        <div t-if="!state.data.has_snapshot" class="ab_sales_dashboard__notice">
            لا توجد لقطة محفوظة لهذه الفلاتر. اضغط "تحديث من E-Plus" لجلب البيانات.
        </div>

        <section class="ab_sales_dashboard__kpis">
            <article class="ab_sales_dashboard__kpi ab_sales_dashboard__kpi--wide">
                <span>إجمالي المبيعات</span>
                <strong t-esc="money(state.data.total_sales)"/>
                <em>
                    <t t-if="state.data.avg_daily_growth_pct &gt;= 0">▲</t>
                    <t t-else="">▼</t>
                    <t t-esc="pct(abs(state.data.avg_daily_growth_pct))"/>
                    عن متوسط الفترة السابقة
                </em>
            </article>
            <article class="ab_sales_dashboard__kpi">
                <span>متوسط المبيعات اليومي</span>
                <strong t-esc="money(state.data.avg_daily_sales)"/>
                <em>السابق: <t t-esc="money(state.data.prev_avg_daily_sales)"/></em>
            </article>
            <article class="ab_sales_dashboard__kpi">
                <span>إجمالي الفواتير</span>
                <strong t-esc="number(state.data.invoice_count)"/>
                <em t-esc="state.data.store_filter_label"/>
            </article>
            <article class="ab_sales_dashboard__kpi">
                <span>نسبة التحمل</span>
                <strong t-esc="pct(state.data.bearing_pct)"/>
                <em>الشركة: <t t-esc="money(state.data.company_part_amount)"/></em>
            </article>
        </section>

        <section class="ab_sales_dashboard__split">
            <article class="ab_sales_dashboard__panel">
                <div class="ab_sales_dashboard__panel_header">
                    <h2>دواء مقابل غير دواء</h2>
                    <span><t t-esc="decimal(medicinePct)"/> / <t t-esc="decimal(nonMedicinePct)"/></span>
                </div>
                <div class="ab_sales_dashboard__ratio">
                    <div class="ab_sales_dashboard__ratio_bar">
                        <span t-att-style="'width:' + medicinePct + '%'"/>
                    </div>
                    <div class="ab_sales_dashboard__ratio_values">
                        <div>
                            <span>مبيعات الدواء</span>
                            <strong t-esc="money(state.data.medicine_sales)"/>
                            <em><t t-esc="pct(medicinePct)"/> من الإجمالي</em>
                        </div>
                        <div>
                            <span>مبيعات غير الدواء</span>
                            <strong t-esc="money(state.data.non_medicine_sales)"/>
                            <em><t t-esc="pct(nonMedicinePct)"/> من الإجمالي</em>
                        </div>
                    </div>
                </div>
            </article>
            <article class="ab_sales_dashboard__panel">
                <div class="ab_sales_dashboard__panel_header">
                    <h2>توزيع المبيعات حسب طريقة التحصيل</h2>
                    <span>٤ فئات</span>
                </div>
                <div class="ab_sales_dashboard__collection">
                    <t t-foreach="state.data.collection_lines" t-as="line" t-key="line.category">
                        <div class="ab_sales_dashboard__collection_card">
                            <span t-esc="collectionLabel(line.category)"/>
                            <strong t-esc="money(line.total_sales)"/>
                            <em><t t-esc="pct(line.pct_of_total)"/> من الإجمالي</em>
                        </div>
                    </t>
                </div>
            </article>
        </section>

        <section class="ab_sales_dashboard__tables">
            <article class="ab_sales_dashboard__panel">
                <div class="ab_sales_dashboard__panel_header">
                    <h2>مبيعات المستخدمين</h2>
                    <span>مرتبة تنازليا</span>
                </div>
                <table>
                    <thead>
                        <tr><th>#</th><th>المستخدم</th><th>إجمالي المبيعات</th><th>النسبة</th></tr>
                    </thead>
                    <tbody>
                        <t t-foreach="state.data.user_lines" t-as="line" t-key="line.employee_eplus_id || line.employee_name">
                            <tr>
                                <td t-esc="line_index + 1"/>
                                <td t-esc="line.employee_name"/>
                                <td t-esc="money(line.total_sales)"/>
                                <td t-esc="pct(line.pct_of_total)"/>
                            </tr>
                        </t>
                    </tbody>
                </table>
            </article>

            <article class="ab_sales_dashboard__panel">
                <div class="ab_sales_dashboard__panel_header">
                    <h2>مبيعات الأصناف</h2>
                    <span>عدد مرات البيع + الرصيد الحالي</span>
                </div>
                <table>
                    <thead>
                        <tr><th>#</th><th>الصنف</th><th>عدد مرات البيع</th><th>الرصيد الحالي</th></tr>
                    </thead>
                    <tbody>
                        <t t-foreach="state.data.item_lines" t-as="line" t-key="line.eplus_item_id">
                            <tr>
                                <td t-esc="line_index + 1"/>
                                <td>
                                    <strong t-esc="line.product_name"/>
                                    <small t-esc="line.eplus_item_code"/>
                                </td>
                                <td t-esc="number(line.sale_times)"/>
                                <td><t t-esc="decimal(line.current_balance)"/> وحدة</td>
                            </tr>
                        </t>
                    </tbody>
                </table>
            </article>
        </section>

        <section class="ab_sales_dashboard__panel">
            <div class="ab_sales_dashboard__panel_header">
                <h2>مبيعات العملاء</h2>
                <span>الفاتورة + العميل + الأصناف</span>
            </div>
            <table>
                <thead>
                    <tr><th>الفاتورة</th><th>العميل</th><th>الأصناف</th><th>إجمالي الفاتورة</th></tr>
                </thead>
                <tbody>
                    <t t-foreach="state.data.invoice_lines" t-as="line" t-key="line.invoice_no">
                        <tr>
                            <td t-esc="line.invoice_no"/>
                            <td t-esc="line.customer_name"/>
                            <td t-esc="line.items_summary"/>
                            <td t-esc="money(line.invoice_total)"/>
                        </tr>
                    </t>
                </tbody>
            </table>
        </section>
    </t>
</div>
`;

registry.category("actions").add("ab_sales_dashboard.dashboard", SalesDashboardAction);
