/** @odoo-module **/

import { Component, xml, useState, onWillUpdateProps } from "@odoo/owl";
import { money, pct } from "../utils/formatters.js";

export class DonutChart extends Component {
    static template = xml`
        <div class="sd-donut-wrap sd-animate-in" t-att-style="'animation-delay:' + (props.delay || 0) + 'ms'">
            <svg class="sd-donut-svg" viewBox="0 0 120 120">
                <circle cx="60" cy="60" r="50"
                        stroke-width="12"
                        class="sd-donut-track"/>
                <circle cx="60" cy="60" r="50"
                        t-att-stroke="state.colorA"
                        stroke-width="12"
                        t-att-stroke-dasharray="state.circumference"
                        t-att-stroke-dashoffset="state.offsetA"
                        style="transition: stroke-dashoffset 1s cubic-bezier(0.16,1,0.3,1)"/>
                <circle cx="60" cy="60" r="50"
                        t-att-stroke="state.colorB"
                        stroke-width="12"
                        t-att-stroke-dasharray="state.circumference"
                        t-att-stroke-dashoffset="state.offsetB"
                        style="transition: stroke-dashoffset 1s cubic-bezier(0.16,1,0.3,1) 0.1s"/>
            </svg>
            <div class="sd-donut-legend">
                <div class="sd-donut-legend-item">
                    <span class="sd-legend-label">
                        <span class="sd-legend-dot" t-att-style="'background:' + state.colorA"/>
                        <t t-esc="props.labelA"/>
                    </span>
                    <span class="sd-legend-value" t-esc="formatMoney(props.valueA)"/>
                    <span class="sd-legend-pct" t-esc="pct(state.pctA)"/>
                </div>
                <div class="sd-donut-legend-item">
                    <span class="sd-legend-label">
                        <span class="sd-legend-dot" t-att-style="'background:' + state.colorB"/>
                        <t t-esc="props.labelB"/>
                    </span>
                    <span class="sd-legend-value" t-esc="formatMoney(props.valueB)"/>
                    <span class="sd-legend-pct" t-esc="pct(state.pctB)"/>
                </div>
            </div>
        </div>
    `;

    setup() {
        this.state = useState({
            circumference: 2 * Math.PI * 50,
            offsetA: 2 * Math.PI * 50,
            offsetB: 2 * Math.PI * 50,
            pctA: 0,
            pctB: 0,
            colorA: this.props.colorA || "#10b981",
            colorB: this.props.colorB || "#10b981",
        });

        onWillUpdateProps(() => this.computeArcs());
        this.computeArcs();
    }

    computeArcs() {
        const total = Number(this.props.valueA || 0) + Number(this.props.valueB || 0);
        const pctA = total ? (100 * Number(this.props.valueA || 0)) / total : 0;
        const pctB = total ? 100 - pctA : 0;
        const c = this.state.circumference;
        this.state.pctA = pctA;
        this.state.pctB = pctB;
        this.state.offsetA = c - (c * pctA) / 100;
        this.state.offsetB = c - (c * pctB) / 100;
    }

    formatMoney(v) {
        return money(v);
    }

    pct(v) {
        return pct(v);
    }
}

DonutChart.props = {
    valueA: { type: Number },
    valueB: { type: Number },
    labelA: { type: String },
    labelB: { type: String },
    colorA: { type: String, optional: true },
    colorB: { type: String, optional: true },
    delay: { type: Number, optional: true },
};

DonutChart.defaultProps = {
    colorA: "#10b981",
    colorB: "#64748b",
};
