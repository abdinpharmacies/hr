/** @odoo-module **/

import { Component, xml, markup } from "@odoo/owl";

export class KpiCard extends Component {
    static template = xml`
        <div class="ab_sales_dashboard__kpi sd-animate-in"
             t-att-class="props.variant ? 'ab_sales_dashboard__kpi--' + props.variant : ''"
             t-att-style="'animation-delay:' + (props.delay || 0) + 'ms'">
            <div class="sd-kpi-icon" t-out="iconMarkup"/>
            <span class="sd-kpi-label" t-esc="props.label"/>
            <strong class="sd-kpi-value" t-esc="props.value"/>
            <t t-if="props.trend !== undefined &amp;&amp; props.trend !== null">
                <div class="sd-kpi-trend">
                    <span class="sd-kpi-trend-icon"
                          t-att-class="trendPositive() ? 'positive' : 'negative'"
                          t-out="trendIcon()"/>
                    <span t-esc="props.formatter ? props.formatter(trendAbs()) : trendAbs()"/>
                    <t t-if="props.trendLabel">
                        <span class="sd-kpi-trend-label" t-esc="props.trendLabel"/>
                    </t>
                </div>
            </t>
            <t t-if="props.sub">
                <span class="sd-kpi-sub" t-esc="props.sub"/>
            </t>
        </div>
    `;

    setup() {
        this.iconMarkup = this.props.icon ? markup(this.props.icon) : markup('');
    }

    trendPositive() {
        return Number(this.props.trend || 0) >= 0;
    }

    trendAbs() {
        return Math.abs(Number(this.props.trend || 0));
    }

    trendIcon() {
        return this.trendPositive() ? markup('&#9650;') : markup('&#9660;');
    }
}

KpiCard.props = {
    label: { type: String },
    value: { type: String },
    icon: { type: String, optional: true },
    variant: { type: String, optional: true },
    trend: { type: [Number, String, null, undefined], optional: true },
    trendLabel: { type: String, optional: true },
    sub: { type: String, optional: true },
    formatter: { type: Function, optional: true },
    delay: { type: Number, optional: true },
};
