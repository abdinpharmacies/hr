/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { X2ManyFieldDialog } from "@web/views/fields/relational_utils";
import { FloatField } from "@web/views/fields/float/float_field";
import { FormController } from "@web/views/form/form_controller";

function isQualityVisitForm(controller) {
    return controller.props.resModel === "ab_quality_assurance_visit";
}

function isSubmittedVisit(controller) {
    return controller.model?.root?.data?.state === "submitted";
}

async function saveQualityVisitDraft(controller) {
    return controller.save({
        reload: false,
        onError: (error, options) => controller.onSaveError(error, options, true),
    });
}

function buildScoreSummary(record) {
    const sectionRecords = record.data.visit_section_ids?.records || [];
    let earnedTotal = 0;
    let maxTotal = 0;
    const summaryLines = [
        `${_t("Department")}: ${record.data.department_id?.display_name || "-"}`,
        `${_t("Visit Date")}: ${record.data.visit_date || "-"}`,
        `${_t("Visited By")}: ${record.data.employee_id?.display_name || "-"}`,
        "",
        _t("Sections"),
    ];

    for (const section of sectionRecords) {
        const lines = section.data.visit_line_ids?.records || [];
        let sectionEarned = 0;
        let sectionMax = 0;

        summaryLines.push(`${_t("Section")}: ${section.data.name || section.data.section_id?.display_name || "-"}`);

        for (const line of lines) {
            const score = Number(line.data.score || 0);
            const maxScore = Number(line.data.max_score || 0);
            const percentage = maxScore ? (score / maxScore) * 100 : 0;

            sectionEarned += score;
            sectionMax += maxScore;
            earnedTotal += score;
            maxTotal += maxScore;

            summaryLines.push(
                `- ${line.data.title || line.data.standard_id?.display_name || _t("Standard")}: ` +
                    `${score}/${maxScore} | ` +
                    `${_t("Percentage")}: ${percentage.toFixed(2)}%`
            );
        }

        const sectionPercentage = sectionMax ? (sectionEarned / sectionMax) * 100 : 0;
        summaryLines.push(`${_t("Section Total")}: ${sectionEarned}/${sectionMax} | ${sectionPercentage.toFixed(2)}%`);
        summaryLines.push("");
    }

    const totalPercentage = maxTotal ? (earnedTotal / maxTotal) * 100 : 0;
    summaryLines.push(`${_t("Earned Score")}: ${earnedTotal}`);
    summaryLines.push(`${_t("Max Score")}: ${maxTotal}`);
    summaryLines.push(`${_t("Total Percentage")}: ${totalPercentage.toFixed(2)}%`);
    summaryLines.push("");
    summaryLines.push(_t("Do you want to submit this visit?"));
    return summaryLines.join("\n");
}

patch(FormController.prototype, {
    beforeVisibilityChange() {
        if (!isQualityVisitForm(this) || isSubmittedVisit(this)) {
            return super.beforeVisibilityChange(...arguments);
        }
        if (document.visibilityState === "hidden" && this.formInDialog === 0) {
            return saveQualityVisitDraft(this);
        }
    },

    async beforeLeave({ forceLeave } = {}) {
        if (!isQualityVisitForm(this)) {
            return super.beforeLeave(...arguments);
        }

        if (isSubmittedVisit(this)) {
            return super.beforeLeave(...arguments);
        }

        if (this.model.root.dirty && !forceLeave) {
            return saveQualityVisitDraft(this);
        }
    },

    async beforeUnload(ev) {
        if (!isQualityVisitForm(this) || isSubmittedVisit(this)) {
            return super.beforeUnload(...arguments);
        }

        const succeeded = await this.model.root.urgentSave();
        if (!succeeded) {
            ev.preventDefault();
            ev.returnValue = _t("Unsaved changes");
        }
    },

    async beforeExecuteActionButton(clickParams) {
        if (
            !isQualityVisitForm(this) ||
            clickParams.type !== "object" ||
            clickParams.name !== "action_submit_visit"
        ) {
            return super.beforeExecuteActionButton(...arguments);
        }

        this.dialogService.add(ConfirmationDialog, {
            title: _t("Confirm Visit Submission"),
            body: buildScoreSummary(this.model.root),
            confirmLabel: _t("Submit Visit"),
            confirm: async () => {
                const saved = await this.save({ reload: false });
                if (!saved || !this.model.root.resId) {
                    return false;
                }
                await this.orm.call(this.props.resModel, "action_submit_visit", [[this.model.root.resId]]);
                await this.model.load({ resId: this.model.root.resId, mode: "readonly" });
            },
            cancelLabel: _t("Cancel"),
            cancel: () => {},
        });
        return false;
    },
});

function isQualityVisitDialog(dialog) {
    const model = dialog.props.record?.resModel;
    return (
        model === "ab_quality_assurance_visit_section" ||
        model === "ab_quality_assurance_visit_line"
    );
}

function isQualityScoreField(field) {
    return (
        field.props?.record?.resModel === "ab_quality_assurance_visit_line" &&
        field.props?.name === "score"
    );
}

patch(X2ManyFieldDialog.prototype, {
    setup() {
        super.setup(...arguments);
        if (isQualityVisitDialog(this)) {
            this.canCreate = false;
        }
    },
});

patch(FloatField.prototype, {
    setup() {
        super.setup(...arguments);
        this.notificationService = useService("notification");
    },

    parse(value) {
        const parsedValue = super.parse(...arguments);
        if (!isQualityScoreField(this) || value === "" || value === false || value === null) {
            return parsedValue;
        }

        const maxScore = Number(this.props?.record?.data?.max_score || 0);
        if (Number.isNaN(parsedValue) || (maxScore && (parsedValue < 0 || parsedValue > maxScore))) {
            this.notificationService.add(_t("Score must be between 0 and the standard maximum score."), {
                type: "danger",
            });
            throw new Error("Invalid quality score");
        }

        return parsedValue;
    },
});
