odoo.define('ab_fixed_asset.FormController', function (require) {
    "use strict";

    let FormController = require('web.FormController');

    FormController.include({
        saveRecord: async function () {
            let self = this;
            let response = await this._super.apply(this, arguments);

            let modelName = self.modelName;
            if (modelName === 'ab_accounting_je_header') {
                // Your JavaScript code goes here.
                let record = self.model.get(self.handle);
                if (record.data.has_fixed_assets && !record.data.fixed_asset_ids?.count) {
                    // Select the notebook page and append an arrow to it.
                    let notebookPage = self.$el.find("li.fixed-assets");
                    notebookPage.prepend('<div class="fixed-asset-arrow"></div>');


                    // Adjust the top and right properties dynamically.
                    // As arrowElement is absolute and relative to notebookPage Element,
                    // 👉  we only want to set 'top' and 'left' positions according to 'notebookPage' Element
                    let arrowElement = self.$el.find(".fixed-asset-arrow");
                    let topPosition = -arrowElement.outerHeight() - 30 // 30 is arrow head;
                    let leftPosition = (notebookPage.width() - arrowElement.outerWidth()) / 2;

                    arrowElement.css({
                        position: "absolute",
                        top: topPosition,
                        left: leftPosition,
                        zIndex: 999,
                    });

                } else {
                    let arrowElement = self.$el.find(".fixed-asset-arrow");
                    if (arrowElement.length) {
                        arrowElement.remove();
                    }
                }
            }  // end of >>> if(modelName === 'ab_accounting_je_header')
            return response

        },
    });
});

