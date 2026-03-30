odoo.define('abdin_js.custom_search_utils', function (require) {
    "use strict";
    const {_lt, _t} = require('web.core');
    const searchUtils = require('web.searchUtils');

    // Find the index of the 'contains' operator
    const containsIndex = searchUtils.FIELD_OPERATORS.char.findIndex(op => op.symbol === 'ilike');

    // Add the new operator after the 'contains' operator
    if (containsIndex !== -1) {
        searchUtils.FIELD_OPERATORS.char.splice(containsIndex + 1, 0,
            {symbol: "=ilike", description: _lt("% contains ")}
        );
    }
});