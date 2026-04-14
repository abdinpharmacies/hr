odoo.define('web_editor.field_html_tests', function (require) {
    "use strict";

    var FormController = require('web.FormController');
    var core = require('web.core');
    var _t = core._t;

    FormController.include({
        /*
        _setEditMode: async function () {
            await this._super.apply(this, arguments);
            if (_formResolveTestPromise) {
                _formResolveTestPromise();
            }
        },
        */
        _saveRecord: function (recordId) {
            // var record = this.model.get(recordId, {raw: true});
            // if (record.isDirty() && this.renderer.isInMultipleRecordEdition(recordId)) {
            //     // do not save the record (see _saveMultipleRecords)
            //     const prom = this.multipleRecordsSavingPromise || Promise.reject();
            //     this.multipleRecordsSavingPromise = null;
            //     return prom;
            // }
            console.log('Record Saved successfully...', arguments)

            return this._super.apply(this, arguments);
        },
    });
})
