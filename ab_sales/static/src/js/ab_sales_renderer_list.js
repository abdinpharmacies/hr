/** @odoo-module **/

import ListRenderer from "web.ListRenderer";
import core from "web.core";

const _t = core._t;

ListRenderer.include({
    events: Object.assign({}, ListRenderer.prototype.events, {
        'click .btn-balance-allow-new': '_onClickBalanceButton',
    }),

    _renderButton: function (record, node) {
        const $button = this._super.apply(this, arguments);

        if (node.tag === 'button' &&
            (node.attrs.class || '').includes('btn-balance-allow-new')) {
            $button.prop('disabled', false);
            $button.removeClass('o_disabled_button');
        }
        return $button;
    },

    _onClickBalanceButton: function (ev) {
        ev.preventDefault();
        ev.stopPropagation();

        const $tr = $(ev.currentTarget).closest('tr.o_data_row');
        const rowId = $tr.data('id');
        const state = this.state || {};
        const data = state.data || [];

        const record = data.find(rec => rec.id === rowId);

        if (!record) {
            console.warn('ab_sales: no record found for rowId', rowId);
            return;
        }

        const productField = record.data.product_id;
        let productId = null;

        // Case 1: classic m2o format [id, name]
        if (Array.isArray(productField)) {
            productId = productField[0];
            // Case 2: plain integer id
        } else if (typeof productField === 'number') {
            productId = productField;
            // Case 3: relational "record" object (your console dump)
        } else if (productField && typeof productField === 'object') {
            productId =
                productField.res_id ||
                productField.ref ||
                (productField.data && productField.data.id) ||
                null;
        }

        if (!productId) {
            console.log('No ProductId extracted from productField:', productField);
            this.trigger_up('display_notification', {
                type: 'warning',
                title: _t('No product'),
                message: _t('Please choose a product first, then click Balance.'),
            });
            return;
        }

        // Open wizard by XMLID, with product in context
        this.trigger_up('do_action', {
            action: 'ab_sales.action_ab_product_balance_wizard',
            options: {
                additional_context: {
                    default_product_id: productId,
                },
            },
        });
    },
});
