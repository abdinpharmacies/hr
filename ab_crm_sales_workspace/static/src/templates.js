import {useChatterFeedback, useChatterNotice, feedbackError} from "./feedback";
import {Component, onMounted, useState} from "@odoo/owl";
import {Dialog} from "@web/core/dialog/dialog";
import {ConfirmationDialog} from "@web/core/confirmation_dialog/confirmation_dialog";
import {useService} from "@web/core/utils/hooks";
import {_t} from "@web/core/l10n/translation";

class TemplateDialog extends Dialog {
    static props = {...Dialog.props, requestClose: Function};
    dismiss() { this.props.requestClose(); }
}

export class SavedReplies extends Component {
    static template = "ab_crm_sales_workspace.SavedReplies";
    static components = {Dialog: TemplateDialog};
    static props = {call: Function, conversation: Object, insert: Function, close: Function};
    setup() {
        this.title = _t("Saved replies");
        this.dialog = useService("dialog");
        this.state = useState({items: [], can_manage: false, selected: false, name: "", body: "", variables: {}, query: "", error: "", busy: false});
        this.feedback = useChatterFeedback(this);
        useChatterNotice(() => this.missingValues ? {message: _t("Complete all required parameters.")} : null,
            () => [this.state.selected, this.missingValues]);
        this.saved = this.snapshot;
        onMounted(() => this.refresh());
    }
    get theme() { return this.props.conversation.provider === "whatsapp" ? "whatsapp" : "telegram"; }
    get snapshot() { return JSON.stringify([this.state.name, this.state.body, this.state.variables]); }
    get dirty() { return this.saved !== this.snapshot; }
    get filteredItems() {
        const query = this.state.query.trim().toLocaleLowerCase();
        return this.state.items.filter(item => `${item.name} ${item.body}`.toLocaleLowerCase().includes(query));
    }
    guard(action) {
        if (this.state.busy) return;
        if (!this.dirty) return action();
        this.dialog.add(ConfirmationDialog, {title: _t("Unsaved changes"), body: _t("Discard your unsaved template changes?"),
            confirmLabel: _t("Discard"), cancelLabel: _t("Keep editing"), cancel: () => {}, confirm: action});
    }
    close() { this.guard(() => this.props.close()); }
    async run(action) {
        if (this.state.busy) return;
        this.state.busy = true;
        this.state.error = "";
        try { await action(); }
        catch (error) { this.state.error = feedbackError(this, error); }
        finally { this.state.busy = false; }
    }
    refresh() {
        return this.guard(() => this.run(async () => {
            const result = await this.props.call("ab_crm_conversation", "workspace_templates", [[this.props.conversation.id]]);
            Object.assign(this.state, result);
            this.load(this.state.items.find(item => item.id === this.state.selected)?.id || this.state.items[0]?.id || false);
        }));
    }
    load(id) {
        const template = this.state.items.find(row => row.id === id);
        this.state.selected = template?.id || false;
        this.state.name = template?.name || "";
        this.state.body = template?.body || "";
        this.state.variables = {customer: this.props.conversation.name, phone: this.props.conversation.phone};
        this.saved = this.snapshot;
    }
    select(id) { if (id !== this.state.selected) this.guard(() => this.load(id)); }
    get placeholders() { return [...new Set([...this.state.body.matchAll(/\{\{\s*(\w+)\s*\}\}/g)].map(match => match[1]))]; }
    get preview() { return this.state.body.replace(/\{\{\s*(\w+)\s*\}\}/g, (match, name) => this.state.variables[name]?.trim() || match); }
    get missingValues() { return this.placeholders.some(key => !this.state.variables[key]?.trim()); }
    save(active = true) {
        if (!this.state.can_manage) return;
        const save = () => this.run(async () => {
            const archived = !active && this.state.items.find(item => item.id === this.state.selected);
            const result = await this.props.call("ab_crm_conversation", "save_template", [[this.props.conversation.id], archived ? archived.name : this.state.name, archived ? archived.body : this.state.body], {template_id: this.state.selected || false, active});
            Object.assign(this.state, {items: result.items, can_manage: result.can_manage});
            this.load(result.selected_id || false);
        });
        return active ? save() : this.guard(save);
    }
    insert() {
        if (this.state.busy || !this.preview.trim() || this.missingValues) return;
        this.props.insert(this.preview);
        this.props.close();
    }
}
