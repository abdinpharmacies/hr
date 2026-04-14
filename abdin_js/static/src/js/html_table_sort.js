odoo.define('abdin_js.TableSort', function (require) {
    "use strict";

    var FormController = require('web.FormController');
    var FormRenderer = require('web.FormRenderer');


    FormRenderer.include({
        events: _.extend({}, FormRenderer.prototype.events, {
            // ADD CLICK EVENT LISTENER TO -> .sort_html_table th
            'click .sort_html_table th': '_onTableClick',
        }),
        _onTableClick: function (e) {
            // STORE th NOTE THAT -> "e.target" MAY NOT EQUAL "th" - (if you click o child of "th")
            const th = e.target.closest('th')
            // STORE 'table' in target_table
            const target_table = e.target.closest('table');
            let icon = th.querySelector('i');
            if (!icon) {
                th.insertAdjacentHTML('beforeend', "<i class=''></i>");
                icon = th.querySelector('i');
            }

            // Reverse the direction: fa-arrow-up='desc' //// fa-arrow-down='asc'
            let direction = icon?.classList.contains('fa-arrow-up') ? 'asc' : 'desc';

            // select all 'i' icons then set className=''
            const icons = target_table.querySelectorAll('th i')
            icons.forEach((icon, _) => icon.className = '')
            
            if (direction === 'asc') {
                icon.classList.add('fa', 'fa-arrow-down')
            } else if (direction === 'desc') {
                icon.classList.add('fa', 'fa-arrow-up')
            }
            this.trigger_up('sort_table', {
                target_table: target_table,
                index: th.cellIndex,
                direction: direction,
            });
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

            // Get the current direction
            // A factor based on the direction
            let direction = e.data.direction;
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

            // Append new row
            newRows.forEach(function (newRow) {
                tableBody.appendChild(newRow);
            });
        },

    });
})
