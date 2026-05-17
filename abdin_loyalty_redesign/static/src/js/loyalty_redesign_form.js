odoo.define('abdin_loyalty_redesign.form_patch', function (require) {
    'use strict';

    var FormRenderer = require('web.FormRenderer');
    var { patch } = require('web.utils');

    patch(FormRenderer.prototype, 'abdin_loyalty_redesign__form_patch', {
        _renderSheet: function () {
            var self = this;
            return this._super.apply(this, arguments).then(function () {
                var $form = self.$('.o_form_view');
                if (!$form.length) return;

                var $typeField = $form.find('[name="program_type"]');
                if ($typeField.length) {
                    var val = $typeField.val();
                    if (val) {
                        $form.attr('data-program-type', val);
                    }
                    $typeField.on('change', function () {
                        var newVal = $(this).val();
                        if (newVal) {
                            $form.attr('data-program-type', newVal);
                        }
                    });
                }
            });
        },
    });

});
