/** @odoo-module **/
// Copyright 2017 ACSONE SA/NV. License AGPL-3.0 or later.
import { patch } from "@web/core/utils/patch";
import { Field } from "@web/views/fields/field";

/** Keep JSON-encoded Char domain fields without changing their stored type. */
export function parseDomainField(domainExpression, record) {
    if (typeof domainExpression !== "string" || !(domainExpression in record.data)) {
        return undefined;
    }
    const value = record.data[domainExpression];
    if (!value) {
        return [];
    }
    return typeof value === "string" ? JSON.parse(value) : value;
}

patch(Field.prototype, {
    get fieldComponentProps() {
        const props = super.fieldComponentProps;
        const expression = this.props.fieldInfo?.domain ||
            this.props.record.fields[this.props.name]?.domain;
        if (typeof expression === "string" && expression in this.props.record.data) {
            props.domain = () => parseDomainField(expression, this.props.record);
        }
        return props;
    },
});
