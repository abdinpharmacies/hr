/** @odoo-module **/

import { registry } from "@web/core/registry";
import { BadgeField, badgeField } from "@web/views/fields/badge/badge_field";

export class AbOdooSyncStatusBadgeField extends BadgeField {
    get badgeClass() {
        if (this.props.record.data[this.props.name] === "partially_applied") {
            return "o_ab_odoo_sync_status_partially_applied";
        }
        return super.badgeClass;
    }
}

export const abOdooSyncStatusBadgeField = {
    ...badgeField,
    component: AbOdooSyncStatusBadgeField,
};

registry.category("fields").add("ab_odoo_sync_status_badge", abOdooSyncStatusBadgeField);
