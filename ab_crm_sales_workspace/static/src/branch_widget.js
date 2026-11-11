import {useChatterFeedback, feedbackError} from "./feedback";
import {Component, onWillUnmount, onWillUpdateProps, useState} from "@odoo/owl";
import {registry} from "@web/core/registry";
import {useService} from "@web/core/utils/hooks";
import {standardWidgetProps} from "@web/views/widgets/standard_widget_props";
import {user} from "@web/core/user";
import {_t} from "@web/core/l10n/translation";
import {LocationDialog} from "./composer";
import {ChatterLoginDialog} from "./login";

export class BranchShareWidget extends Component {
    static template = "ab_crm_sales_workspace.BranchShareWidget";
    static props = {...standardWidgetProps};
    setup() {
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        this.session = useService("ab_chatter_session");
        this.state = useState({error: ""});
        this.feedback = useChatterFeedback(this);
        this.generation = 0;
        onWillUpdateProps(() => { this.generation++; });
        onWillUnmount(() => { this.destroyed = true; });
    }
    async open() {
        this.state.error = "";
        try {
            const cached = this.session.current;
            const bootstrap = await this.feedback.call(this.orm, "ab_crm_chatter_api", "bootstrap", [], {token: cached?.token || false});
            if (!bootstrap.session) {
                this.dialog.add(ChatterLoginDialog, {employees: bootstrap.employees, onLogin: async (profileId, pin) => {
                    let device = sessionStorage.getItem(`ab_chatter_device_${user.userId}`);
                    if (!device) { device = crypto.randomUUID(); sessionStorage.setItem(`ab_chatter_device_${user.userId}`, device); }
                    const result = await this.feedback.call(this.orm, "ab_crm_chatter_api", "employee_login", [], {profile_id: profileId, pin, device_uid: device});
                    if (result.error) throw new Error(result.error);
                    this.session.set(result);
                    this.show();
                }});
            } else this.show();
        } catch (error) { this.state.error = feedbackError(this, error); }
    }
    show() {
        if (this.destroyed) return;
        const generation = this.generation;
        const record = this.props.record;
        const id = record.resId;
        const conversationId = record.resModel === "ab_crm_conversation" ? id : record.data.conversation_id?.id;
        if (!conversationId) { this.state.error = feedbackError(this, _t("Select a conversation before sharing a branch.")); return; }
        const token = this.session.current.token;
        this.dialog.add(LocationDialog, {
            conversationId,
            call: (model, method, args) => this.feedback.call(this.orm, model, method, args, {context: {ab_chatter_session_token: token}}),
            valid: () => !this.destroyed && this.generation === generation && this.props.record.resId === id && this.session.current?.token === token && (record.resModel === "ab_crm_conversation" || record.data.conversation_id?.id === conversationId),
        });
    }
}

registry.category("view_widgets").add("ab_branch_share", {component: BranchShareWidget});
