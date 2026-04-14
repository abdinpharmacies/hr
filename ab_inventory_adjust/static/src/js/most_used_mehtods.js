var rpc = require("web.rpc");


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

// // Wait until Perform the search
// const searchResult = await performSearch(barcode);
// // If NOT one matching result, DO NOT SEND 'TAB' key
// if (searchResult.length !== 1) return;
