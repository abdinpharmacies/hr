odoo.define('custom_arabic_locale.numerals', function (require) {
    "use strict";
    var fieldUtils = require('web.field_utils');
    var core = require('web.core');
    var _t = core._t;

    var arabicNumeralMap = {
        '٠': '0',
        '١': '1',
        '٢': '2',
        '٣': '3',
        '٤': '4',
        '٥': '5',
        '٦': '6',
        '٧': '7',
        '٨': '8',
        '٩': '9'
    };

    function convertToWesternNumerals(str) {
        return str.split('').map(function (char) {
            return arabicNumeralMap[char] || char;
        }).join('');
    }


    // Override integer formatting without thousand separator
    fieldUtils.format.integer = function (value) {
        return convertToWesternNumerals(value.toString().replace(/,/g, ''));
    };


    // Override date formatting
    var originalFormatDate = fieldUtils.format.date;
    fieldUtils.format.date = function (value, field, options) {
        var formattedValue = originalFormatDate(value, field, options);
        return convertToWesternNumerals(formattedValue);
    };

    // Override datetime formatting
    var originalFormatDatetime = fieldUtils.format.datetime;
    fieldUtils.format.datetime = function (value, field, options) {
        var formattedValue = originalFormatDatetime(value, field, options);
        return convertToWesternNumerals(formattedValue);
    };


});

//////////////////////////  END OF FILE //////////////////////////////////
//////////////////////////////////////////////////////////////////////////
/*
    // Override float formatting
    var originalFormatFloat = fieldUtils.format.float;
    fieldUtils.format.float = function (value, field, options) {
        var formattedValue = originalFormatFloat(value, field, options);
        return convertToWesternNumerals(formattedValue);
    };
*/

/*
    // Override monetary formatting
    var originalFormatMonetary = fieldUtils.format.monetary;
    fieldUtils.format.monetary = function (value, field, options) {
        var formattedValue = originalFormatMonetary(value, field, options);
        return convertToWesternNumerals(formattedValue);
    };
*/

/*
    var FormView = require('web.FormView');

    function applyNumeralConversion() {
        // Convert numbers in form fields
        $('input').each(function () {
            var $this = $(this);
            var value = $this.val();
            $this.val(convertToWesternNumerals(value));
        });

        // Convert numbers in text areas
        $('textarea').each(function () {
            var $this = $(this);
            var value = $this.val();
            $this.val(convertToWesternNumerals(value));
        });
    }

    // Apply numeral conversion when form view is rendered
    FormView.include({
        renderElement: function () {
            this._super.apply(this, arguments);
            applyNumeralConversion();
        }
    });
*/

// formats.format.integer = (value) => convertToWesternNumerals(value.toString());
// formats.format.float = (value) => convertToWesternNumerals(value.toFixed(2).toString());
// formats.format.datetime = (value) => convertToWesternNumerals(value.toString());
// formats.format.monetary = (value, currency_id, options) => convertToWesternNumerals(value.toFixed(2).toString());
/*
    // Apply numeral conversion on changes in input and textarea fields
    $(document).on('change', 'input, textarea', function () {
        var $this = $(this);
        var value = $this.val();
        $this.val(convertToWesternNumerals(value));
    });
*/
