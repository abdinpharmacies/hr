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
            const hasLetters = /[A-Za-z\u0600-\u06FF]/;
            const hasAnyDraft = Boolean(title || description);
            const hasPartialDraft = Boolean(title) !== Boolean(description);
            const hasInvalidNumericOnlyDraft =
                hasAnyDraft &&
                ((!title || !hasLetters.test(title)) || (!description || !hasLetters.test(description)));

            if (hasPartialDraft || hasInvalidNumericOnlyDraft || !hasAnyDraft) {
                const body = !hasAnyDraft
                    ? _t("There is no valid issue content yet. Do you want to discard and return to the issues screen, or continue editing?")
                    : _t("The issue draft is incomplete or invalid. Do you want to continue editing, or discard the draft and return to the issues screen?");
                const shouldDiscard = await new Promise((resolve) => {
                    this.dialogService.add(ConfirmationDialog, {
                        body,
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
