/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";

patch(FormController.prototype, {
    async beforeLeave(options = {}) {
        const root = this.model?.root;
        if (
            root &&
            root.resModel === "hr.employee.feedback" &&
            root.dirty &&
            !options.forceLeave
        ) {
            const title = (root.data.name || "").trim();
            const description = (root.data.description || "").trim();
            const hasPartialDraft = Boolean(title) !== Boolean(description);
            if (hasPartialDraft) {
                const shouldDiscard = await new Promise((resolve) => {
                    this.dialogService.add(ConfirmationDialog, {
                        body: _t(
                            "You entered only part of the issue details. Do you want to continue editing, or discard the draft and return to the issues screen?"
                        ),
                        confirmLabel: _t("Discard Changes"),
                        cancelLabel: _t("Continue Editing"),
                        confirmClass: "btn-danger",
                        confirm: () => resolve(true),
                        cancel: () => resolve(false),
                    });
                });
                if (!shouldDiscard) {
                    return false;
                }
                await this.discard();
                return true;
            }
        }
        return super.beforeLeave(options);
    },
});
