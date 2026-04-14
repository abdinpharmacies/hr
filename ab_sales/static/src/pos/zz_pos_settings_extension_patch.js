/** @odoo-module **/

import {Component, useState} from "@odoo/owl";
import {Dialog} from "@web/core/dialog/dialog";
import {registry} from "@web/core/registry";
import {patch} from "@web/core/utils/patch";

class AbSalesPosSettingsDialog extends Component {
    static template = "ab_sales.PosSettingsDialog";
    static components = {Dialog};
    static props = {
        settings: {type: Object, optional: true},
        onApply: Function,
        close: Function,
    };

    setup() {
        const settings = this.props.settings || {};
        this.state = useState({
            productHasBalanceOnly: settings.productHasBalanceOnly !== false,
            productHasPosBalanceOnly: settings.productHasPosBalanceOnly !== false,
            enableProductSearchKeyboardMapping: settings.enableProductSearchKeyboardMapping !== false,
            enableAbMany2oneKeyboardMapping: settings.enableAbMany2oneKeyboardMapping !== false,
            saving: false,
        });

        this.onProductHasBalanceOnlyChange = this.onProductHasBalanceOnlyChange.bind(this);
        this.onProductHasPosBalanceOnlyChange = this.onProductHasPosBalanceOnlyChange.bind(this);
        this.onEnableProductSearchKeyboardMappingChange = this.onEnableProductSearchKeyboardMappingChange.bind(this);
        this.onEnableAbMany2oneKeyboardMappingChange = this.onEnableAbMany2oneKeyboardMappingChange.bind(this);
        this.save = this.save.bind(this);
        this.cancel = this.cancel.bind(this);
    }

    onProductHasBalanceOnlyChange(ev) {
        this.state.productHasBalanceOnly = !!ev.target.checked;
    }

    onProductHasPosBalanceOnlyChange(ev) {
        this.state.productHasPosBalanceOnly = !!ev.target.checked;
    }

    onEnableProductSearchKeyboardMappingChange(ev) {
        this.state.enableProductSearchKeyboardMapping = !!ev.target.checked;
    }

    onEnableAbMany2oneKeyboardMappingChange(ev) {
        this.state.enableAbMany2oneKeyboardMapping = !!ev.target.checked;
    }

    async save() {
        if (this.state.saving) {
            return;
        }
        this.state.saving = true;
        try {
            await this.props.onApply({
                productHasBalanceOnly: !!this.state.productHasBalanceOnly,
                productHasPosBalanceOnly: !!this.state.productHasPosBalanceOnly,
                enableProductSearchKeyboardMapping: !!this.state.enableProductSearchKeyboardMapping,
                enableAbMany2oneKeyboardMapping: !!this.state.enableAbMany2oneKeyboardMapping,
            });
            this.props.close();
        } finally {
            this.state.saving = false;
        }
    }

    cancel() {
        this.props.close();
    }
}

const PosAction = registry.category("actions").get("ab_sales.pos");

if (PosAction) {
    patch(PosAction.prototype, {
        setup() {
            super.setup(...arguments);
            this.openPosSettingsDialog = this.openPosSettingsDialog.bind(this);
            this._savePosSettingsFromDialog = this._savePosSettingsFromDialog.bind(this);
            const initialSettings = this._loadPosUiSettingsLocal();
            if (typeof this.state.enableProductSearchKeyboardMapping !== "boolean") {
                this.state.enableProductSearchKeyboardMapping =
                    initialSettings.enableProductSearchKeyboardMapping !== false;
            }
            if (typeof this.state.enableAbMany2oneKeyboardMapping !== "boolean") {
                this.state.enableAbMany2oneKeyboardMapping =
                    initialSettings.enableAbMany2oneKeyboardMapping !== false;
            }
        },

        _defaultPosUiSettings() {
            const defaults = super._defaultPosUiSettings(...arguments);
            return {
                ...defaults,
                enableProductSearchKeyboardMapping: true,
                enableAbMany2oneKeyboardMapping: true,
            };
        },

        _normalizePosUiSettings(payload) {
            const normalized = super._normalizePosUiSettings(payload);
            const defaults = this._defaultPosUiSettings();
            const raw = payload && typeof payload === "object" ? payload : {};
            return {
                ...normalized,
                enableProductSearchKeyboardMapping:
                    typeof raw.enableProductSearchKeyboardMapping === "boolean"
                        ? raw.enableProductSearchKeyboardMapping
                        : (
                            typeof normalized.enableProductSearchKeyboardMapping === "boolean"
                                ? normalized.enableProductSearchKeyboardMapping
                                : defaults.enableProductSearchKeyboardMapping
                        ),
                enableAbMany2oneKeyboardMapping:
                    typeof raw.enableAbMany2oneKeyboardMapping === "boolean"
                        ? raw.enableAbMany2oneKeyboardMapping
                        : (
                            typeof normalized.enableAbMany2oneKeyboardMapping === "boolean"
                                ? normalized.enableAbMany2oneKeyboardMapping
                                : defaults.enableAbMany2oneKeyboardMapping
                        ),
            };
        },

        _currentPosUiSettings() {
            const current = super._currentPosUiSettings(...arguments);
            return this._normalizePosUiSettings({
                ...current,
                enableProductSearchKeyboardMapping: this.state.enableProductSearchKeyboardMapping !== false,
                enableAbMany2oneKeyboardMapping: this.state.enableAbMany2oneKeyboardMapping !== false,
            });
        },

        _applyPosUiSettings(payload, persistLocal = true) {
            const settings = super._applyPosUiSettings(payload, persistLocal);
            this.state.enableProductSearchKeyboardMapping = settings.enableProductSearchKeyboardMapping !== false;
            this.state.enableAbMany2oneKeyboardMapping = settings.enableAbMany2oneKeyboardMapping !== false;
            return settings;
        },

        openPosSettingsDialog() {
            this.dialog.add(AbSalesPosSettingsDialog, {
                settings: this._currentPosUiSettings(),
                onApply: async (nextSettings) => {
                    await this._savePosSettingsFromDialog(nextSettings);
                },
            });
        },

        async _savePosSettingsFromDialog(nextSettings) {
            this._applyPosUiSettings(nextSettings, true);
            await this.savePosUiSettings();
            await this.searchProducts((this.state.productQuery || "").trim());
        },
    });
}
