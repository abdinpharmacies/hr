/** @odoo-module **/

import { registry } from "@web/core/registry";
import { FileInput } from "@web/core/file_input/file_input";
import {
    Many2ManyBinaryField,
    many2ManyBinaryField,
} from "@web/views/fields/many2many_binary/many2many_binary_field";

export class DeliveryEvidenceFileInput extends FileInput {
    static template = "ab_internal_shipment_tracking.DeliveryEvidenceFileInput";
}

export class DeliveryEvidenceField extends Many2ManyBinaryField {
    static template = "web.Many2ManyBinaryField";
    static components = {
        FileInput: DeliveryEvidenceFileInput,
    };
}

export const deliveryEvidenceField = {
    ...many2ManyBinaryField,
    component: DeliveryEvidenceField,
};

registry.category("fields").add("ais_delivery_evidence", deliveryEvidenceField);
