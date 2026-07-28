/** @odoo-module **/

import {onWillDestroy, onWillStart} from "@odoo/owl";
import {registry} from "@web/core/registry";
import {patch} from "@web/core/utils/patch";
import {session} from "@web/session";
import {AbEmployeeAccessLoginPanel} from "@ab_employee_access/login/employee_login";

const ReturnAction = registry.category("actions").get("ab_sales.return_ui");

const RETURN_SESSION_KEY = `ab_employee_access_sales_return_session_${session.user_id || 0}`;
const RETURN_DEVICE_KEY = `ab_employee_access_sales_return_device_${session.user_id || 0}`;

function makeDeviceUid() {
    try {
        const raw = localStorage.getItem(RETURN_DEVICE_KEY);
        if (raw) {
            return raw;
        }
        const generated = `return_device_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;
        localStorage.setItem(RETURN_DEVICE_KEY, generated);
        return generated;
    } catch {
        return `return_device_${session.user_id || 0}`;
    }
}

function makeDeviceName() {
    const nav = globalThis.navigator || {};
    const platform = nav.userAgentData?.platform || nav.platform || "";
    const agent = nav.userAgent || "";
    const value = [platform, agent].filter(Boolean).join(" / ").trim();
    return value || "Sales Return Terminal";
}

if (ReturnAction) {
    ReturnAction.components = {
        ...(ReturnAction.components || {}),
        AbEmployeeAccessLoginPanel,
    };

    patch(ReturnAction.prototype, {
        setup() {
            super.setup(...arguments);

            this._abReturnDeviceUid = makeDeviceUid();
            this._abReturnDeviceName = makeDeviceName();
            this._abReturnLogoutStarted = false;
            this._abReturnDestroyCleanupStarted = false;
            this._abReturnLastLoadError = "";

            this.state.abReturnAccess = {
                loading: true,
                session: false,
                employee: false,
                pin: "",
                error: "",
                loginLoading: false,
            };

            this._abReturnLoadCachedSession = this._abReturnLoadCachedSession.bind(this);
            this._abReturnSaveCachedSession = this._abReturnSaveCachedSession.bind(this);
            this._abReturnClearCachedSession = this._abReturnClearCachedSession.bind(this);
            this._abReturnSessionToken = this._abReturnSessionToken.bind(this);
            this._abReturnApplySession = this._abReturnApplySession.bind(this);
            this._abReturnClearSessionState = this._abReturnClearSessionState.bind(this);
            this._abReturnBootstrap = this._abReturnBootstrap.bind(this);
            this._abReturnLogout = this._abReturnLogout.bind(this);
            this._abReturnLogoutOnDestroy = this._abReturnLogoutOnDestroy.bind(this);
            this._abReturnMaybeAbandonTemporaryReturn = this._abReturnMaybeAbandonTemporaryReturn.bind(this);
            this._abReturnDestroyCleanup = this._abReturnDestroyCleanup.bind(this);
            this.returnLoginPanelSubtitle = this.returnLoginPanelSubtitle.bind(this);
            this.returnLoginPanelEmployeeValue = this.returnLoginPanelEmployeeValue.bind(this);
            this.returnLoginPanelPinValue = this.returnLoginPanelPinValue.bind(this);
            this.closeReturnLoginOverlay = this.closeReturnLoginOverlay.bind(this);
            this.onReturnLoginEmployeeUpdate = this.onReturnLoginEmployeeUpdate.bind(this);
            this.returnLoginPanelPinInput = this.returnLoginPanelPinInput.bind(this);
            this.returnLoginPanelPinKeydown = this.returnLoginPanelPinKeydown.bind(this);
            this.submitReturnLoginPanel = this.submitReturnLoginPanel.bind(this);

            if (!this._abReturnOrmWrapped) {
                const rawCall = this.orm.call.bind(this.orm);
                this.orm.call = async (model, method, args = [], kwargs = {}) => {
                    if (model === "ab_sales_return_ui_api" && kwargs && typeof kwargs === "object") {
                        if (method !== "abandon_return" && !("session_token" in kwargs)) {
                            kwargs = {
                                ...kwargs,
                                session_token: this._abReturnSessionToken(),
                            };
                        }
                    }
                    return rawCall(model, method, args, kwargs);
                };
                this._abReturnOrmWrapped = true;
            }

            onWillStart(async () => {
                await this._abReturnBootstrap();
            });

            onWillDestroy(() => {
                this._abReturnDestroyCleanup();
            });
        },

        _abReturnLoadCachedSession() {
            try {
                const raw = localStorage.getItem(RETURN_SESSION_KEY);
                return raw ? JSON.parse(raw) : {};
            } catch {
                return {};
            }
        },

        _abReturnSaveCachedSession(payload) {
            try {
                localStorage.setItem(RETURN_SESSION_KEY, JSON.stringify(payload || {}));
            } catch {
                // Ignore local storage failures.
            }
        },

        _abReturnClearCachedSession() {
            try {
                localStorage.removeItem(RETURN_SESSION_KEY);
            } catch {
                // Ignore local storage failures.
            }
        },

        _abReturnSessionToken() {
            return this.state.abReturnAccess?.session?.token || "";
        },

        _abReturnApplySession(sessionPayload) {
            const payload = sessionPayload || false;
            this.state.abReturnAccess.session = payload;
            this.state.abReturnAccess.employee = payload?.profile_id
                ? {
                    id: payload.profile_id,
                    display_name: payload.employee?.name || payload.employee?.code || `#${payload.profile_id}`,
                }
                : false;
            this.state.abReturnAccess.pin = "";
            this.state.abReturnAccess.error = "";
            if (payload?.token) {
                this._abReturnSaveCachedSession({session_token: payload.token});
            } else {
                this._abReturnClearCachedSession();
            }
        },

        _abReturnClearSessionState() {
            this.state.abReturnAccess.session = false;
            this.state.abReturnAccess.employee = false;
            this.state.abReturnAccess.pin = "";
            this.state.abReturnAccess.loginLoading = false;
            this._abReturnLastLoadError = "";
        },

        async _abReturnBootstrap() {
            this.state.abReturnAccess.loading = true;
            this.state.abReturnAccess.error = "";
            const cached = this._abReturnLoadCachedSession();
            const cachedToken = String(cached?.session_token || "").trim();
            try {
                const payload = await this.orm.call("ab_employee_access_sales_pos_api", "pos_bootstrap", [], {
                    session_token: cachedToken,
                    device_uid: this._abReturnDeviceUid,
                    device_name: this._abReturnDeviceName,
                });
                this._abReturnDeviceUid = payload?.device_uid || this._abReturnDeviceUid;
                this._abReturnDeviceName = payload?.device_name || this._abReturnDeviceName;
                const sessionPayload = payload?.session || false;
                if (sessionPayload?.permissions?.allow_return_screen) {
                    this._abReturnApplySession(sessionPayload);
                    const loaded = await this.load({reportError: false});
                    if (!loaded) {
                        this.state.abReturnAccess.error = this._abReturnLastLoadError || "Employee login is required.";
                        await this._abReturnLogout({silent: true, preserveError: true});
                    }
                } else {
                    this._abReturnClearCachedSession();
                    this._abReturnClearSessionState();
                }
            } catch (error) {
                this._abReturnClearCachedSession();
                this._abReturnClearSessionState();
                this.state.abReturnAccess.error = this._messageFromError(error, "Failed to start employee login.");
            } finally {
                this.state.abReturnAccess.loading = false;
                this.state.loading = false;
            }
        },

        async load({reportError = true} = {}) {
            const sessionToken = this._abReturnSessionToken();
            if (!sessionToken) {
                this.state.loading = false;
                this.state.record = null;
                return false;
            }
            this.state.loading = true;
            this._abReturnLastLoadError = "";
            try {
                const record = await this.orm.call("ab_sales_return_ui_api", "get_state", [], {
                    return_header_id: this.returnHeaderId,
                });
                this._applyRecord(record);
                return true;
            } catch (error) {
                this.state.record = null;
                this._abReturnLastLoadError = this._messageFromError(error, "Failed to load sales return.");
                if (reportError) {
                    this.notification.add(this._abReturnLastLoadError, {type: "danger"});
                }
                return false;
            } finally {
                this.state.loading = false;
            }
        },

        returnLoginPanelSubtitle() {
            if (this.state.abReturnAccess.loading) {
                return "Loading employee access...";
            }
            return "Select employee and enter PIN to access sales return screen.";
        },

        returnLoginPanelEmployeeValue() {
            return this.state.abReturnAccess.employee || false;
        },

        returnLoginPanelPinValue() {
            return this.state.abReturnAccess.pin || "";
        },

        async closeReturnLoginOverlay() {
            await this.close();
        },

        onReturnLoginEmployeeUpdate(value) {
            this.state.abReturnAccess.employee = value && value.id ? value : false;
            this.state.abReturnAccess.error = "";
        },

        returnLoginPanelPinInput(ev) {
            this.state.abReturnAccess.pin = String(ev.target.value || "");
            this.state.abReturnAccess.error = "";
        },

        returnLoginPanelPinKeydown(ev) {
            if (ev.key !== "Enter") {
                return;
            }
            ev.preventDefault();
            ev.stopPropagation();
            this.submitReturnLoginPanel();
        },

        async submitReturnLoginPanel() {
            if (this.state.abReturnAccess.loginLoading) {
                return false;
            }
            const employeeAccessId = Number.parseInt(this.state.abReturnAccess.employee?.id || 0, 10) || 0;
            const pin = String(this.state.abReturnAccess.pin || "").trim();
            if (!employeeAccessId || !pin) {
                this.state.abReturnAccess.error = "Employee and PIN are required.";
                return false;
            }
            this.state.abReturnAccess.loginLoading = true;
            this.state.abReturnAccess.error = "";
            try {
                const sessionPayload = await this.orm.call("ab_employee_access_sales_pos_api", "employee_login", [], {
                    employee_access_id: employeeAccessId,
                    pin,
                    device_uid: this._abReturnDeviceUid,
                    device_name: this._abReturnDeviceName,
                });
                if (!sessionPayload?.permissions?.allow_return_screen) {
                    if (sessionPayload?.token) {
                        await this.orm.call("ab_employee_access_sales_pos_api", "logout_session", [], {
                            session_token: sessionPayload.token,
                        });
                    }
                    this.state.abReturnAccess.error = "Employee role does not allow sales return screen access.";
                    return false;
                }
                this._abReturnApplySession(sessionPayload);
                const loaded = await this.load({reportError: false});
                if (!loaded) {
                    this.state.abReturnAccess.error = this._abReturnLastLoadError || "Employee login is required.";
                    await this._abReturnLogout({silent: true, preserveError: true});
                    return false;
                }
                return true;
            } catch (error) {
                this.state.abReturnAccess.error = this._messageFromError(error, "Employee login failed.");
                return false;
            } finally {
                this.state.abReturnAccess.loginLoading = false;
            }
        },

        async _abReturnLogout({silent = true, preserveError = false} = {}) {
            if (this._abReturnLogoutStarted) {
                return;
            }
            const token = this._abReturnSessionToken();
            this._abReturnLogoutStarted = true;
            try {
                if (token) {
                    await this.orm.call("ab_employee_access_sales_pos_api", "logout_session", [], {
                        session_token: token,
                    });
                }
            } catch (error) {
                if (!silent) {
                    this.notification.add(this._messageFromError(error, "Failed to close employee session."), {
                        type: "warning",
                    });
                }
            } finally {
                const preservedError = preserveError ? this.state.abReturnAccess.error : "";
                this._abReturnClearCachedSession();
                this._abReturnClearSessionState();
                this.state.abReturnAccess.error = preservedError;
                this._abReturnLogoutStarted = false;
            }
        },

        _abReturnLogoutOnDestroy() {
            const token = this._abReturnSessionToken();
            if (!token || this._abReturnLogoutStarted) {
                return;
            }
            this._abReturnLogoutStarted = true;
            this._abReturnClearCachedSession();
            Promise.resolve(
                this.orm.call("ab_employee_access_sales_pos_api", "logout_session", [], {
                    session_token: token,
                })
            ).catch(() => {});
        },

        async _abReturnMaybeAbandonTemporaryReturn() {
            if (!this.returnHeaderId) {
                return;
            }
            try {
                await this.orm.call("ab_sales_return_ui_api", "abandon_return", [], {
                    return_header_id: this.returnHeaderId,
                });
            } catch {
                // Ignore abandon failures during close.
            }
        },

        _abReturnDestroyCleanup() {
            if (this._abReturnDestroyCleanupStarted) {
                return;
            }
            this._abReturnDestroyCleanupStarted = true;
            this._abReturnLogoutOnDestroy();
            if (this.returnHeaderId) {
                Promise.resolve(
                    this.orm.call("ab_sales_return_ui_api", "abandon_return", [], {
                        return_header_id: this.returnHeaderId,
                    })
                ).catch(() => {});
            }
        },

        async close() {
            await this._abReturnLogout({silent: true});
            await this._abReturnMaybeAbandonTemporaryReturn();
            return await super.close(...arguments);
        },
    });
}
