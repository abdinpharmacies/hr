odoo.define('ab_inventory_adjust.GetInventoryDetails', function (require) {
    "use strict";

    var ListView = require('web.ListView');
    var core = require('web.core');
    var rpc = require('web.rpc');

    var _t = core._t;

    ListView.include({
        events: _.extend({}, ListView.prototype.events, {
            'click .get_inventory_details': '_onGetInventoryDetailsClick',
        }),

        _onGetInventoryDetailsClick: function (event) {
            event.preventDefault();
            var self = this;
            var $target = $(event.currentTarget);
            var recordId = $target.closest('tr').data('id');

            rpc.query({
                model: 'ab_inventory_adjust_product',
                method: 'btn_get_inv_detailed',
                args: [[recordId]],
            }).then(function () {
                self._reload();  // Optionally reload the view to reflect changes
            }).catch(function (error) {
                console.error(_t('An error occurred: ') + error.message);
            });
        },
    });
});
