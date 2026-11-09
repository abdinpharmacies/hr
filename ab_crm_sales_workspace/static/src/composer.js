import {Component, onWillStart, onWillUnmount, useState} from "@odoo/owl";
import {Dialog} from "@web/core/dialog/dialog";
import {user} from "@web/core/user";
import {_t} from "@web/core/l10n/translation";
import {LocationCard} from "./location";

export class LocationDialog extends Component {
    static template = "ab_crm_sales_workspace.LocationDialog";
    static components = {Dialog, LocationCard};
    static props = {close: Function, call: Function, conversationId: Number, valid: Function, storeId: {type: Number, optional: true}, sent: {type: Function, optional: true}};
    setup() {
        this.title = _t("Choose branch");
        this.state = useState({query: "", language: ["ar", "ar_001"].includes(user.context.lang) ? user.context.lang : "en_US", rows: [], preview: null, busy: false, error: "", includeDetails: false});
        this.sequence = 0;
        this.tokens = {location: crypto.randomUUID(), details: crypto.randomUUID()};
        onWillStart(async () => {
            await this.search();
            const selected = this.state.rows.find(row => row.store_id === this.props.storeId);
            if (selected) await this.preview(selected.id);
        });
        onWillUnmount(() => { this.destroyed = true; this.sequence++; });
    }
    check() {
        if (this.destroyed || !this.props.valid()) throw new Error(_t("This branch picker has expired. Open it again from the conversation."));
    }
    async search() {
        const sequence = ++this.sequence;
        this.state.preview = null;
        try {
            this.check();
            const rows = await this.props.call("ab_crm_conversation", "workspace_branch_directory", [[this.props.conversationId], this.state.query, this.state.language]);
            if (sequence === this.sequence && !this.destroyed) this.state.rows = rows;
        } catch (error) { this.state.error = error.data?.message || error.message; }
    }
    async preview(id) {
        const sequence = ++this.sequence;
        this.state.preview = null;
        this.state.error = "";
        try {
            this.check();
            const preview = await this.props.call("ab_crm_conversation", "workspace_branch_preview", [[this.props.conversationId], id, this.state.language]);
            if (sequence !== this.sequence || this.destroyed) return;
            this.state.preview = preview;
            this.tokens = {location: crypto.randomUUID(), details: crypto.randomUUID()};
        } catch (error) { this.state.error = error.data?.message || error.message; }
    }
    async languageChanged() {
        const id = this.state.preview?.id;
        await this.search();
        if (id) await this.preview(id);
    }
    async send() {
        if (this.state.busy || !this.state.preview) return;
        this.state.busy = true;
        this.state.error = "";
        try {
            this.check();
            const preview = this.state.preview;
            await this.props.call("ab_crm_conversation", "action_share_branch", [[this.props.conversationId], preview.id, preview.revision, preview.language, this.tokens.location, this.state.includeDetails]);
            this.props.sent?.();
            this.props.close();
        } catch (error) { this.state.error = error.data?.message || error.message; }
        finally { this.state.busy = false; }
    }
}
