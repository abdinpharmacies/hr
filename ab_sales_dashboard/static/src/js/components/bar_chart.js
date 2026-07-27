/** @odoo-module **/

import { Component, xml, markup } from "@odoo/owl";
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
        <div class="sd-bar-chart sd-animate-in" t-att-style="'animation-delay:' + (props.delay || 0) + 'ms'">
            <t t-foreach="props.items" t-as="item" t-key="item.category || item_index">
                <div class="sd-bar-item">
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

    pct(v) {
        return pct(v);
    }
}

BarChart.props = {
    items: { type: Array },
    labelFormatter: { type: Function, optional: true },
    delay: { type: Number, optional: true },
};
