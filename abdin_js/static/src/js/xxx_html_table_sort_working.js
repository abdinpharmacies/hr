odoo.define('abdin_js.TableSort', function (require) {
    "use strict";

    var FormController = require('web.FormController');
    var FormRenderer = require('web.FormRenderer');
    // let target_table;
    let direction;

    FormRenderer.include({
        events: _.extend({}, FormRenderer.prototype.events, {
            // 'click #sortMe th': '_onTableClick',
            'click .sort_html_table th': '_onTableClick',
        }),
        _onTableClick: function (e) {
            if (e.target) {
                const target_table = e.target.closest('table');
                this.trigger_up('sort_table', {target_table: target_table, index: e.target.cellIndex});
            }

        },

    });
    FormController.include({
        custom_events: _.extend({}, FormController.prototype.custom_events, {
            sort_table: '_sortTable',
        }),
        init: function () {
            this._super.apply(this, arguments);
        },

        _sortTable: function (e) {

            // const target_table = document.getElementById('sortMe');
            const index = e.data.index
            const target_table = e.data.target_table;
            const headers = target_table.querySelectorAll('th');
            const tableBody = target_table.querySelector('tbody');
            const rows = tableBody.querySelectorAll('tr');

            // Transform the content of given cell in given column
            const transform = function (index, content) {
                // Get the data type of column
                if (headers[index].classList.contains('sort-as-number')) {
                    return parseFloat(content.replace(/,/g, ''));
                } else {
                    return content;
                }
            };

            console.log('execute sortColumn .............')
            // Get the current direction
            // A factor based on the direction
            const multiplier = direction === 'asc' ? 1 : -1;
            const newRows = Array.from(rows);

            newRows.sort(function (rowA, rowB) {
                const cellA = rowA.querySelectorAll('td')[index].innerHTML;
                const cellB = rowB.querySelectorAll('td')[index].innerHTML;

                const a = transform(index, cellA);
                const b = transform(index, cellB);

                switch (true) {
                    case a > b:
                        return 1 * multiplier;
                    case a < b:
                        return -1 * multiplier;
                    case a === b:
                        return 0;
                }
            });

            // Remove old rows
            [].forEach.call(rows, function (row) {
                tableBody.removeChild(row);
            });

            // Reverse the direction
            direction = direction === 'asc' ? 'desc' : 'asc';

            // Append new row
            newRows.forEach(function (newRow) {
                tableBody.appendChild(newRow);
            });
        },

    });
})
