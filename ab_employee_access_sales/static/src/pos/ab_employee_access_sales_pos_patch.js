/** @odoo-module **/

import {onMounted, onWillStart, onWillUnmount} from "@odoo/owl";
import {registry} from "@web/core/registry";
import {patch} from "@web/core/utils/patch";
import {session} from "@web/session";
import {AbEmployeeAccessLoginPanel} from "@ab_employee_access/login/employee_login";

const PosAction = registry.category("actions").get("ab_sales.pos");

const POS_HR_SESSION_KEY = `ab_employee_access_sales_pos_session_${session.user_id || 0}`;
const POS_HR_DEVICE_KEY = `ab_employee_access_sales_pos_device_${session.user_id || 0}`;

function makeDeviceUid() {
    try {
        const raw = localStorage.getItem(POS_HR_DEVICE_KEY);
        if (raw) {
            return raw;
        }
        const generated = `pos_device_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;
        localStorage.setItem(POS_HR_DEVICE_KEY, generated);
        return generated;
    } catch {
        return `pos_device_${session.user_id || 0}`;
    }
}

function makeDeviceName() {
    const nav = globalThis.navigator || {};
    const platform = nav.userAgentData?.platform || nav.platform || "";
    const agent = nav.userAgent || "";
    const value = [platform, agent].filter(Boolean).join(" / ").trim();
    return value || "POS Terminal";
}

if (PosAction) {
    PosAction.components = {
        ...(PosAction.components || {}),
        AbEmployeeAccessLoginPanel,
    };

    patch(PosAction.prototype, {
        setup() {
            super.setup(...arguments);

            this._abSalesHrDeviceUid = makeDeviceUid();
            this._abSalesHrHeartbeatTimer = null;
            this._abSalesHrDeviceName = makeDeviceName();

            this.state.abSalesHr = {
                loading: true,
                session: false,
                requireLogin: true,
                selectedStoreId: 0,
                allowedStoreIds: [],
                employeeAccessId: 0,
                employeeId: 0,
                employee: false,
                pin: "",
                unlockPin: "",
                error: "",
            };

            this._abSalesHrLoadCachedSession = this._abSalesHrLoadCachedSession.bind(this);
            this._abSalesHrSaveCachedSession = this._abSalesHrSaveCachedSession.bind(this);
            this._abSalesHrClearCachedSession = this._abSalesHrClearCachedSession.bind(this);
            this._abSalesHrBootstrap = this._abSalesHrBootstrap.bind(this);
            this._abSalesHrApplySession = this._abSalesHrApplySession.bind(this);
            this._abSalesHrSessionToken = this._abSalesHrSessionToken.bind(this);
            this._abSalesHrPermissions = this._abSalesHrPermissions.bind(this);
            this._abSalesHrIsLocked = this._abSalesHrIsLocked.bind(this);
            this._abSalesHrEnsureActiveSession = this._abSalesHrEnsureActiveSession.bind(this);
            this._abSalesHrStoreOptions = this._abSalesHrStoreOptions.bind(this);
            this.abSalesHrStoreValue = this.abSalesHrStoreValue.bind(this);
            this.abSalesHrStoreDomain = this.abSalesHrStoreDomain.bind(this);
            this.abSalesHrEmployeeValue = this.abSalesHrEmployeeValue.bind(this);
            this.abSalesHrEmployeeDomain = this.abSalesHrEmployeeDomain.bind(this);
            this.abSalesHrLoginPanelSubtitle = this.abSalesHrLoginPanelSubtitle.bind(this);
            this.abSalesHrLoginPanelEmployeeValue = this.abSalesHrLoginPanelEmployeeValue.bind(this);
            this.abSalesHrLoginPanelPinValue = this.abSalesHrLoginPanelPinValue.bind(this);
            this.abSalesHrLoginPanelShowEmployee = this.abSalesHrLoginPanelShowEmployee.bind(this);
            this.abSalesHrLoginPanelSubmitLabel = this.abSalesHrLoginPanelSubmitLabel.bind(this);
            this.abSalesHrLoginPanelLoadingLabel = this.abSalesHrLoginPanelLoadingLabel.bind(this);
            this.abSalesHrLoginPanelInputName = this.abSalesHrLoginPanelInputName.bind(this);
            this.abSalesHrLoginPanelSubmit = this.abSalesHrLoginPanelSubmit.bind(this);
            this.abSalesHrLoginPanelPinInput = this.abSalesHrLoginPanelPinInput.bind(this);
            this.abSalesHrLoginPanelPinKeydown = this.abSalesHrLoginPanelPinKeydown.bind(this);
            this.abSalesHrLockedLogin = this.abSalesHrLockedLogin.bind(this);
            this._abSalesHrScheduleTimers = this._abSalesHrScheduleTimers.bind(this);
            this._abSalesHrClearTimers = this._abSalesHrClearTimers.bind(this);
            this._abSalesHrChangeStore = this._abSalesHrChangeStore.bind(this);
            this._abSalesHrLogOperation = this._abSalesHrLogOperation.bind(this);
            this.canOpenReturnScreen = this.canOpenReturnScreen.bind(this);
            this.openReturnWindow = this.openReturnWindow.bind(this);
            this.onAbSalesHrStoreChange = this.onAbSalesHrStoreChange.bind(this);
            this.onAbSalesHrStoreUpdate = this.onAbSalesHrStoreUpdate.bind(this);
            this.onAbSalesHrEmployeeUpdate = this.onAbSalesHrEmployeeUpdate.bind(this);
            this.onAbSalesHrPinInput = this.onAbSalesHrPinInput.bind(this);
            this.onAbSalesHrPinKeydown = this.onAbSalesHrPinKeydown.bind(this);
            this.onAbSalesHrUnlockPinInput = this.onAbSalesHrUnlockPinInput.bind(this);
            this.abSalesHrLogin = this.abSalesHrLogin.bind(this);
            this.abSalesHrUnlock = this.abSalesHrUnlock.bind(this);
            this.abSalesHrLock = this.abSalesHrLock.bind(this);
            this.abSalesHrLogout = this.abSalesHrLogout.bind(this);
            this.abSalesHrClosePopup = this.abSalesHrClosePopup.bind(this);

            if (!this._abSalesHrOrmWrapped) {
                const rawCall = this.orm.call.bind(this.orm);
                this.orm.call = async (model, method, args = [], kwargs = {}) => {
                    if (model === "ab_sales_pos_api" && method === "pos_submit" && kwargs && typeof kwargs === "object") {
                        kwargs = {
                            ...kwargs,
                            pos_hr_session_token: this._abSalesHrSessionToken(),
                        };
                    }
                    return rawCall(model, method, args, kwargs);
                };
                this._abSalesHrOrmWrapped = true;
            }

            onWillStart(async () => {
                await this._abSalesHrBootstrap();
            });

            onMounted(() => {
                this._abSalesHrScheduleTimers();
            });

            onWillUnmount(() => {
                this._abSalesHrClearTimers();
            });
        },

        _abSalesHrLoadCachedSession() {
            try {
                const raw = localStorage.getItem(POS_HR_SESSION_KEY);
                return raw ? JSON.parse(raw) : {};
            } catch {
                return {};
            }
        },

        _abSalesHrSaveCachedSession(payload) {
            try {
                localStorage.setItem(POS_HR_SESSION_KEY, JSON.stringify(payload || {}));
            } catch {
                // Ignore local storage failures.
            }
        },

        _abSalesHrClearCachedSession() {
            try {
                localStorage.removeItem(POS_HR_SESSION_KEY);
            } catch {
                // Ignore local storage failures.
            }
        },

        _abSalesHrSessionToken() {
            return this.state.abSalesHr?.session?.token || "";
        },

        _abSalesHrPermissions() {
            return this.state.abSalesHr?.session?.permissions || {};
        },

        _abSalesHrIsLocked() {
            return this.state.abSalesHr?.session?.state === "locked";
        },

        canOpenReturnScreen() {
            const permissions = this._abSalesHrPermissions();
            return !!permissions.allow_return_screen;
        },

        _abSalesHrStoreOptions() {
            const allowedIds = this.state.abSalesHr?.allowedStoreIds || [];
            if (!allowedIds.length) {
                return this.state.stores || [];
            }
            return (this.state.stores || []).filter((store) => allowedIds.includes(store.id));
        },

        abSalesHrStoreValue() {
            const storeId = parseInt(this.state.abSalesHr?.selectedStoreId || 0, 10) || 0;
            if (!storeId) {
                return false;
            }
            const store = (this.state.stores || []).find((row) => row.id === storeId);
            if (!store) {
                return false;
            }
            return {
                id: store.id,
                display_name: store.name || store.code || "",
            };
        },

        abSalesHrStoreDomain() {
            const allowedIds = this.state.abSalesHr?.allowedStoreIds || [];
            const domain = [["allow_sale", "=", true]];
            if (allowedIds.length) {
                domain.push(["id", "in", allowedIds]);
            }
            return domain;
        },

        abSalesHrEmployeeValue() {
            const employeeAccessId = parseInt(
                this.state.abSalesHr?.employee?.id || this.state.abSalesHr?.employeeAccessId || 0,
                10
            ) || 0;
            if (!employeeAccessId) {
                return false;
            }
            return {
                id: employeeAccessId,
                display_name: this.state.abSalesHr?.employee?.display_name
                    || this.state.abSalesHr?.session?.employee?.name
                    || "",
            };
        },

        abSalesHrEmployeeDomain() {
            return [["pos_allow_login", "=", true]];
        },

        abSalesHrLoginPanelSubtitle() {
            if (this.state.abSalesHr.loading) {
                return "Loading POS HR...";
            }
            return "Select employee and enter PIN on the branch service user session.";
        },

        abSalesHrLoginPanelEmployeeValue() {
            return this.abSalesHrEmployeeValue();
        },

        abSalesHrLoginPanelPinValue() {
            return this._abSalesHrIsLocked() ? this.state.abSalesHr.unlockPin : this.state.abSalesHr.pin;
        },

        abSalesHrLoginPanelShowEmployee() {
            return true;
        },

        abSalesHrLoginPanelSubmitLabel() {
            return "Employee Login";
        },

        abSalesHrLoginPanelLoadingLabel() {
            return "Signing in...";
        },

        abSalesHrLoginPanelInputName() {
            return this._abSalesHrIsLocked()
                ? "ab_employee_access_sales_unlock_pin"
                : "ab_employee_access_sales_pin";
        },

        abSalesHrLoginPanelSubmit() {
            return this._abSalesHrIsLocked() ? this.abSalesHrLockedLogin() : this.abSalesHrLogin();
        },

        abSalesHrLoginPanelPinInput(ev) {
            if (this._abSalesHrIsLocked()) {
                this.onAbSalesHrUnlockPinInput(ev);
                return;
            }
            this.onAbSalesHrPinInput(ev);
        },

        abSalesHrLoginPanelPinKeydown(ev) {
            if (this._abSalesHrIsLocked()) {
                this.onAbSalesHrUnlockPinKeydown(ev);
                return;
            }
            this.onAbSalesHrPinKeydown(ev);
        },

        async _abSalesHrBootstrap() {
            this.state.abSalesHr.loading = true;
            this.state.abSalesHr.error = "";
            const cached = this._abSalesHrLoadCachedSession();
            try {
                const result = await this.orm.call("ab_employee_access_sales_pos_api", "pos_bootstrap", [], {
                    session_token: cached?.token || "",
                    store_id: this.currentBill?.header?.store_id || cached?.store_id || false,
                    device_uid: this._abSalesHrDeviceUid,
                    device_name: this._abSalesHrDeviceName,
                });
                this.state.abSalesHr.allowedStoreIds = Array.isArray(result?.allowed_store_ids) ? result.allowed_store_ids : [];
                this.state.abSalesHr.selectedStoreId = parseInt(
                    this.currentBill?.header?.store_id || result?.default_store_id || 0,
                    10
                ) || 0;
                if (result?.session?.token) {
                    await this._abSalesHrApplySession(result.session);
                } else {
                    this.state.abSalesHr.session = false;
                    this.state.abSalesHr.requireLogin = true;
                    this._abSalesHrClearCachedSession();
                }
            } catch (err) {
                this.state.abSalesHr.session = false;
                this.state.abSalesHr.requireLogin = true;
                this.state.abSalesHr.error = err?.message || "Failed to initialize POS HR.";
            } finally {
                this.state.abSalesHr.loading = false;
                this._abSalesHrScheduleTimers();
            }
        },

        async _abSalesHrApplySession(sessionPayload) {
            const previousEmployeeId = typeof this._posDraftEmployeeId === "function" ? this._posDraftEmployeeId() : 0;
            if (previousEmployeeId && typeof this._saveCacheToServer === "function") {
                if (this._cacheSaveTimer) {
                    clearTimeout(this._cacheSaveTimer);
                    this._cacheSaveTimer = null;
                }
                await this._saveCacheToServer({allowRetry: false});
            }
            const payload = sessionPayload || false;
            this.state.abSalesHr.session = payload;
            this.state.abSalesHr.requireLogin = !payload || payload.state !== "active";
            this.state.abSalesHr.selectedStoreId = parseInt(payload?.store?.id || this.state.abSalesHr.selectedStoreId || 0, 10) || 0;
            this.state.abSalesHr.employeeId = parseInt(payload?.employee?.id || this.state.abSalesHr.employeeId || 0, 10) || 0;
            this.state.abSalesHr.employeeAccessId = parseInt(
                payload?.profile_id || this.state.abSalesHr.employeeAccessId || 0,
                10
            ) || 0;
            this.state.abSalesHr.employee = this.state.abSalesHr.employeeAccessId
                ? {
                    id: this.state.abSalesHr.employeeAccessId,
                    display_name: payload?.employee?.name || this.state.abSalesHr.employee?.display_name || "",
                }
                : false;
            if (payload?.token) {
                this._abSalesHrSaveCachedSession({
                    token: payload.token,
                    store_id: payload.store?.id || false,
                });
            } else {
                this._abSalesHrClearCachedSession();
            }
            this._abSalesHrScheduleTimers();
            const sessionStoreId = parseInt(payload?.store?.id || 0, 10) || 0;
            const nextEmployeeId = typeof this._posDraftEmployeeId === "function" ? this._posDraftEmployeeId() : 0;
            if (nextEmployeeId && nextEmployeeId !== previousEmployeeId && typeof this.loadCache === "function") {
                this._lastServerCachePayload = "";
                await this.loadCache();
                this._syncInputsForBill(this.currentBill);
                this.refreshPromotions(this.currentBill);
                this.scheduleLinePosBalanceRefresh(this.currentBill);
                this.refreshStoreStatus(this.currentBill?.header?.store_id);
                this.refreshCustomerInsights(this.currentBill);
                this.searchProducts((this.state.productQuery || "").trim());
            }
            if (sessionStoreId && !this.currentBill) {
                await super.createNewBill(sessionStoreId);
            }
        },

        async _abSalesHrChangeStore(storeId, {silent = false} = {}) {
            const currentSession = this._abSalesHrEnsureActiveSession(!silent);
            if (!currentSession) {
                return false;
            }
            const targetStoreId = parseInt(storeId || 0, 10) || 0;
            if (!targetStoreId) {
                return currentSession;
            }
            if (targetStoreId === parseInt(currentSession.store?.id || 0, 10)) {
                return currentSession;
            }
            const payload = await this.orm.call("ab_employee_access_sales_pos_api", "change_store", [], {
                session_token: currentSession.token,
                store_id: targetStoreId,
            });
            await this._abSalesHrApplySession(payload);
            return payload;
        },

        _abSalesHrClearTimers() {
            if (this._abSalesHrHeartbeatTimer) {
                clearInterval(this._abSalesHrHeartbeatTimer);
                this._abSalesHrHeartbeatTimer = null;
            }
        },

        _abSalesHrScheduleTimers() {
            this._abSalesHrClearTimers();
            if (!this.state.abSalesHr?.session || this.state.abSalesHr.session.state !== "active") {
                return;
            }
            this._abSalesHrHeartbeatTimer = setInterval(() => {
                const token = this._abSalesHrSessionToken();
                if (!token || this.state.abSalesHr.session.state !== "active") {
                    return;
                }
                this.orm.call("ab_employee_access_sales_pos_api", "heartbeat", [], {session_token: token}).catch(() => {
                });
            }, 60000);
        },

        _abSalesHrEnsureActiveSession(notify = true) {
            const currentSession = this.state.abSalesHr?.session;
            if (currentSession?.state === "active") {
                return currentSession;
            }
            if (notify) {
                this.notification.add("Employee login is required.", {type: "warning"});
            }
            return false;
        },

        onAbSalesHrStoreChange(ev) {
            this.state.abSalesHr.selectedStoreId = parseInt(ev.target.value || 0, 10) || 0;
            this.state.abSalesHr.error = "";
        },

        onAbSalesHrStoreUpdate(value) {
            this.state.abSalesHr.selectedStoreId = parseInt(value?.id || 0, 10) || 0;
            this.state.abSalesHr.error = "";
        },

        onAbSalesHrEmployeeUpdate(value) {
            const employeeAccessId = parseInt(value?.id || 0, 10) || 0;
            this.state.abSalesHr.employeeAccessId = employeeAccessId;
            this.state.abSalesHr.employee = employeeAccessId
                ? {id: employeeAccessId, display_name: value?.display_name || ""}
                : false;
            this.state.abSalesHr.error = "";
        },

        onAbSalesHrPinInput(ev) {
            this.state.abSalesHr.pin = ev.target.value || "";
            this.state.abSalesHr.error = "";
        },

        onAbSalesHrPinKeydown(ev) {
            if (ev.key !== "Enter") {
                return;
            }
            ev.preventDefault();
            ev.stopPropagation();
            this.abSalesHrLogin();
        },

        onAbSalesHrUnlockPinInput(ev) {
            this.state.abSalesHr.unlockPin = ev.target.value || "";
            this.state.abSalesHr.error = "";
        },

        onAbSalesHrUnlockPinKeydown(ev) {
            if (ev.key !== "Enter") {
                return;
            }
            ev.preventDefault();
            ev.stopPropagation();
            this.abSalesHrLockedLogin();
        },

        async abSalesHrLogin() {
            try {
                const employeeAccessId = parseInt(
                    this.state.abSalesHr.employee?.id || this.state.abSalesHr.employeeAccessId || 0,
                    10
                ) || 0;
                if (!employeeAccessId || !String(this.state.abSalesHr.pin || "").trim()) {
                    this.state.abSalesHr.error = "Employee and PIN are required.";
                    return;
                }
                const payload = await this.orm.call("ab_employee_access_sales_pos_api", "employee_login", [], {
                    employee_access_id: employeeAccessId || false,
                    pin: this.state.abSalesHr.pin,
                    store_id: false,
                    device_uid: this._abSalesHrDeviceUid,
                    device_name: this._abSalesHrDeviceName,
                });
                this.state.abSalesHr.pin = "";
                this.state.abSalesHr.unlockPin = "";
                this.state.abSalesHr.error = "";
                await this._abSalesHrApplySession(payload);
                this.notification.add(`Logged in as ${payload?.employee?.name || "employee"}.`, {type: "success"});
            } catch (err) {
                const data = err?.data || err?.response?.data || {};
                const rpcArgs = data?.["arguments"];
                this.state.abSalesHr.error = (Array.isArray(rpcArgs) && rpcArgs[0]) || data?.message || err?.message || "Login failed.";
            }
        },

        async abSalesHrLockedLogin() {
            try {
                const currentSession = this.state.abSalesHr?.session;
                const employeeAccessId = parseInt(
                    this.state.abSalesHr.employee?.id || this.state.abSalesHr.employeeAccessId || 0,
                    10
                ) || 0;
                const storeId = parseInt(currentSession?.store?.id || this.state.abSalesHr.selectedStoreId || 0, 10) || 0;
                if (!employeeAccessId || !String(this.state.abSalesHr.unlockPin || "").trim()) {
                    this.state.abSalesHr.error = "Employee and PIN are required.";
                    return;
                }
                const payload = await this.orm.call("ab_employee_access_sales_pos_api", "employee_login", [], {
                    employee_access_id: employeeAccessId || false,
                    pin: this.state.abSalesHr.unlockPin,
                    store_id: storeId || false,
                    device_uid: this._abSalesHrDeviceUid,
                    device_name: this._abSalesHrDeviceName,
                });
                this.state.abSalesHr.pin = "";
                this.state.abSalesHr.unlockPin = "";
                this.state.abSalesHr.error = "";
                await this._abSalesHrApplySession(payload);
                this.notification.add(`Logged in as ${payload?.employee?.name || "employee"}.`, {type: "success"});
            } catch (err) {
                const data = err?.data || err?.response?.data || {};
                const rpcArgs = data?.["arguments"];
                this.state.abSalesHr.error = (Array.isArray(rpcArgs) && rpcArgs[0]) || data?.message || err?.message || "Login failed.";
            }
        },

        async abSalesHrUnlock() {
            try {
                const payload = await this.orm.call("ab_employee_access_sales_pos_api", "unlock_session", [], {
                    session_token: this._abSalesHrSessionToken(),
                    pin: this.state.abSalesHr.unlockPin,
                });
                this.state.abSalesHr.unlockPin = "";
                this.state.abSalesHr.error = "";
                await this._abSalesHrApplySession(payload);
            } catch (err) {
                const data = err?.data || err?.response?.data || {};
                const rpcArgs = data?.["arguments"];
                this.state.abSalesHr.error = (Array.isArray(rpcArgs) && rpcArgs[0]) || data?.message || err?.message || "Unlock failed.";
            }
        },

        async abSalesHrLock(reason = "manual") {
            const currentSession = this.state.abSalesHr?.session;
            if (!currentSession || currentSession.state !== "active") {
                return;
            }
            try {
                const payload = await this.orm.call("ab_employee_access_sales_pos_api", "lock_session", [], {
                    session_token: currentSession.token,
                    reason,
                });
                await this._abSalesHrApplySession(payload);
            } catch {
                // Ignore lock failures and keep UI usable.
            }
        },

        async abSalesHrLogout() {
            const currentSession = this.state.abSalesHr?.session;
            if (currentSession?.employee?.id && typeof this._saveCacheToServer === "function") {
                if (this._cacheSaveTimer) {
                    clearTimeout(this._cacheSaveTimer);
                    this._cacheSaveTimer = null;
                }
                await this._saveCacheToServer({allowRetry: false});
            }
            if (currentSession?.token) {
                try {
                    await this.orm.call("ab_employee_access_sales_pos_api", "logout_session", [], {
                        session_token: currentSession.token,
                        close_shift: true,
                    });
                } catch {
                    // Ignore logout transport failures.
                }
            }
            this._abSalesHrClearCachedSession();
            this.state.abSalesHr.session = false;
            this.state.abSalesHr.requireLogin = true;
            this.state.abSalesHr.unlockPin = "";
            this.state.bills = [];
            this.state.selectedId = null;
            this._syncInputsForBill(null);
            this._abSalesHrClearTimers();
        },

        abSalesHrClosePopup() {
            this.closeWindow();
        },

        _abSalesHrLogOperation(operationType, details = {}, status = "success") {
            const token = this._abSalesHrSessionToken();
            if (!token) {
                return;
            }
            this.orm.call("ab_employee_access_sales_pos_api", "log_operation", [], {
                session_token: token,
                operation_type: operationType,
                status,
                details,
            }).catch(() => {
            });
        },

        openReturnWindow() {
            const currentSession = this._abSalesHrEnsureActiveSession();
            if (!currentSession) {
                return;
            }
            if (!this.canOpenReturnScreen()) {
                this.notification.add("This employee cannot access return screen.", {type: "warning"});
                return;
            }
            const storeId = parseInt(
                this.currentBill?.header?.store_id || currentSession.store?.id || 0,
                10
            ) || false;
            this._abSalesHrLogOperation("return_open", {
                action: "open_return_screen",
                store_id: storeId || false,
            });
            this.action.doAction({
                type: "ir.actions.act_window",
                name: "Sales Return",
                res_model: "ab_sales_return_header",
                view_mode: "form",
                views: [[false, "form"]],
                target: "current",
                context: {
                    default_store_id: storeId,
                },
            });
        },

        onKeydown(ev) {
            if (this.state.abSalesHr?.loading || !this.state.abSalesHr?.session || this.state.abSalesHr.session.state === "locked") {
                return;
            }
            return super.onKeydown(...arguments);
        },

        openNewBillDialog() {
            if (!this._abSalesHrEnsureActiveSession()) {
                return;
            }
            return super.openNewBillDialog(...arguments);
        },

        async createNewBill(storeId) {
            const currentSession = this._abSalesHrEnsureActiveSession();
            if (!currentSession) {
                return;
            }
            const targetStoreId = parseInt(storeId || currentSession.store.id || 0, 10) || parseInt(currentSession.store.id || 0, 10) || 0;
            if (targetStoreId && targetStoreId !== parseInt(currentSession.store.id, 10)) {
                try {
                    await this._abSalesHrChangeStore(targetStoreId, {silent: true});
                } catch (err) {
                    const data = err?.data || err?.response?.data || {};
                    const rpcArgs = data?.["arguments"];
                    this.notification.add((Array.isArray(rpcArgs) && rpcArgs[0]) || data?.message || err?.message || "Store change failed.", {type: "warning"});
                    return;
                }
            }
            return super.createNewBill(targetStoreId);
        },

        async onStoreM2OUpdate(value) {
            const currentSession = this._abSalesHrEnsureActiveSession();
            if (!currentSession) {
                return;
            }
            const targetStoreId = parseInt(value?.id || 0, 10) || 0;
            if (targetStoreId && targetStoreId !== parseInt(currentSession.store.id, 10)) {
                try {
                    await this._abSalesHrChangeStore(targetStoreId, {silent: true});
                } catch (err) {
                    const data = err?.data || err?.response?.data || {};
                    const rpcArgs = data?.["arguments"];
                    this.notification.add((Array.isArray(rpcArgs) && rpcArgs[0]) || data?.message || err?.message || "Store change failed.", {type: "warning"});
                    return;
                }
            }
            return super.onStoreM2OUpdate(...arguments);
        },

        updateLineSellPrice(line, value) {
            const currentSession = this._abSalesHrEnsureActiveSession();
            if (!currentSession || !line) {
                return;
            }
            return super.updateLineSellPrice(line, value);
        },

        onAvailablePriceSelect(line, priceValue) {
            return this.updateLineSellPrice(line, String(priceValue));
        },

        removeLine(line) {
            const currentSession = this._abSalesHrEnsureActiveSession();
            if (!currentSession || !line) {
                return;
            }
            return super.removeLine(...arguments);
        },

        async submitCurrentBill() {
            const currentSession = this._abSalesHrEnsureActiveSession();
            if (!currentSession) {
                return;
            }
            return super.submitCurrentBill(...arguments);
        },

        async _submitBillInternal(bill) {
            const currentSession = this._abSalesHrEnsureActiveSession();
            if (!currentSession || !bill) {
                return;
            }
            return super._submitBillInternal(...arguments);
        },
    });
}
