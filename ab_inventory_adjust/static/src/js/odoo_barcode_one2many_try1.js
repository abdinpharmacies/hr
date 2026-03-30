odoo.define('ab_inventory_adjust.track_f12_f8_keys', function (require) {
    "use strict";

    var FormController = require('web.FormController');
    var core = require('web.core');

    console.log('JS is working...');

    FormController.include({
        start: function () {
            var self = this;
            this._super.apply(this, arguments);

            // Check if the current form is for the desired model
            var modelName = this.modelName;

            console.log('Current model:', modelName);
            if (modelName === 'ab_inventory_adjust_header') {
                // Attach a keydown event listener to the form
                this.$el.on('keydown', function (event) {
                    console.log(event.key);
                    var enterDelayF12 = 1000;
                    var tabDelayF8 = 400;

                    if (event.key === 'F12' || event.keyCode === 123) {
                        event.preventDefault(); // Prevent default F12 action (e.g., opening developer tools)

                        // Add a delay before sending the Enter key
                        setTimeout(function () {
                            console.log(`Sending Enter {F12} key after ${enterDelayF12}ms delay`);
                            var enterEvent = new KeyboardEvent('keydown', {
                                key: 'Enter',
                                code: 'Enter',
                                keyCode: 13,
                                which: 13,
                                bubbles: true
                            });
                            document.activeElement.dispatchEvent(enterEvent);
                        }, enterDelayF12);
                    }

                    if (event.key === 'F8' || event.keyCode === 119) {
                        event.preventDefault(); // Prevent any default F8 action

                        // Add a delay before sending the Tab key
                        setTimeout(function () {
                            console.log(`Sending Tab {F8} key after ${tabDelayF8}ms delay`);
                            var tabEvent = new KeyboardEvent('keydown', {
                                key: 'Tab',
                                code: 'Tab',
                                keyCode: 9,
                                which: 9,
                                bubbles: true
                            });
                            document.activeElement.dispatchEvent(tabEvent);
                        }, tabDelayF8); // 400ms delay
                    }
                });
            }
        }
    });
});


// F12 code 123
// F8  code 119