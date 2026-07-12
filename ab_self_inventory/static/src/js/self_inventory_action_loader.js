/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";

const LOADER_ACTIONS = {
    ab_self_inventory_request: {
        action_fetch_branch_stock: _t("Fetching branch stock"),
        action_run_inventory_analysis: _t("Running inventory analysis"),
    },
    ab_self_inventory_request_batch: {
        action_fetch_branch_stocks: _t("Fetching branch stocks"),
        action_run_inventory_analysis: _t("Running inventory analysis"),
    },
};

function getLoaderText(controller, clickParams) {
    return LOADER_ACTIONS[controller.props.resModel]?.[clickParams?.name] || "";
}

function buildLoader(text) {
    const wrapper = document.createElement("div");
    wrapper.className = "ab-batches-overlay-fixed ab-batches-overlay-fixed--visible ab-self-inventory-action-loader";
    wrapper.innerHTML = `
        <div class="ab-batches-loading-overlay">
            <div class="ab-batches-overlay-backdrop"></div>
            <div class="ab-batches-overlay-content">
                <div class="ab-batches-loader">
                    <div class="ab-batches-spinner"></div>
                    <div class="ab-batches-loader-text"></div>
                </div>
            </div>
        </div>
    `;
    wrapper.querySelector(".ab-batches-loader-text").textContent = text;
    return wrapper;
}

patch(FormController.prototype, {
    async beforeExecuteActionButton(clickParams) {
        const loaderText = getLoaderText(this, clickParams);
        if (loaderText) {
            this._abSelfInventoryShowActionLoader(loaderText);
        }
        let canExecute;
        try {
            canExecute = await super.beforeExecuteActionButton(...arguments);
        } catch (error) {
            if (loaderText) {
                this._abSelfInventoryHideActionLoader();
            }
            throw error;
        }
        if (canExecute === false) {
            if (loaderText) {
                this._abSelfInventoryHideActionLoader();
            }
            return canExecute;
        }
        return canExecute;
    },

    async afterExecuteActionButton(clickParams) {
        try {
            return await super.afterExecuteActionButton(...arguments);
        } finally {
            if (getLoaderText(this, clickParams)) {
                this._abSelfInventoryHideActionLoader();
            }
        }
    },

    _abSelfInventoryShowActionLoader(text) {
        this._abSelfInventoryLoaderDepth = (this._abSelfInventoryLoaderDepth || 0) + 1;
        if (this._abSelfInventoryLoaderEl) {
            const label = this._abSelfInventoryLoaderEl.querySelector(".ab-batches-loader-text");
            if (label) {
                label.textContent = text;
            }
            return;
        }
        this._abSelfInventoryLoaderEl = buildLoader(text);
        document.body.appendChild(this._abSelfInventoryLoaderEl);
    },

    _abSelfInventoryHideActionLoader() {
        this._abSelfInventoryLoaderDepth = Math.max((this._abSelfInventoryLoaderDepth || 1) - 1, 0);
        if (this._abSelfInventoryLoaderDepth || !this._abSelfInventoryLoaderEl) {
            return;
        }
        this._abSelfInventoryLoaderEl.remove();
        this._abSelfInventoryLoaderEl = null;
    },
});
