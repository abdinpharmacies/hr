/** @odoo-module **/
import { registry } from "@web/core/registry";
import { Component, useState, xml } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";

class BulkImportResultsDialog extends Component {
    static template = xml`
        <Dialog size="'lg'">
            <div class="ab_bulk_dialog">
                <div class="ab_bulk_header">
                    <h3 class="ab_bulk_title">Bulk Product Import Results</h3>
                </div>

                <div class="ab_bulk_summary_row">
                    <div class="ab_bulk_summary_card ab_bulk_summary_card--branches">
                        <div class="ab_bulk_summary_value"><t t-esc="props.branches_processed"/></div>
                        <div class="ab_bulk_summary_label">Branches Processed</div>
                    </div>
                    <div class="ab_bulk_summary_card ab_bulk_summary_card--added">
                        <div class="ab_bulk_summary_value"><t t-esc="props.products_added"/></div>
                        <div class="ab_bulk_summary_label">Products Added</div>
                    </div>
                    <div class="ab_bulk_summary_card ab_bulk_summary_card--missing">
                        <div class="ab_bulk_summary_value"><t t-esc="props.products_missing"/></div>
                        <div class="ab_bulk_summary_label">Products Missing</div>
                    </div>
                </div>

                <div class="ab_bulk_warning" t-if="props.has_missing">
                    <span class="ab_bulk_warning_icon">&#x26A0;</span>
                    Some product codes could not be found
                </div>

                <div class="ab_bulk_empty" t-if="props.is_empty">
                    <div class="ab_bulk_empty_icon">&#x1F50D;</div>
                    <div class="ab_bulk_empty_title">No Matching Products Found</div>
                    <div class="ab_bulk_empty_desc">The entered product codes do not exist in the selected branches.</div>
                </div>

                <div class="ab_bulk_table_wrapper" t-if="!props.is_empty">
                    <table class="ab_bulk_table">
                        <thead>
                            <tr>
                                <th>Branch</th>
                                <th class="ab_bulk_cell_added">Added</th>
                                <th class="ab_bulk_cell_missing">Missing</th>
                            </tr>
                        </thead>
                        <tbody>
                            <t t-foreach="props.branch_results" t-as="row" t-key="row_index">
                                <tr>
                                    <td><t t-esc="row.branch_name"/></td>
                                    <td class="ab_bulk_cell_added"><span class="ab_bulk_badge ab_bulk_badge--added"><t t-esc="row.added_count"/></span></td>
                                    <td class="ab_bulk_cell_missing"><span class="ab_bulk_badge ab_bulk_badge--missing" t-if="row.missing_count"><t t-esc="row.missing_count"/></span><span t-else="">0</span></td>
                                </tr>
                            </t>
                        </tbody>
                    </table>
                </div>

                <div class="ab_bulk_missing_section" t-if="props.has_missing">
                    <div class="ab_bulk_missing_header" t-on-click="toggleMissing">
                        <span t-if="!state.showMissing">Show Missing Product Codes</span>
                        <span t-else="">Hide Missing Product Codes</span>
                        <span class="ab_bulk_chevron" t-att-class="state.showMissing ? 'ab_bulk_chevron--open' : ''">&#x25B6;</span>
                    </div>
                    <div class="ab_bulk_missing_body" t-if="state.showMissing">
                        <t t-foreach="props.all_missing_codes" t-as="code" t-key="code_index">
                            <code class="ab_bulk_missing_code"><t t-esc="code"/></code>
                        </t>
                    </div>
                </div>

                <div class="ab_bulk_footer">
                    <button class="btn btn-secondary" t-on-click="downloadMissing" t-if="props.has_missing">
                        Download Missing Codes
                    </button>
                    <button class="btn btn-primary" t-on-click="close">
                        Close
                    </button>
                </div>
            </div>
        </Dialog>
    `;
    static components = { Dialog };
    static props = {
        branches_processed: { type: Number },
        products_added: { type: Number },
        products_missing: { type: Number },
        has_missing: { type: Boolean, optional: true },
        is_empty: { type: Boolean, optional: true },
        branch_results: { type: Array },
        all_missing_codes: { type: Array, optional: true },
        close: { type: Function, optional: true },
    };

    setup() {
        this.state = useState({ showMissing: false });
    }

    toggleMissing() {
        this.state.showMissing = !this.state.showMissing;
    }

    downloadMissing() {
        const codes = this.props.all_missing_codes || [];
        if (!codes.length) return;
        const text = codes.join('\n');
        const blob = new Blob([text], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'missing_product_codes.txt';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }

    close() {
        if (this.props.close) this.props.close();
    }
}

registry.category('actions').add('ab_inventory_bulk_code_results', function (env, action) {
    const dialog = env.services.dialog;
    dialog.add(BulkImportResultsDialog, action.params);
});
