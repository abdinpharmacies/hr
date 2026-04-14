odoo.define('abdin_js.ab_so_line_many2one', function (require) {
    "use strict";

    /*
    ##############################################################
    FormrRenderer and FormContoller Method
    extend events via
    events: _.extend({},FormRenderer.prototype.events,{'click my-tag .my-class':'_myCustomMethod'})
    ---or---
    instead of _.extend >> use Object.assign form ES6+
    ##############################################################
    */
    const fieldRegistry = require('web.field_registry');
    var FormController = require('web.FormController');
    var FormRenderer = require('web.FormRenderer')
    var core = require('web.core');
    var _t = core._t;
    FormRenderer.include({
        events: Object.assign({}, FormRenderer.prototype.events, {
            // ADD CLICK EVENT LISTENER TO -> .sort_html_table th
            "click div[name='product_id']": '_customSave',
        }), _customSave: function (e) {
            // STORE th NOTE THAT -> "e.target" MAY NOT EQUAL "th" - (if you click o child of "th")
            this.trigger_up('custom_save', {

                // target_table: target_table,
                // index: th.cellIndex,
                // direction: direction,
            });
        },

    });
    FormController.include({
        custom_events: _.extend({}, FormController.prototype.custom_events, {
            custom_save: '_customSave', // sort_table: '_sortTable',
        }), init: function () {
            this._super.apply(this, arguments);
        },

        // _sortTable: function (e) {
        //     // const target_table = document.getElementById('sortMe');
        //     const index = e.data.index
        //     const target_table = e.data.target_table;
        // },
        _customSave: function (e) {
            // const target_table = document.getElementById('sortMe');
            console.log('this', this);
            console.log('FormRenderer.prototype.events', FormRenderer.prototype.events)
            console.log(this.model.modelName)
        },

    });
    /*
    ##############################################################
    Widget Method
    After Creating Widget using .extend
      ... Put your widget in xml >> <field name='' widget='ab_so_line_many2one'
    ##############################################################
    */

    const {FieldOne2Many, FieldMany2One} = require('web.relational_fields');

    const SoLineOne2Many = FieldOne2Many.extend({
        _onFieldChanged: function (ev) {
            console.log('field changes One2many.....');

            if (ev.data.changes) {
                console.log('ev.data.changes', ev.data.changes)

                const recordID = '1';
                // FormController.prototype.saveRecord(recordID)
                // ev.data.changes.is_so_line_edited = true;
            }
            this._super.apply(this, arguments);
        }
    });

    const SoLineMany2one = FieldMany2One.extend({
        /**
         * @override
         *
         * When the user manually changes the field, we need to change the is_so_line_edited field in this model
         * to know the changes is manual and not via a compute method.
         */
        _onFieldChanged(ev) {
            console.log('field changes Many2one updated log .....');
            if (ev.data.changes
                // && ev.data.changes.hasOwnProperty('item_id')
                // && !ev.data.changes.so_line.is_so_line_edited
            ) {
                // ev.data.changes.qty = 3;
            }
            this._super.apply(this, arguments);
        },
    });


    fieldRegistry.add('ab_so_line_one2many', SoLineOne2Many);
    fieldRegistry.add('ab_so_line_many2one', SoLineMany2one);

    return SoLineOne2Many;

});