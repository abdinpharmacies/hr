odoo.define('ab_inventory_adjust.One2manyInsert', function (require) {
    "use strict";

    var ListRenderer = require('web.ListRenderer');

    ListRenderer.include({
        events: _.extend({}, ListRenderer.prototype.events, {
            'keydown': '_onKeydown',
        }),

        _onKeydown: function (event) {
            if (event.key === 'Insert') {
                event.preventDefault();
                console.log('Insert key pressed....')
            }
        },

        _focusFirstEditableCell: function (rowIndex) {
            var $row = this.$('tr[data-id]:eq(' + rowIndex + ')');
            var $firstEditableCell = $row.find('td.o_list_record_editable:eq(0)');
            $firstEditableCell.focus();
        },
    });
});
