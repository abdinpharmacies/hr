/** @odoo-module **/

import { ListRenderer } from "@web/views/list/list_renderer";
import { patch } from "@web/core/utils/patch";

patch(ListRenderer.prototype, {
    isAbRequestInlineCreate(record) {
        return Boolean(
            record &&
            record.resModel === "ab_request" &&
            record.isNew &&
            this.props.list.editedRecord === record
        );
    },

    async onAbRequestInlineSave(record, ev) {
        ev?.stopPropagation();
        const saved = await record.save();
        if (saved) {
            await this.props.list.leaveEditMode();
        }
    },

    async onAbRequestInlineDiscard(record, ev) {
        ev?.stopPropagation();
        if (this.props.list.editedRecord === record) {
            await this.props.list.leaveEditMode({ discard: true });
        }
    },
});
