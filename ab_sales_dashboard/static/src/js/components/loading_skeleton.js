/** @odoo-module **/

import { Component, xml } from "@odoo/owl";

export class LoadingSkeleton extends Component {
    static template = xml`
        <div class="ab_sales_dashboard__skeleton sd-animate-in">
            <div class="ab_sales_dashboard__kpis">
                <div t-foreach="4" t-as="i" t-key="i" class="sd-skeleton sd-skeleton-kpi sd-animate-in"
                     t-att-style="'animation-delay:' + (i * 80) + 'ms'"/>
            </div>
            <div class="ab_sales_dashboard__split" style="margin-top:20px">
                <div class="sd-skeleton sd-skeleton-card sd-animate-in" style="animation-delay:350ms"/>
                <div class="sd-skeleton sd-skeleton-card sd-animate-in" style="animation-delay:420ms"/>
            </div>
            <div class="ab_sales_dashboard__tables" style="margin-top:20px">
                <div class="sd-skeleton sd-skeleton-card sd-animate-in" style="animation-delay:500ms"/>
                <div class="sd-skeleton sd-skeleton-card sd-animate-in" style="animation-delay:560ms"/>
            </div>
            <div style="margin-top:20px">
                <div class="sd-skeleton sd-skeleton-card sd-animate-in" style="animation-delay:640ms"/>
            </div>
        </div>
    `;
}
