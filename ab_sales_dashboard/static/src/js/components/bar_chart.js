/** @odoo-module **/

import { Component, xml, markup, useState } from "@odoo/owl";
import { money, pct } from "../utils/formatters.js";

const ICONS = {
    cash: markup('<i class="fa fa-money"/>'),
    delivery: markup('<i class="fa fa-truck"/>'),
    contract: markup('<i class="fa fa-file-text-o"/>'),
    offer: markup('<i class="fa fa-tag"/>'),
};

const COLORS = {
    cash: "#10b981",
    delivery: "#3b82f6",
    contract: "#8b5cf6",
    offer: "#f59e0b",
};

export class BarChart extends Component {
    static template = xml`
        <div t-att-class="'sd-bar-chart sd-animate-in' + (state.hoveredCategory ? ' sd-bar-chart--hovering' : '')"
             t-att-style="'animation-delay:' + (props.delay || 0) + 'ms'">
            <t t-foreach="props.items" t-as="item" t-key="item.category || item_index">
                <div t-att-class="'sd-bar-item' + (state.hoveredCategory === item.category ? ' sd-bar-item--active' : '')"
                     t-att-style="'--sd-bar-color:' + getColor(item.category)"
                     t-on-mouseenter="() => this.setHoveredCategory(item.category)"
                     t-on-mouseleave="() => this.setHoveredCategory(null)"
                     t-on-focusin="() => this.setHoveredCategory(item.category)"
                     t-on-focusout="() => this.setHoveredCategory(null)"
                     tabindex="0">
                    <div class="sd-bar-item-header">
                        <span class="sd-bar-item-label">
                            <span class="sd-bar-icon" t-out="getIcon(item.category)"/>
                            <t t-esc="props.labelFormatter ? props.labelFormatter(item.category) : item.category"/>
                        </span>
                        <span class="sd-bar-item-value" t-esc="formatMoney(item.total_sales)"/>
                    </div>
                    <div class="sd-bar-track">
                        <div class="sd-bar-fill"
                             t-att-style="'width:' + getBarWidth(item.pct_of_total) + '%; background:' + getColor(item.category)"/>
                    </div>
                    <span class="sd-bar-item-pct" t-esc="pct(item.pct_of_total)"/>
                </div>
            </t>
        </div>
    `;

    setup() {
        this.state = useState({
            hoveredCategory: null,
        });
    }

    getIcon(category) {
        return ICONS[category] || markup('<i class="fa fa-circle-o"/>');
    }

    getColor(category) {
        return COLORS[category] || "#3b82f6";
    }

    getBarWidth(pctValue) {
        return Math.min(Math.max(Number(pctValue || 0), 1), 100);
    }

    formatMoney(v) {
        return money(v);
    }

    setHoveredCategory(category) {
        this.state.hoveredCategory = category;
    }

    pct(v) {
        return pct(v);
    }
}

BarChart.props = {
    items: { type: Array },
    labelFormatter: { type: Function, optional: true },
    delay: { type: Number, optional: true },
};
