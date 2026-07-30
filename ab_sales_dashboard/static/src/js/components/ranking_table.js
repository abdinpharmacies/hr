/** @odoo-module **/

import { Component, xml } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { money, pct, number } from "../utils/formatters.js";

export class RankingTable extends Component {
    static template = xml`
        <div class="sd-ranking sd-animate-in" t-att-style="'animation-delay:' + (props.delay || 0) + 'ms'">
            <table t-att-aria-busy="props.loading">
                <thead>
                    <tr>
                        <th class="sd-rank-th">#</th>
                        <th t-esc="props.nameLabel"/>
                        <th t-esc="props.valueLabel"/>
                        <th t-esc="props.pctLabel || _t('Percentage')"/>
                    </tr>
                </thead>
                <tbody>
                    <t t-foreach="props.rows" t-as="row" t-key="rowKey(row, row_index)">
                        <tr>
                            <td>
                                <span class="sd-rank-badge"
                                      t-att-class="{
                                          'sd-rank-badge--gold': row_index === 0,
                                          'sd-rank-badge--silver': row_index === 1,
                                          'sd-rank-badge--bronze': row_index === 2,
                                      }"
                                      t-esc="rowNumber(row_index)"/>
                            </td>
                            <td>
                                <strong t-esc="getName(row)"/>
                                <t t-if="props.subNameField">
                                    <small t-esc="row[props.subNameField]"/>
                                </t>
                            </td>
                            <td t-esc="formatValue(row)"/>
                            <td>
                                <span t-esc="pct(row[props.pctField || 'pct_of_total'])"/>
                                <span class="sd-mini-bar"
                                      t-att-style="'width:' + miniBarWidth(row) + '%'"/>
                            </td>
                        </tr>
                    </t>
                    <t t-if="!props.rows.length &amp;&amp; !props.loading">
                        <tr>
                            <td t-att-colspan="props.subNameField ? 4 : 4">
                                <div class="sd-empty-state">
                                    <i class="fa fa-inbox"/>
                                    <span t-esc="_t('No records found.')"/>
                                </div>
                            </td>
                        </tr>
                    </t>
                </tbody>
            </table>
        </div>
    `;

    rowNumber(index) {
        return ((this.props.page || 1) - 1) * (this.props.pageSize || 20) + index + 1;
    }

    rowKey(row, index) {
        return row.row_key || row.employee_eplus_id || row.eplus_item_id || index;
    }

    getName(row) {
        if (this.props.nameField) {
            return row[this.props.nameField] || "";
        }
        return row.employee_name || row.product_name || "";
    }

    formatValue(row) {
        const field = this.props.valueField || "total_sales";
        const val = row[field];
        if (this.props.valueFormatter) {
            return this.props.valueFormatter(val);
        }
        return money(val);
    }

    pctValue(row) {
        return Number(row[this.props.pctField || "pct_of_total"] || 0);
    }

    miniBarWidth(row) {
        return Math.min(this.pctValue(row), 100);
    }

    pct(v) {
        return pct(v);
    }

    _t = _t;
}

RankingTable.props = {
    rows: { type: Array },
    nameLabel: { type: String },
    valueLabel: { type: String },
    pctLabel: { type: String, optional: true },
    nameField: { type: String, optional: true },
    subNameField: { type: String, optional: true },
    valueField: { type: String, optional: true },
    valueFormatter: { type: Function, optional: true },
    pctField: { type: String, optional: true },
    page: { type: Number, optional: true },
    pageSize: { type: Number, optional: true },
    loading: { type: Boolean, optional: true },
    delay: { type: Number, optional: true },
};
