odoo.define('ab_inventory_adjust.barcode_reader', function (require) {
    "use strict";

    const FormController = require('web.FormController');
    const Helper = require('ab_inventory_adjust.helper_functions');

    FormController.include({
        start: function () {
            const res = this._super.apply(this, arguments);
            this.$el.on('keydown', async function (event) {

                if (event.key === Helper.PREFIX) {
                    event.preventDefault(); // Prevent default PREFIX behavior

                    const barcode = await Helper.collectBarcodeKeys();

                    await Helper.addLineIfNeeded();

                    document.activeElement.value = barcode;
                    document.activeElement.dispatchEvent(new Event('input', {bubbles: true}));

                    const itemsCount = await Helper.fetchDropdownItems(barcode);

                    if (itemsCount === 1) {
                        Helper.sendKey('Tab', 9)
                    }


                    setTimeout(() => {
                        Helper.selectText(document.activeElement)
                    }, 50)
                }
            });
            return res;
        },
    });
});
