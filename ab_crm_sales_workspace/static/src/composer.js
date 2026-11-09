import {Component, onWillUnmount, useState} from "@odoo/owl";
import {AutoComplete} from "@web/core/autocomplete/autocomplete";
import {Dialog} from "@web/core/dialog/dialog";
import {_t} from "@web/core/l10n/translation";
import {LocationCard} from "./location";

export class LocationDialog extends Component {
    static template = "ab_crm_sales_workspace.LocationDialog";
    static components = {Dialog, LocationCard, AutoComplete};
    static props = {close: Function, call: Function, conversationId: Number, valid: Function, storeId: {type: Number, optional: true}, sent: {type: Function, optional: true}};
    setup() {
        this.title = _t("Choose branch");
        this.state = useState({query: "", preview: null, busy: false, error: "", includeDetails: false});
        this.searchId = `ab-branch-search-${crypto.randomUUID()}`;
        this.searchPlaceholder = _t("Name, region, address or store code");
        this.sources = [{placeholder: _t("Searching…"), options: query => this.search(query)}];
        this.sequence = 0;
        this.tokens = {location: crypto.randomUUID(), details: crypto.randomUUID()};
        onWillUnmount(() => { this.destroyed = true; this.sequence++; });
    }
    check() {
        if (this.destroyed || !this.props.valid()) throw new Error(_t("This branch picker has expired. Open it again from the conversation."));
    }
    searchInput(event) {
        this.sequence++;
        this.state.query = event.target.value;
        this.state.preview = null;
        this.state.error = "";
    }
    async search(query) {
        const sequence = ++this.sequence;
        if (!query.trim()) return [];
        try {
            this.check();
            const rows = await this.props.call("ab_crm_conversation", "workspace_branch_directory", [[this.props.conversationId], query, "ar_001"]);
            if (sequence !== this.sequence || this.destroyed) return [];
            return rows.length ? rows.map(row => ({
                label: [row.name, row.region, row.store_code].filter(Boolean).join(" · "),
                onSelect: () => {
                    if (sequence !== this.sequence || this.destroyed) return;
                    this.state.query = row.name;
                    this.preview(row.id);
                },
            })) : [{label: _t("No reviewed branches available.")}];
        } catch (error) {
            if (sequence === this.sequence && !this.destroyed) this.state.error = error.data?.message || error.message;
            return [];
        }
    }
    async preview(id) {
        const sequence = ++this.sequence;
        this.state.preview = null;
        this.state.error = "";
        try {
            this.check();
            const preview = await this.props.call("ab_crm_conversation", "workspace_branch_preview", [[this.props.conversationId], id, "ar_001"]);
            if (sequence !== this.sequence || this.destroyed) return;
            this.state.preview = preview;
            this.tokens = {location: crypto.randomUUID(), details: crypto.randomUUID()};
        } catch (error) {
            if (sequence === this.sequence && !this.destroyed) this.state.error = error.data?.message || error.message;
        }
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
