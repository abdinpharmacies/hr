odoo.define('test_modulo.BasicView', function (require) {
    "use strict";

    var session = require('web.session');
    var BasicView = require('web.BasicView');
    BasicView.include({
        init: function (viewInfo, params) {
            var self = this;
            this._super.apply(this, arguments);
            if (self.controllerParams.modelName == 'ab_je_line') {
                session.user_has_group('group_tblje_manager').then(function (has_group) {
                    if (!has_group) {
                        self.controllerParams.archiveEnabled = 'False' in viewInfo.fields;
                    }
                });
            }
        },
    });
});