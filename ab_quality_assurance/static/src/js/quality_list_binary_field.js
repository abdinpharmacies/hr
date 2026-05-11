/** @odoo-module **/

import { registry } from "@web/core/registry";
import { BinaryField, binaryField } from "@web/views/fields/binary/binary_field";

export class QualityListBinaryField extends BinaryField {
    static template = "ab_quality_assurance.QualityListBinaryField";
    static components = BinaryField.components;

    get canUpload() {
        return Boolean(this.props.record.data.can_upload_attachment);
    }
}

export const qualityListBinaryField = {
    ...binaryField,
    component: QualityListBinaryField,
};

registry.category("fields").add("qa_list_binary", qualityListBinaryField);
