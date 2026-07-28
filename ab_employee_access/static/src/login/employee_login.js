/** @odoo-module **/

import {Component, onWillUnmount, useState} from "@odoo/owl";
import {Dialog} from "@web/core/dialog/dialog";
import {ABMany2one} from "@ab_widgets/ab_many2one";

export class AbEmployeeAccessLoginScreen extends Component {
    static template = "ab_employee_access.LoginScreen";
    static components = {ABMany2one};
    static props = {
        employee: {optional: true},
        employeeRelation: {type: String, optional: true},
        employeeDomain: {optional: true},
        pin: {type: String, optional: true},
        error: {type: String, optional: true},
        loading: {type: Boolean, optional: true},
        showEmployee: {type: Boolean, optional: true},
        showCancel: {type: Boolean, optional: true},
        required: {type: Boolean, optional: true},
        submitLabel: {type: String, optional: true},
        loadingLabel: {type: String, optional: true},
        cancelLabel: {type: String, optional: true},
        employeeLabel: {type: String, optional: true},
        pinLabel: {type: String, optional: true},
        employeePlaceholder: {type: String, optional: true},
        pinPlaceholder: {type: String, optional: true},
        pinInputName: {type: String, optional: true},
        onSubmit: Function,
        onCancel: {type: Function, optional: true},
        onEmployeeUpdate: {type: Function, optional: true},
        onPinInput: {type: Function, optional: true},
        onPinKeydown: {type: Function, optional: true},
    };

    setup() {
        this.employeeDomain = this.employeeDomain.bind(this);
        this.onEmployeeUpdate = this.onEmployeeUpdate.bind(this);
        this.onPinInput = this.onPinInput.bind(this);
        this.onPinKeydown = this.onPinKeydown.bind(this);
        this.submit = this.submit.bind(this);
        this.cancel = this.cancel.bind(this);
    }

    employeeDomain() {
        return this.props.employeeDomain || [["pos_allow_login", "=", true]];
    }

    onEmployeeUpdate(value) {
        if (this.props.onEmployeeUpdate) {
            this.props.onEmployeeUpdate(value);
        }
    }

    onPinInput(ev) {
        if (this.props.onPinInput) {
            this.props.onPinInput(ev);
        }
    }

    onPinKeydown(ev) {
        if (this.props.onPinKeydown) {
            this.props.onPinKeydown(ev);
        }
    }

    submit() {
        return this.props.onSubmit();
    }

    cancel() {
        if (this.props.required) {
            return;
        }
        if (this.props.onCancel) {
            this.props.onCancel();
        }
    }
}

export class AbEmployeeAccessLoginPanel extends Component {
    static template = "ab_employee_access.LoginPanel";
    static components = {AbEmployeeAccessLoginScreen};
    static props = {
        title: {type: String, optional: true},
        subtitle: {type: String, optional: true},
        showClose: {type: Boolean, optional: true},
        onClose: {type: Function, optional: true},
        showScreen: {type: Boolean, optional: true},
        loadingMessage: {type: String, optional: true},
        employee: {optional: true},
        employeeRelation: {type: String, optional: true},
        employeeDomain: {optional: true},
        pin: {type: String, optional: true},
        error: {type: String, optional: true},
        loading: {type: Boolean, optional: true},
        showEmployee: {type: Boolean, optional: true},
        showCancel: {type: Boolean, optional: true},
        required: {type: Boolean, optional: true},
        submitLabel: {type: String, optional: true},
        loadingLabel: {type: String, optional: true},
        cancelLabel: {type: String, optional: true},
        employeeLabel: {type: String, optional: true},
        pinLabel: {type: String, optional: true},
        employeePlaceholder: {type: String, optional: true},
        pinPlaceholder: {type: String, optional: true},
        pinInputName: {type: String, optional: true},
        onSubmit: {type: Function, optional: true},
        onCancel: {type: Function, optional: true},
        onEmployeeUpdate: {type: Function, optional: true},
        onPinInput: {type: Function, optional: true},
        onPinKeydown: {type: Function, optional: true},
    };

    setup() {
        this.close = this.close.bind(this);
    }

    close() {
        if (this.props.onClose) {
            this.props.onClose();
        }
    }
}

export class AbEmployeeAccessLoginDialog extends Component {
    static template = "ab_employee_access.LoginDialog";
    static components = {Dialog, AbEmployeeAccessLoginPanel};
    static props = {
        title: {type: String, optional: true},
        subtitle: {type: String, optional: true},
        onSubmit: Function,
        onCancel: {type: Function, optional: true},
        required: {type: Boolean, optional: true},
        close: Function,
        defaultEmployee: {type: Object, optional: true},
        employeeRelation: {type: String, optional: true},
        employeeDomain: {optional: true},
        defaultPin: {type: String, optional: true},
        showEmployee: {type: Boolean, optional: true},
        submitLabel: {type: String, optional: true},
        loadingLabel: {type: String, optional: true},
        cancelLabel: {type: String, optional: true},
        employeeLabel: {type: String, optional: true},
        pinLabel: {type: String, optional: true},
        employeePlaceholder: {type: String, optional: true},
        pinPlaceholder: {type: String, optional: true},
        pinInputName: {type: String, optional: true},
    };

    setup() {
        this._done = false;
        const defaultEmployee = this.props.defaultEmployee || false;
        const defaultEmployeeId = Number.parseInt(defaultEmployee?.id || 0, 10) || 0;
        this.state = useState({
            employee: defaultEmployeeId
                ? {id: defaultEmployeeId, display_name: defaultEmployee?.display_name || ""}
                : false,
            pin: String(this.props.defaultPin || ""),
            loading: false,
            error: "",
        });
        this.onEmployeeUpdate = this.onEmployeeUpdate.bind(this);
        this.onPinInput = this.onPinInput.bind(this);
        this.onPinKeydown = this.onPinKeydown.bind(this);
        this.submit = this.submit.bind(this);
        this.cancel = this.cancel.bind(this);
        onWillUnmount(() => {
            if (!this._done && this.props.onCancel) {
                this.props.onCancel();
            }
        });
    }

    onEmployeeUpdate(value) {
        if (value && value.id) {
            this.state.employee = value;
        } else {
            this.state.employee = false;
        }
        this.state.error = "";
    }

    onPinInput(ev) {
        this.state.pin = String(ev.target.value || "");
        this.state.error = "";
    }

    onPinKeydown(ev) {
        if (ev.key !== "Enter") {
            return;
        }
        ev.preventDefault();
        ev.stopPropagation();
        this.submit();
    }

    async submit() {
        if (this.state.loading) {
            return;
        }
        this.state.error = "";
        const showEmployee = this.props.showEmployee !== false;
        const employeeAccessId = Number.parseInt(this.state.employee?.id || 0, 10) || 0;
        const pin = String(this.state.pin || "").trim();
        if ((showEmployee && !employeeAccessId) || !pin) {
            this.state.error = "Employee and PIN are required.";
            return;
        }
        this.state.loading = true;
        try {
            const result = await this.props.onSubmit({
                employeeAccessId,
                selectedId: employeeAccessId,
                pin,
            });
            if (!result) {
                return;
            }
            this._done = true;
            if (this.props.close) {
                this.props.close();
            }
        } catch (err) {
            this.state.error = String(err?.message || "Login failed.");
        } finally {
            this.state.loading = false;
        }
    }

    cancel() {
        if (this.props.required) {
            return;
        }
        this._done = true;
        if (this.props.onCancel) {
            this.props.onCancel();
        }
        if (this.props.close) {
            this.props.close();
        }
    }

}
