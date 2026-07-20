/** @odoo-module **/

import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { BinaryField, binaryField } from "@web/views/fields/binary/binary_field";
import { X2ManyField, x2ManyField } from "@web/views/fields/x2many/x2many_field";

const MIME_PREFIX_RULES = {
    "image/*": "image/",
    "video/*": "video/",
    "audio/*": "audio/",
};
const POWERPOINT_EXTENSIONS = new Set([
    ".ppt",
    ".pptx",
    ".pps",
    ".ppsx",
    ".pot",
    ".potx",
    ".pptm",
    ".ppsm",
    ".potm",
]);

export class TrainingMaterialBinaryField extends BinaryField {
    static template = "ab_training_tasks.TrainingMaterialBinaryField";
    static components = BinaryField.components;
    static props = {
        ...BinaryField.props,
        acceptedExtensionsField: { type: String, optional: true },
    };

    get acceptedFileExtensions() {
        const fieldName = this.props.acceptedExtensionsField || "accepted_file_extensions";
        return this.props.record.data[fieldName] || ".no-training-material-type";
    }

    isFileAllowed({ name = "", type = "" }) {
        const rules = this.acceptedFileExtensions
            .split(",")
            .map((rule) => rule.trim().toLowerCase())
            .filter(Boolean);
        const mimeType = type.toLowerCase();
        const fileName = name.toLowerCase();
        const extension = fileName.includes(".") ? `.${fileName.split(".").pop()}` : "";

        for (const [rule, mimePrefix] of Object.entries(MIME_PREFIX_RULES)) {
            if (mimeType.startsWith(mimePrefix)) {
                return rules.includes(rule);
            }
        }
        if (mimeType === "application/pdf") {
            return rules.includes(".pdf");
        }
        if (mimeType.includes("powerpoint") || mimeType.includes("presentationml")) {
            return rules.some((rule) => POWERPOINT_EXTENSIONS.has(rule));
        }
        if (mimeType && !["application/octet-stream", "application/zip"].includes(mimeType)) {
            return false;
        }

        return (
            (extension === ".pdf" && rules.includes(extension))
            || (POWERPOINT_EXTENSIONS.has(extension) && rules.includes(extension))
        );
    }

    async update(fileInfo) {
        if (fileInfo.data && !this.isFileAllowed(fileInfo)) {
            this.notification.add(
                _t("The selected file type is not allowed for this material category."),
                { type: "danger" }
            );
            return;
        }
        return super.update(fileInfo);
    }
}

export const trainingMaterialBinaryField = {
    ...binaryField,
    component: TrainingMaterialBinaryField,
    extractProps: (params) => ({
        ...binaryField.extractProps(params),
        acceptedExtensionsField: params.options.accepted_field || "accepted_file_extensions",
    }),
};

registry.category("fields").add("training_material_binary", trainingMaterialBinaryField);

export class TrainingMaterialOne2ManyField extends X2ManyField {
    async onAdd({ context = {} } = {}) {
        const parentRecord = this.props.record;
        if (!parentRecord.resId) {
            this.notificationService.add(
                _t("Save the training task before uploading files."),
                { type: "warning" }
            );
            return;
        }
        if (!(await parentRecord.save())) {
            return;
        }

        const actionContext = {
            ...this.props.context,
            ...context,
            form_view_ref: "ab_training_tasks.view_training_material_upload_form",
            default_task_id: parentRecord.resId,
            default_accepted_file_extensions: parentRecord.data.allowed_file_extensions,
        };
        return this.action.doAction(
            {
                type: "ir.actions.act_window",
                name: _t("Upload Training Material"),
                res_model: "ab.training.material",
                views: [[false, "form"]],
                target: "new",
                context: actionContext,
            },
            {
                onClose: () => parentRecord._load(),
            }
        );
    }
}

export const trainingMaterialOne2ManyField = {
    ...x2ManyField,
    component: TrainingMaterialOne2ManyField,
};

registry.category("fields").add(
    "training_material_one2many",
    trainingMaterialOne2ManyField
);
