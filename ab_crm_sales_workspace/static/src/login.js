import {useChatterFeedback, feedbackError} from "./feedback";
/** @odoo-module **/

import {Component, useState} from "@odoo/owl";
import {ABMany2one} from "@ab_widgets/ab_many2one";
import {localization} from "@web/core/l10n/localization";
import {Dialog} from "@web/core/dialog/dialog";
import {_t} from "@web/core/l10n/translation";

export class ChatterLoginDialog extends Component {
    static template = "ab_crm_sales_workspace.Login";
    static components = {Dialog, ABMany2one};
    static props = {employees: Array, onLogin: Function, close: Function};
    setup() {
        this.direction = localization.direction;
        this.title = _t("Employee Login");
        this.state = useState({employee: false, pin: "", busy: false, error: ""});
        this.feedback = useChatterFeedback(this);
    }
    employeeDomain() {
        return [["id", "in", this.props.employees.map(employee => employee.id)]];
    }
    updateEmployee(value) {
        this.state.employee = value || false;
        this.state.error = "";
    }
    async submit() {
        if (this.state.busy) return;
        if (!this.state.employee || !this.state.pin) {
            this.state.error = feedbackError(this, _t("Employee and PIN are required."));
            return;
        }
        this.state.busy = true;
        try {
            await this.props.onLogin(this.state.employee.id, this.state.pin.trim());
            this.props.close();
        } catch (error) {
            this.state.error = feedbackError(this, error);
        } finally {
            this.state.pin = "";
            this.state.busy = false;
        }
    }
}
