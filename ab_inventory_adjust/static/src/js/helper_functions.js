odoo.define('ab_inventory_adjust.helper_functions', function (require) {
    "use strict";

    const MAX_WAIT_TIME = 3000; // Maximum wait time in milliseconds (3 seconds)
    const CHECK_INTERVAL = 50; // Interval between checks in milliseconds
    const PREFIX = 'F12';
    const SUFFIX = 'Enter';

    // GLOBALLY PREVENT PREFIX and SUFFIX
    async function handleEvent(event) {
        // Check if the active element is the body and the key is the specified PREFIX
        if (event.key === PREFIX) {
            event.preventDefault(); // Prevent the default behavior
            if (document.activeElement.tagName === 'BODY') {
                await addLineIfNeeded();
                await sleep(500);
            }
        }
    }

    // Attach the event handler to the desired event type, e.g., keydown
    document.addEventListener('keydown', async (event) => await handleEvent(event));


    // Utility function to pause execution for a given number of milliseconds
    function sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    async function fetchDropdownItems(barcode) {
        let elapsedTime = 0; // Time elapsed so far
        while (elapsedTime < MAX_WAIT_TIME) {
            // Get all the <li> elements with class 'ui-menu-item'
            let listItems = document.querySelectorAll('a.dropdown-item.ui-menu-item-wrapper');
            let noResultItems = document.querySelectorAll('li.o_m2o_no_result.ui-menu-item');

            // Check if 'No records' item is present
            if (noResultItems.length > 0) {
                return 0;
            }

            // Return the count of <li> elements if they are present
            if (listItems.length > 0) {
                const rpcItems = await performSearch(barcode);
                const rpcItemsCount = rpcItems.length;
                if (listItems.length !== rpcItemsCount) {
                    await sleep(500);
                }
                return rpcItemsCount;
            }

            await sleep(CHECK_INTERVAL);
            elapsedTime += CHECK_INTERVAL;
        }

        return 0; // Return 0 if the timeout is reached and no items are found
    }

    // Function to collect barcode keys
    function collectBarcodeKeys() {
        return new Promise(resolve => {
            let keys = [];

            // Handler for keydown events
            const barcodeKeyListener = function (event) {
                // Skip PREFIX key itself
                event.preventDefault(); // Prevent default action for all keys
                if (event.key === PREFIX) {
                    // DO NOTHING
                } else if (event.key === SUFFIX) {
                    // event.preventDefault();
                    // document.removeEventListener('keydown', barcodeKeyListener);
                    // resolve(keys.join(''));
                } else {
                    // Collect other keys
                    keys.push(event.key);
                }
            };

            // Listen for keydown events
            document.addEventListener('keydown', barcodeKeyListener);
            sleep(350).then(() => {
                document.removeEventListener('keydown', barcodeKeyListener);
                resolve(keys.join(''));
            })
        });
    }

    async function addLineIfNeeded() {
        const productExist = document.querySelector('[name="product_id"]');
        if (!productExist) return;

        if (!isActiveElementName('product_id')) {
            // If not in Many2One selection, click the "Add Line" button
            const addLineButton = document.querySelector('.o_field_x2many_list_row_add a');
            if (addLineButton) {
                addLineButton.click();
            } else {
                console.warn('Add button not found');
            }
        }

        // Wait until the element is in Many2One selection
        let elapsedTime = 0;

        while (elapsedTime < MAX_WAIT_TIME) {
            // Re-check if the current active element is in Many2One selection
            if (isActiveElementName('product_id')) {
                break;
            }

            await sleep(CHECK_INTERVAL);
            elapsedTime += CHECK_INTERVAL;
        }
    }

    function isActiveElementName(name) {
        const activeElement = document.activeElement;

        // Find the closest ancestor div with the specified name attribute
        const ancestorDiv = activeElement.closest(`div[name="${name}"]`);

        // Return true if such a div is found
        return ancestorDiv !== null;
    }

    const rpc = require("web.rpc");

// Function to perform the RPC call
    async function performSearch(barcode) {
        try {
            return await rpc.query({
                model: 'ab_product',  // Model name
                method: 'search_read',
                args: [[['barcode_ids', '=ilike', barcode]]], // Domain for search
                kwargs: {fields: ['id']}  // Fields to return
            });
        } catch (error) {
            console.error('Error performing search:', error);
            throw error;
        }
    }

    function sendKey(key, keyCode) {
        document.activeElement.dispatchEvent(new KeyboardEvent('keydown', {
            key: key,
            code: key,
            keyCode: keyCode,
            which: keyCode,
            bubbles: true
        }));
    }

    function selectText(element) {
        if (element && element.tagName === 'INPUT') {
            element.focus();
            element.select();
        }
    }

    // Expose functions globally
    return {
        sleep,
        fetchDropdownItems,
        collectBarcodeKeys,
        addLineIfNeeded,
        isActiveElementName,
        sendKey,
        selectText,
        PREFIX

    };
});
