/** @odoo-module **/

import {registry} from "@web/core/registry";
import {patch} from "@web/core/utils/patch";
import {AbEmployeeAccessLoginPanel} from "@ab_employee_access/login/employee_login";

const CashierAction = registry.category("actions").get("ab_sales.cashier");

if (CashierAction) {
    CashierAction.components = {
        ...(CashierAction.components || {}),
        AbEmployeeAccessLoginPanel,
    };

    patch(CashierAction.prototype, {
        setup() {
            super.setup(...arguments);

            this.state.loginOverlayMode = "";
            this.state.employeeAccessId = 0;
            this.state.loginEmployee = false;
            this.state.loginPin = "";
            this.state.loginError = "";
            this.state.loginLoading = false;

            this._cashierCurrentEmployeeValue = this._cashierCurrentEmployeeValue.bind(this);
            this._cashierPrepareLoginOverlayState = this._cashierPrepareLoginOverlayState.bind(this);
            this._cashierSuspendPolling = this._cashierSuspendPolling.bind(this);
            this._cashierEnterLoginOverlay = this._cashierEnterLoginOverlay.bind(this);
            this.cashierLoginPanelSubtitle = this.cashierLoginPanelSubtitle.bind(this);
            this.cashierLoginPanelEmployeeValue = this.cashierLoginPanelEmployeeValue.bind(this);
            this.cashierLoginPanelPinValue = this.cashierLoginPanelPinValue.bind(this);
            this.closeCashierLoginOverlay = this.closeCashierLoginOverlay.bind(this);
            this.submitCashierLoginPanel = this.submitCashierLoginPanel.bind(this);
            this.onCashierLoginEmployeeUpdate = this.onCashierLoginEmployeeUpdate.bind(this);
            this.cashierLoginPanelPinInput = this.cashierLoginPanelPinInput.bind(this);
            this.cashierLoginPanelPinKeydown = this.cashierLoginPanelPinKeydown.bind(this);
        },

        _cashierCurrentEmployeeValue() {
            const employeeAccessId = Number.parseInt(this.state.employeeAccessId || 0, 10) || 0;
            if (!employeeAccessId) {
                return false;
            }
            return {
                id: employeeAccessId,
                display_name: this.state.employeeName || this.state.employeeCode || `#${employeeAccessId}`,
            };
        },

        _cashierPrepareLoginOverlayState({preserveEmployee = false, employee = undefined} = {}) {
            if (employee !== undefined) {
                this.state.loginEmployee = employee;
            } else if (!preserveEmployee || !(Number.parseInt(this.state.loginEmployee?.id || 0, 10) || 0)) {
                this.state.loginEmployee = this._cashierCurrentEmployeeValue();
            }
            this.state.loginPin = "";
            this.state.loginError = "";
            this.state.loginLoading = false;
        },

        _cashierSuspendPolling() {
            if (this._pollTimer) {
                clearTimeout(this._pollTimer);
                this._pollTimer = null;
            }
            this._pollSeq += 1;
            this._pollAppliedSeq = this._pollSeq;
        },

        _cashierEnterLoginOverlay({mode = "initial", keepEmployeeContext = false, employee = undefined, clearStore = false, clearInvoices = false} = {}) {
            this._cashierSuspendPolling();
            this.state.sessionToken = "";
            this.state.sessionId = 0;
            this.state.isAuthenticated = false;
            this._persistCachedSessionToken("");
            this.state.loginOverlayMode = mode || "initial";
            if (!keepEmployeeContext) {
                this.state.employeeAccessId = 0;
                this.state.employeeId = 0;
                this.state.employeeName = "";
                this.state.employeeCode = "";
            }
            if (clearStore) {
                this.state.selectedStoreId = null;
                this.state.selectedStoreName = "";
            }
            if (clearInvoices) {
                this._clearInvoicesState();
            }
            this.state.loadingInitial = false;
            this._cashierPrepareLoginOverlayState({
                preserveEmployee: keepEmployeeContext,
                employee,
            });
        },

        _applyBootstrapPayload(payload) {
            super._applyBootstrapPayload(...arguments);
            this.state.employeeAccessId = Number.parseInt(payload?.employee_access_id || this.state.employeeAccessId || 0, 10) || 0;
            if (this.state.isAuthenticated) {
                this.state.loginOverlayMode = "";
                this._cashierPrepareLoginOverlayState({
                    employee: this._cashierCurrentEmployeeValue(),
                });
            } else {
                this._cashierPrepareLoginOverlayState({
                    preserveEmployee: true,
                });
            }
        },

        async loginWithPin({employeeAccessId, pin, storeId = false}) {
            const preferredStoreId = Number.parseInt(storeId || 0, 10) || 0;
            const payload = await this.orm.call("ab_sales_cashier_api", "cashier_pin_login", [], {
                employee_access_id: Number.parseInt(employeeAccessId || 0, 10) || false,
                pin: String(pin || "").trim(),
                device_uid: this._deviceUid(),
                device_name: this.state.deviceName || this.state.branchName || "",
            });
            this._applyBootstrapPayload(payload || {});
            this.state.selectedStoreId = null;
            this.state.selectedStoreName = "";
            this._clearInvoicesState();
            await this.loadStores();
            if (preferredStoreId && this.state.storeById?.[preferredStoreId]) {
                await this.applyStoreSelection(preferredStoreId, {refresh: false});
            } else {
                await this._applyInitialStore();
            }
            if (this.state.selectedStoreId) {
                await this.refreshPending({manual: true});
            } else {
                this.state.loadingInitial = false;
            }
            return true;
        },

        cashierLoginPanelSubtitle() {
            return "Select employee and enter PIN to access cashier screen.";
        },

        cashierLoginPanelEmployeeValue() {
            return this.state.loginEmployee || false;
        },

        cashierLoginPanelPinValue() {
            return this.state.loginPin || "";
        },

        closeCashierLoginOverlay() {
            this.closeWindow();
        },

        onCashierLoginEmployeeUpdate(value) {
            if (value && value.id) {
                this.state.loginEmployee = value;
            } else {
                this.state.loginEmployee = false;
            }
            this.state.loginError = "";
        },

        cashierLoginPanelPinInput(ev) {
            this.state.loginPin = String(ev.target.value || "");
            this.state.loginError = "";
        },

        cashierLoginPanelPinKeydown(ev) {
            if (ev.key !== "Enter") {
                return;
            }
            ev.preventDefault();
            ev.stopPropagation();
            this.submitCashierLoginPanel();
        },

        async submitCashierLoginPanel() {
            if (this.state.loginLoading) {
                return false;
            }
            const employeeAccessId = Number.parseInt(this.state.loginEmployee?.id || 0, 10) || 0;
            const pin = String(this.state.loginPin || "").trim();
            if (!employeeAccessId || !pin) {
                this.state.loginError = "Employee and PIN are required.";
                return false;
            }
            this.state.loginLoading = true;
            this.state.loginError = "";
            try {
                await this.loginWithPin({
                    employeeAccessId,
                    pin,
                    storeId: this.state.selectedStoreId || false,
                });
                return true;
            } catch (err) {
                this.state.loginError = this._rpcError(err, "PIN login failed.");
                return false;
            } finally {
                this.state.loginLoading = false;
            }
        },

        async logoutCashier() {
            const token = this.state.sessionToken || "";
            const currentEmployee = this._cashierCurrentEmployeeValue();
            try {
                if (token) {
                    await this.orm.call("ab_sales_cashier_api", "cashier_logout", [], {
                        session_token: token,
                    });
                }
            } catch {
                // Ignore logout errors and reset local state anyway.
            }
            this._cashierEnterLoginOverlay({
                mode: "initial",
                keepEmployeeContext: false,
                employee: currentEmployee,
                clearStore: true,
                clearInvoices: true,
            });
        },

        async lockCashier() {
            if (!this.state.isAuthenticated) {
                return;
            }
            this._cashierEnterLoginOverlay({
                mode: "locked",
                keepEmployeeContext: true,
                employee: this._cashierCurrentEmployeeValue(),
                clearStore: false,
                clearInvoices: false,
            });
        },

        async refreshPending({manual = false} = {}) {
            if (
                this.state.requirePinLogin
                && !this.state.sessionToken
                && this.state.loginOverlayMode === "locked"
            ) {
                this.state.loadingInitial = false;
                return;
            }
            return await super.refreshPending({manual});
        },

        onKeyDown(ev) {
            if (this.state.requirePinLogin && !this.state.isAuthenticated) {
                if (ev.key === "Escape") {
                    ev.preventDefault();
                    this.closeCashierLoginOverlay();
                }
                return;
            }
            return super.onKeyDown(...arguments);
        },
    });
}
