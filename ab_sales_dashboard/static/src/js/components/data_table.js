/** @odoo-module **/

import { Component, xml, markup } from "@odoo/owl";
import { money, number } from "../utils/formatters.js";

export class DataTable extends Component {
    static template = xml`
        <div class="sd-data-table sd-animate-in" t-att-style="'animation-delay:' + (props.delay || 0) + 'ms'">
            <table t-att-aria-busy="props.loading">
                <thead>
                    <tr>
                        <t t-foreach="props.columns" t-as="col" t-key="col.field">
                            <th t-esc="col.label"/>
                        </t>
                    </tr>
                </thead>
                <tbody>
                    <t t-foreach="props.rows" t-as="row" t-key="rowKey(row, row_index)">
                        <tr>
                            <t t-foreach="props.columns" t-as="col" t-key="col.field">
                                <td>
                                    <t t-if="col.render" t-out="renderCell(col, row)"/>
                                    <t t-else="" t-esc="formatCell(row[col.field], col)"/>
                                </td>
                            </t>
                        </tr>
                    </t>
                </tbody>
            </table>
            <div t-if="!props.rows.length &amp;&amp; !props.loading" class="sd-empty-state">
                <i class="fa fa-inbox"/>
                <span>No records found.</span>
            </div>
        </div>
    `;

    renderCell(col, row) {
        const result = col.render(row);
        if (result && typeof result === "object" && result.constructor && result.constructor.name === "Markup") {
            return result;
        }
        return markup(result || "");
    }

    rowKey(row, index) {
        return row.row_key || row.invoice_no || row.sth_id || index;
    }

    formatCell(value, col) {
        if (col.format === "money") {
            return money(value);
        }
        if (col.format === "number") {
            return number(value);
        }
        if (col.format === "truncate") {
            const str = String(value || "");
            return str.length > (col.maxLen || 60) ? str.slice(0, col.maxLen || 60) + "..." : str;
        }
        return value !== false && value !== null && value !== undefined ? String(value) : (col.fallback || "-");
    }
}

DataTable.props = {
    rows: { type: Array },
    columns: { type: Array },
    loading: { type: Boolean, optional: true },
    delay: { type: Number, optional: true },
};
