/** @odoo-module **/

import {registry} from "@web/core/registry";
import {patch} from "@web/core/utils/patch";

const BillWizardAction = registry.category("actions").get("ab_sales.bill_wizard");

const normalizeSelection = (value) => Array.isArray(value) ? value : [];

if (BillWizardAction) {
    patch(BillWizardAction.prototype, {
        setup() {
            super.setup(...arguments);
            if (!Object.prototype.hasOwnProperty.call(this.state.filters, "doctorSelection")) {
                this.state.filters.doctorSelection = [];
            }
            this.onDoctorSelectionUpdate = this.onDoctorSelectionUpdate.bind(this);
            this.doctorSelectionDomain = this.doctorSelectionDomain.bind(this);
        },

        _searchPayload(page = null) {
            const payload = super._searchPayload(...arguments);
            payload.doctor_ids = normalizeSelection(this.state.filters.doctorSelection)
                .map((row) => parseInt(row?.id || 0, 10) || 0)
                .filter((id) => id > 0);
            return payload;
        },

        onDoctorSelectionUpdate(value) {
            this.state.filters.doctorSelection = normalizeSelection(value);
        },

        doctorSelectionDomain() {
            const ids = normalizeSelection(this.state.filters.doctorSelection)
                .map((row) => parseInt(row?.id || 0, 10) || 0)
                .filter((id) => id > 0);
            return ids.length ? [["id", "not in", ids]] : [];
        },

        async resetFilters() {
            if (this.state.filters) {
                this.state.filters.doctorSelection = [];
            }
            return super.resetFilters(...arguments);
        },
    });
}
