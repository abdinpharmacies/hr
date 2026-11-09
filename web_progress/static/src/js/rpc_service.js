/** @odoo-module **/

import { download } from "@web/core/network/download";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";

// -----------------------------------------------------------------------------
// download adapted to handle progress reporting
// -----------------------------------------------------------------------------

const org_download = download._download;

// Keep the local attachment-download fix when using the upstream 19.0 addon.
export function parseProgressPayload(value) {
    if (typeof value === "string") {
        try {
            value = JSON.parse(value);
        } catch {
            return null;
        }
    }
    return value && typeof value === "object" ? value : null;
}

function _download(options) {
    const blockUI = registry.category("main_components").get("BlockUI");
    const values = options.data;
    let context;
    if (values?.context) {
        context = parseProgressPayload(values.context);
        if (context) {
            context.progress_code ||= pseudoUuid();
            values.context = JSON.stringify(context);
        }
    } else if (values?.data) {
        const payload = parseProgressPayload(values.data);
        if (payload) {
            if (Array.isArray(payload)) {
                context = payload.at(-1);
                if (!context || typeof context !== "object" || Array.isArray(context)) {
                    context = {};
                    payload.push(context);
                }
            } else {
                context = payload.context ||= {};
            }
            context.progress_code ||= pseudoUuid();
            values.data = JSON.stringify(payload);
        }
    }
    if (!context?.progress_code) {
        // Binary and non-JSON downloads must pass through without JSON parsing errors.
        return org_download(options);
    }
    blockUI.props.bus.trigger("BLOCK", { progressCode: context.progress_code });
    return org_download(options).finally(() => blockUI.props.bus.trigger("UNBLOCK", {}));
}

download._download = _download;

// -----------------------------------------------------------------------------
// RPC function with progress code
// -----------------------------------------------------------------------------

function pseudoUuid(a) {
    return a ? (a ^ Math.random() * 16 >> a / 4).toString(16) : ([1e7] + -1e3 + -4e3 + -8e3 + -1e11).replace(/[018]/g, pseudoUuid)
}

function findContext(params) {
    var ret = false;
    if ('context' in params) {
        ret = params.context;
    } else if ('kwargs' in params) {
        if ('context' in params.kwargs) {
            ret = params.kwargs.context;
        }
    } else if ('args' in params && params.args.length > 0) {
        ret = params.args[params.args.length - 1];
    }
    return ret;
}

// Store the original rpc function
const originalRpc = rpc._rpc;

// Override the internal _rpc function to add progress code support
rpc._rpc = function (url, params = {}, settings = {}) {
    // Find and update context with progress code
    var context = findContext(params);
    if (context && !context?.progress_code) {
        // Generate progress code
        context.progress_code =  pseudoUuid();
    }

    // Call the original RPC function (don't modify settings - Odoo 19 validates them strictly)
    return originalRpc.call(this, url, params, settings);
};
