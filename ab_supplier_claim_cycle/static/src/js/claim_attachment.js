import { Attachment } from "@mail/core/common/attachment_model";
import { patch } from "@web/core/utils/patch";

patch(Attachment.prototype, {
    get isDeletable() {
        return !this.supplier_claim_locked && super.isDeletable;
    },
});
