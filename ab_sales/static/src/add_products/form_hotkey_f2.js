/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";
import { useService } from "@web/core/utils/hooks";
import { useExternalListener } from "@odoo/owl";

patch(FormController.prototype, {
    setup() {
        super.setup(...arguments);
        this.abSalesAddProductsNotification = useService("notification");
        this._abSalesF2Busy = false;
        useExternalListener(
            window,
            "keydown",
            (ev) => {
                // don't block the UI thread; ignore returned promise
                this._abSalesOnKeydown(ev);
            },
            { capture: true }
        );
    },

    _abSalesGetStoreContext() {
        const storeValue = this.model?.root?.data?.store_id;
        let storeId = null;
        let storeName = "";
        if (Array.isArray(storeValue)) {
            storeId = storeValue[0];
            storeName = storeValue[1] || "";
        } else if (typeof storeValue === "number") {
            storeId = storeValue;
        }
        const ctx = {};
        if (storeId) {
            ctx.pos_store_id = storeId;
        }
        if (storeName) {
            ctx.pos_store_name = storeName;
        }
        return ctx;
    },

    async _abSalesReloadIfRequested(closeParams) {
        if (!closeParams?.ab_sales_refresh) {
            return;
        }
        // reload current record so new lines appear
        await this.model.load();
    },

    async _abSalesOnKeydown(ev) {
        if (ev.key !== "F2") {
            return;
        }
        if (document.body.classList.contains("modal-open")) {
            return;
        }
        if (this.props.resModel !== "ab_sales_header") {
            return;
        }

        ev.preventDefault();
        ev.stopPropagation();
        ev.stopImmediatePropagation();

        if (this._abSalesF2Busy) {
            return;
        }
        this._abSalesF2Busy = true;
        try {
            // Always save first so the active store (and other pending changes)
            // are applied before opening the search window.
            const saved = await this.saveButtonClicked({}); // save & stay on form
            const resId = this.model?.root?.resId;
            if (!saved || !resId) {
                return;
            }

            await this.actionService.doActionButton({
                type: "object",
                name: "action_open_add_products",
                resModel: "ab_sales_header",
                resId,
                resIds: [resId],
                context: { ...(this.props.context || {}), ...this._abSalesGetStoreContext() },
                onClose: (closeParams) => this._abSalesReloadIfRequested(closeParams),
            });
        } finally {
            this._abSalesF2Busy = false;
        }
    },

    async beforeExecuteActionButton(clickParams) {
        // Ensure Add Products opened from the form button reloads the record only
        // when the dialog is closed after applying.
        if (
            clickParams?.type === "object" &&
            clickParams?.name === "action_open_add_products" &&
            clickParams?.resModel === "ab_sales_header"
        ) {
            clickParams.onClose = (closeParams) => this._abSalesReloadIfRequested(closeParams);
            clickParams.context = { ...(clickParams.context || {}), ...this._abSalesGetStoreContext() };
        }
        return super.beforeExecuteActionButton(...arguments);
    },
});
