import {Component, onWillStart, useState} from "@odoo/owl";
import {Dialog} from "@web/core/dialog/dialog";
import {_t} from "@web/core/l10n/translation";

export class SavedReplies extends Component {
    static template = "ab_crm_sales_workspace.SavedReplies";
    static components = {Dialog};
    static props = {call: Function, conversation: Object, insert: Function, close: Function};
    setup() {
        this.title = _t("Templates");
        this.state = useState({items: [], can_manage: false, selected: "", name: "", body: "", variables: {}, error: "", busy: false});
        onWillStart(() => this.refresh());
    }
    async run(action) {
        if (this.state.busy) return;
        this.state.busy = true;
        try { await action(); this.state.error = ""; }
        catch (error) { this.state.error = error.data?.message || error.message; }
        finally { this.state.busy = false; }
    }
    async refresh() {
        await this.run(async () => Object.assign(this.state, await this.props.call("ab_crm_conversation", "workspace_templates", [[this.props.conversation.id]])));
    }
    select() {
        const template = this.state.items.find(row => row.id === Number(this.state.selected));
        this.state.name = template?.name || "";
        this.state.body = template?.body || "";
        this.state.variables = {customer: this.props.conversation.name, phone: this.props.conversation.phone};
    }
    get placeholders() { return [...new Set([...this.state.body.matchAll(/\{\{\s*(\w+)\s*\}\}/g)].map(match => match[1]))]; }
    get preview() { return this.state.body.replace(/\{\{\s*(\w+)\s*\}\}/g, (match, name) => this.state.variables[name] || match); }
    async save(active = true) {
        await this.run(async () => Object.assign(this.state, await this.props.call("ab_crm_conversation", "save_template", [[this.props.conversation.id], this.state.name, this.state.body], {template_id: Number(this.state.selected) || false, active})));
    }
    insert() { this.props.insert(this.preview); this.props.close(); }
}
