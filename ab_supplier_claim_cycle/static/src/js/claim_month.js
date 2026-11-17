import { useSubEnv } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { formatDate } from "@web/core/l10n/dates";
import { DateTimeField, dateField } from "@web/views/fields/datetime/datetime_field";

const ISO_DATE_FORMAT = "yyyy-MM-dd";

// Reuse the standard date field and calendar. Scope its input format to this
// component rather than changing the language or the shared picker service.
export class SupplierClaimMonth extends DateTimeField {
    setup() {
        const pickerService = this.env.services.datetime_picker;
        useSubEnv({
            services: {
                ...this.env.services,
                datetime_picker: {
                    ...pickerService,
                    create(params) {
                        return pickerService.create(
                            Object.assign(Object.create(params), { format: ISO_DATE_FORMAT })
                        );
                    },
                },
            },
        });
        super.setup();
    }

    getFormattedValue(valueIndex) {
        const value = this.values[valueIndex];
        return value ? formatDate(value, { format: ISO_DATE_FORMAT }) : "";
    }
}

registry.category("fields").add("supplier_claim_month", {
    ...dateField,
    component: SupplierClaimMonth,
    extractProps: (...args) => ({
        ...dateField.extractProps(...args),
        numeric: true,
        placeholder: "YYYY-MM-DD",
    }),
});
