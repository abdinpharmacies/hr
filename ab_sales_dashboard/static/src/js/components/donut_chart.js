/** @odoo-module **/

import { Component, xml, useState, onWillUpdateProps } from "@odoo/owl";
import { money, pct } from "../utils/formatters.js";

export class DonutChart extends Component {
    static template = xml`
        <div class="sd-donut-wrap sd-animate-in" t-att-style="'animation-delay:' + (props.delay || 0) + 'ms'">
            <svg t-att-class="'sd-donut-svg' + (state.hoveredSegment ? ' sd-donut-svg--hovering sd-donut-svg--hover-' + state.hoveredSegment : '')"
                 viewBox="0 0 120 120">
                <circle cx="60" cy="60" r="50"
                        stroke-width="12"
                        class="sd-donut-track"/>
                <circle cx="60" cy="60" r="50"
                        t-att-stroke="state.colorA"
                        t-att-style="segmentStyle('a')"
                        stroke-width="12"
                        t-att-stroke-dasharray="state.dashA"
                        t-att-stroke-dashoffset="state.offsetA"
                        class="sd-donut-segment sd-donut-segment--a"
                        t-on-mouseenter="() => this.setHoveredSegment('a')"
                        t-on-mouseleave="() => this.setHoveredSegment(null)"
                        t-on-focus="() => this.setHoveredSegment('a')"
                        t-on-blur="() => this.setHoveredSegment(null)"
                        tabindex="0"/>
                <circle cx="60" cy="60" r="50"
                        t-att-stroke="state.colorB"
                        t-att-style="segmentStyle('b')"
                        stroke-width="12"
                        t-att-stroke-dasharray="state.dashB"
                        t-att-stroke-dashoffset="state.offsetB"
                        class="sd-donut-segment sd-donut-segment--b"
                        t-on-mouseenter="() => this.setHoveredSegment('b')"
                        t-on-mouseleave="() => this.setHoveredSegment(null)"
                        t-on-focus="() => this.setHoveredSegment('b')"
                        t-on-blur="() => this.setHoveredSegment(null)"
                        tabindex="0"/>
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
            dashA: `0 ${2 * Math.PI * 50}`,
            dashB: `0 ${2 * Math.PI * 50}`,
            offsetA: 0,
            offsetB: 0,
            pctA: 0,
            pctB: 0,
            colorA: this.props.colorA || "#10b981",
            colorB: this.props.colorB || "#10b981",
            hoveredSegment: null,
            segmentAOffsetX: 0,
            segmentAOffsetY: -4,
            segmentBOffsetX: 0,
            segmentBOffsetY: 4,
        });

        onWillUpdateProps(() => this.computeArcs());
        this.computeArcs();
    }

    computeArcs() {
        const total = Number(this.props.valueA || 0) + Number(this.props.valueB || 0);
        const pctA = total ? (100 * Number(this.props.valueA || 0)) / total : 0;
        const pctB = total ? 100 - pctA : 0;
        const c = this.state.circumference;
        const arcA = (c * pctA) / 100;
        const arcB = (c * pctB) / 100;
        this.state.pctA = pctA;
        this.state.pctB = pctB;
        this.state.dashA = `${arcA} ${c - arcA}`;
        this.state.dashB = `${arcB} ${c - arcB}`;
        this.state.offsetA = 0;
        this.state.offsetB = -arcA;
        const aOffset = this.segmentOffset(0, pctA);
        const bOffset = this.segmentOffset(pctA, pctB);
        this.state.segmentAOffsetX = aOffset.x;
        this.state.segmentAOffsetY = aOffset.y;
        this.state.segmentBOffsetX = bOffset.x;
        this.state.segmentBOffsetY = bOffset.y;
    }

    segmentOffset(startPct, spanPct) {
        const midpointDegrees = ((startPct + spanPct / 2) * 360) / 100;
        const radians = (midpointDegrees * Math.PI) / 180;
        const distance = 4;
        return {
            x: Math.cos(radians) * distance,
            y: Math.sin(radians) * distance,
        };
    }

    segmentStyle(segment) {
        const color = segment === "a" ? this.state.colorA : this.state.colorB;
        const x = segment === "a" ? this.state.segmentAOffsetX : this.state.segmentBOffsetX;
        const y = segment === "a" ? this.state.segmentAOffsetY : this.state.segmentBOffsetY;
        return [
            `--sd-segment-color: ${color}`,
            `--sd-segment-x: ${x.toFixed(2)}px`,
            `--sd-segment-y: ${y.toFixed(2)}px`,
        ].join(";");
    }

    setHoveredSegment(segment) {
        this.state.hoveredSegment = segment;
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
