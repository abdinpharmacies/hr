import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { Many2OneField, buildM2OFieldDescription } from "@web/views/fields/many2one/many2one_field";
import { SelectCreateDialog } from "@web/views/view_dialogs/select_create_dialog";

export class SeoProductSelector extends Many2OneField {
    setup() {
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        this.action = useService("action");
        this.selectionSequence = 0;
    }

    get m2oProps() {
        return { ...super.m2oProps, update: (value, options) => this.selectProduct(value, options) };
    }

    async selectProduct(value, options = {}) {
        const sequence = ++this.selectionSequence;
        if (!value?.id || value.id === this.props.record.data[this.props.name]?.id) {
            return super.m2oProps.update(value, options);
        }
        const action = await this.orm.call("product.template", "action_open_existing_seo", [[value.id]], {
            context: this.props.context,
        });
        if (sequence !== this.selectionSequence) {
            return;
        }
        if (!action || action.res_id === this.props.record.resId) {
            return super.m2oProps.update(value, options);
        }
        this.dialog.add(ConfirmationDialog, {
            title: _t("SEO Record Already Exists"),
            body: _t("This product already has an SEO record, which may still be a draft. Choose another product, or open the existing record to continue."),
            confirmLabel: _t("Open Product SEO"),
            cancelLabel: _t("Back to Product List"),
            confirm: () => this.action.doAction(action),
            cancel: () => this.openProductList(),
            dismiss: () => {},
        });
    }

    openProductList() {
        this.dialog.add(SelectCreateDialog, {
            title: _t("Select a Product"),
            resModel: "product.template",
            domain: super.m2oProps.domain(),
            context: { ...this.props.context, search_default_ab_without_seo_content: 1 },
            multiSelect: false,
            noCreate: true,
            onSelected: async (ids) => {
                if (ids.length) {
                    const [product] = await this.orm.read("product.template", [ids[0]], ["display_name"], {
                        context: this.props.context,
                    });
                    await this.selectProduct(product);
                }
            },
        });
    }
}

registry.category("fields").add("ab_seo_product_selector", buildM2OFieldDescription(SeoProductSelector));
