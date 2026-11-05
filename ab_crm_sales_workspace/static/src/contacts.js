import {Component, onMounted, onWillUnmount, useRef, useState} from "@odoo/owl";
import {Dialog} from "@web/core/dialog/dialog";
import {localization} from "@web/core/l10n/localization";
import {_t} from "@web/core/l10n/translation";

export class ChatterContacts extends Component {
    static template = "ab_crm_sales_workspace.Contacts";
    static components = {Dialog};
    static props = ["close", "mode", "call", "token", "onSaved"];
    setup() {
        this.direction = localization.direction;
        this.title = {add: _t("Add contact"), edit: _t("Edit contact"), delete: _t("Delete contact")}[this.props.mode];
        this.searchRef = useRef("search");
        this.nameRef = useRef("name");
        this.state = useState({query: "", contacts: [], branches: [], branch: "", offset: 0, more: false, loading: false, error: "", editing: this.props.mode === "add", selected: null, name: "", phone: "", address: "", duplicates: null, confirmedDuplicate: false});
        this.request = 0;
        onMounted(async () => { await this.search(); this.searchRef.el?.focus(); this.nameRef.el?.focus(); });
        onWillUnmount(() => { clearTimeout(this.timer); this.request++; });
    }
    api(method, values = {}) { return this.props.call("ab_crm_chatter_api", method, [], {token: this.props.token, ...values}); }
    async search() {
        const request = ++this.request;
        this.state.loading = true;
        try {
            const result = await this.api("contact_search", {query: this.state.query, offset: this.state.offset});
            if (request !== this.request) return;
            this.state.contacts = result.contacts; this.state.more = result.has_more;
            this.state.branches = result.branches;
            if (!this.state.branch) this.state.branch = String(result.branches[0]?.id || "");
        } catch (error) { this.state.error = error.data?.message || error.message; }
        finally { if (request === this.request) this.state.loading = false; }
    }
    queryChanged() { clearTimeout(this.timer); this.request++; this.state.offset = 0; this.timer = setTimeout(() => this.search(), 250); }
    page(direction) { this.state.offset += direction * 30; return this.search(); }
    select(contact) {
        this.state.selected = contact; this.state.editing = true; this.state.duplicates = null;
        Object.assign(this.state, {name: contact.name, phone: contact.phone, address: contact.address, branch: String(contact.branch_id)});
        requestAnimationFrame(() => this.nameRef.el?.focus());
    }
    async save() {
        if (this.state.loading) return;
        this.state.loading = true; this.state.error = "";
        try {
            if (this.props.mode === "delete") {
                await this.api("contact_archive", {contact_id: this.state.selected.id});
                await this.props.onSaved(); this.props.close(); return;
            }
            if (!this.state.confirmedDuplicate) {
                const result = await this.api("contact_search", {phone: this.state.phone, branch_id: Number(this.state.branch)});
                this.state.duplicates = result.contacts.filter(contact => contact.id !== this.state.selected?.id);
                if (this.state.duplicates.length) return;
            }
            const contact = await this.api("contact_save", {contact_id: this.state.selected?.id || false, branch_id: Number(this.state.branch), values: {name: this.state.name, phone: this.state.phone, address: this.state.address}});
            await this.props.onSaved(contact); this.props.close();
        } catch (error) { this.state.error = error.data?.message || error.message; }
        finally { this.state.loading = false; }
    }
    async useExisting(contact) { await this.props.onSaved(contact); this.props.close(); }
}
