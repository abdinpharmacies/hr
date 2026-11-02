import { useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { BinaryField, binaryField } from "@web/views/fields/binary/binary_field";

export class SupplierClaimUpload extends BinaryField {
    static template = "ab_supplier_claim_cycle.DocumentUpload";

    setup() {
        super.setup();
        this.orm = useService("orm");
        this.state = useState({ submitting: false });
        this.files = [];
    }

    async beforeUpload() {
        if (this.state.submitting || this.props.readonly) {
            return false;
        }
        this.files = [];
        return this.props.record.save();
    }

    onUploaded(file) {
        this.files.push({ name: file.name, data: file.data });
        if (file.objectUrl) {
            URL.revokeObjectURL(file.objectUrl);
        }
    }

    async onUploadComplete() {
        const files = this.files;
        this.files = [];
        if (!files.length) {
            return;
        }
        this.state.submitting = true;
        try {
            await this.orm.call(this.props.record.resModel, "action_upload_documents", [
                [this.props.record.resId], this.props.name, files,
            ]);
            await this.props.record.load();
        } finally {
            this.state.submitting = false;
        }
    }
}

registry.category("fields").add("supplier_claim_upload", {
    ...binaryField,
    component: SupplierClaimUpload,
});
