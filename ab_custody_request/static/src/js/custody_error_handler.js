/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { WarningDialog } from "@web/core/errors/error_dialogs";
import { UncaughtPromiseError } from "@web/core/errors/error_service";
import { RPCError } from "@web/core/network/rpc";
import { registry } from "@web/core/registry";

export function custodyRequestErrorHandler(env, error, originalError) {
    if (
        !(error instanceof UncaughtPromiseError) ||
        !(originalError instanceof RPCError) ||
        !["ab_custody_request_header", "ab_custody_request_line"].includes(originalError.model) ||
        originalError.exceptionName !== "werkzeug.exceptions.RequestEntityTooLarge"
    ) {
        return false;
    }
    error.unhandledRejectionEvent.preventDefault();
    env.services.dialog.add(WarningDialog, {
        title: _t("Custody request too large"),
        message: _t(
            "The custody request is too large to process. Use smaller attachments or fewer detail lines, then try again."
        ),
    });
    return true;
}

registry.category("error_handlers").add("ab_custody_request_payload_error", custodyRequestErrorHandler, {
    sequence: 96,
});
