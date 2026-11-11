import {useChatterFeedback, useChatterNotice, feedbackError} from "./feedback";
import {Component, onMounted, onWillUnmount, useRef, useState} from "@odoo/owl";
import {Dialog} from "@web/core/dialog/dialog";
import {localization} from "@web/core/l10n/localization";
import {_t} from "@web/core/l10n/translation";

export class ChatterContacts extends Component {
    static template = "ab_crm_sales_workspace.Contacts";
    static components = {Dialog};
    static props = ["close", "mode", "call", "token", "onSaved", "initial?", "conversationId?", "branchId?", "channel?", "onLink?", "onMerge?", "pick?"];
    setup() {
        this.direction = localization.direction;
        this.title = {add: _t("Add contact"), edit: _t("Edit contact"), delete: _t("Archive contact"), link: _t("Link to existing contact"), consolidate: _t("Consolidate duplicate contact")}[this.props.mode];
        this.searchRef = useRef("search");
        this.nameRef = useRef("name");
        this.state = useState({query: this.props.initial?.display_phone || this.props.initial?.phone || this.props.initial?.name || "", posCustomers: [], posStores: [], posStore: "", posMessage: "", contactMode: "existing", contacts: [], branches: [], branch: "", offset: 0, more: false, loading: false, error: "", editing: false, selected: null, name: "", phone: "", address: "", duplicates: null, confirmedDuplicate: false, preview: null, reason: "", resolveConflict: false, customerConfirmed: false, phones: [], newPhone: "", phoneLabel: "", sharedNumber: false, reviewNumbers: [], accounts: [], proposedPhone: this.props.initial?.display_phone || this.props.initial?.phone || ""});
        this.feedback = useChatterFeedback(this);
        useChatterNotice(() => this.state.reviewNumbers.length ? {message: `${_t("Numbers awaiting review:")} ${this.state.reviewNumbers.join(", ")}`} : null,
            () => [this.state.reviewNumbers.join(",")]);
        useChatterNotice(() => this.state.duplicates?.length ? {message: _t("Potential duplicates. Select an existing contact or save separately.")} : null,
            () => [this.state.duplicates?.map(contact => contact.id).join(",")]);
        if (this.props.initial) {
            Object.assign(this.state, {name: this.props.initial.name || "", phone: this.props.initial.display_phone || this.props.initial.phone || "", address: this.props.initial.address || "", branch: String(this.props.initial.branch_id || "")});
            if (["edit", "link", "delete"].includes(this.props.mode) && this.props.initial.id) this.select(this.props.initial);
        }
        this.request = 0;
        onMounted(async () => { await this.search(); this.searchRef.el?.focus(); this.nameRef.el?.focus(); });
        onWillUnmount(() => { clearTimeout(this.timer); this.request++; });
    }
    createNew() {
        Object.assign(this.state, {contactMode: "new", editing: true, selected: null, name: this.props.initial?.name || "",
            phone: this.state.proposedPhone, address: this.props.initial?.address || "", phones: [], accounts: [],
            duplicates: null, confirmedDuplicate: false, newPhone: "", reason: "", customerConfirmed: false, sharedNumber: false});
        requestAnimationFrame(() => this.nameRef.el?.focus());
    }
    existingMode() {
        Object.assign(this.state, {contactMode: "existing", editing: false, selected: null});
        this.search();
    }
    async searchPos(lookup = false) {
        if (!this.state.branch) return;
        const query = this.state.query;
        const branch = this.state.branch;
        try {
            const result = await this.api("contact_pos_search", {query, branch_id: Number(branch), lookup, store_id: Number(this.state.posStore) || false});
            if (query !== this.state.query || branch !== this.state.branch) return;
            this.state.posCustomers = result.customers || [];
            this.state.posStores = result.stores || [];
            if (!this.state.posStores.some(store => store.id === Number(this.state.posStore))) this.state.posStore = "";
            this.state.posMessage = result.message || "";
        } catch (error) { this.state.posMessage = feedbackError(this, error); }
    }
    async selectPos(customer) {
        if (this.state.loading) return;
        this.state.loading = true;
        try {
            const contact = await this.api("contact_pos_select", {customer_id: customer.id,
                branch_id: Number(this.state.branch), contact_id: this.state.selected?.id || false});
            await this.props.onSaved(contact);
            this.props.close();
        } catch (error) { this.state.error = feedbackError(this, error); }
        finally { this.state.loading = false; }
    }
    channelLabel(provider) { return {telegram: _t("Telegram"), whatsapp: _t("WhatsApp"), website: _t("Website"), application: _t("Application")}[provider] || provider; }
    api(method, values = {}) { return this.props.call("ab_crm_chatter_api", method, [], {token: this.props.token, ...values}); }
    async search() {
        const request = ++this.request;
        this.state.loading = true;
        try {
            const values = {query: this.state.query, offset: this.state.offset};
            if (this.props.mode === "link" && this.props.branchId) values.branch_id = this.props.branchId;
            const result = await this.api("contact_search", values);
            if (request !== this.request) return;
            this.state.contacts = result.contacts; this.state.more = result.has_more;
            this.state.branches = result.branches;
            if (!this.state.branch) this.state.branch = String(result.branches[0]?.id || "");
            if (this.props.mode === "add") await this.searchPos();
        } catch (error) { this.state.error = feedbackError(this, error); }
        finally { if (request === this.request) this.state.loading = false; }
    }
    queryChanged() { clearTimeout(this.timer); this.request++; this.state.offset = 0; this.timer = setTimeout(() => this.search(), 250); }
    page(direction) { this.state.offset += direction * 30; return this.search(); }
    async select(contact) {
        if (this.props.pick) { await this.props.onSaved(contact); this.props.close(); return; }
        if (this.props.mode === "consolidate") {
            this.state.loading = true; this.state.error = "";
            try {
                this.state.preview = await this.api("contact_consolidate", {canonical_id: this.props.initial.id, duplicate_id: contact.id});
                this.state.selected = contact; this.state.editing = true;
            } catch (error) { this.state.error = feedbackError(this, error); }
            finally { this.state.loading = false; }
            return;
        }
        if (this.props.mode === "link") {
            this.state.loading = true; this.state.error = "";
            try {
                this.state.preview = await this.props.call("ab_crm_conversation", "action_preview_customer_link", [[this.props.conversationId], contact.id]);
                if (this.state.preview.automatic_match) {
                    await this.props.call("ab_crm_conversation", "action_confirm_customer_link", [[this.props.conversationId], contact.id, this.state.preview.fingerprint]);
                    await this.props.onSaved(contact);
                    this.props.close();
                    return;
                }
                this.state.selected = contact; this.state.editing = true;
            } catch (error) { this.state.error = feedbackError(this, error); }
            finally { this.state.loading = false; }
            return;
        }
        this.state.selected = contact; this.state.editing = true; this.state.duplicates = null;
        Object.assign(this.state, {name: contact.name, phone: contact.display_phone || contact.phone, address: contact.address, branch: String(contact.branch_id), phones: contact.phones || []});
        if (this.props.mode === "add") this.state.newPhone = this.state.proposedPhone;
        if (["add", "edit"].includes(this.props.mode)) {
            try {
                this.state.query = contact.display_phone || contact.phone || contact.name;
                await this.searchPos();
                const detail = await this.api("contact_accounts", {contact_id: contact.id});
                if (this.state.selected?.id === contact.id) this.state.accounts = detail.accounts || [];
            } catch (error) { this.state.error = feedbackError(this, error); }
        }
        requestAnimationFrame(() => this.nameRef.el?.focus());
    }
    async save() {
        if (this.state.loading) return;
        this.state.loading = true; this.state.error = "";
        try {
            if (this.props.mode === "consolidate") {
                const contact = await this.api("contact_consolidate", {canonical_id: this.props.initial.id, duplicate_id: this.state.selected.id, fingerprint: this.state.preview.fingerprint, reason: this.state.reason});
                await this.props.onSaved(contact); this.props.close(); return;
            }
            if (this.props.mode === "link") {
                await this.props.call("ab_crm_conversation", "action_confirm_customer_link", [[this.props.conversationId], this.state.selected.id, this.state.preview.fingerprint], {resolve_conflict: this.state.resolveConflict});
                await this.props.onSaved(this.state.selected); this.props.close(); return;
            }
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
        } catch (error) { this.state.error = feedbackError(this, error); }
        finally { this.state.loading = false; }
    }
    async phoneAction(action, phone = null) {
        if (this.state.loading) return;
        this.state.loading = true; this.state.error = "";
        try {
            const contact = action === "initialize"
                ? await this.api("contact_initialize_phones", {contact_id: this.state.selected.id})
                : action === "add"
                ? await this.api("contact_phone_add", {contact_id: this.state.selected.id, number: this.state.newPhone, label: this.state.phoneLabel, reason: this.state.reason, customer_confirmed: this.state.customerConfirmed, resolve_shared: this.state.sharedNumber})
                : await this.api("contact_phone_update", {contact_id: this.state.selected.id, phone_id: phone.id, action, reason: this.state.reason, label: phone.label});
            this.state.phones = contact.phones; this.state.phone = contact.display_phone || contact.phone;
            this.state.reviewNumbers = contact.review_display_numbers || contact.review_numbers || [];
            this.state.selected = contact; this.state.newPhone = ""; this.state.phoneLabel = "";
            await this.props.onSaved(contact);
        } catch (error) { this.state.error = feedbackError(this, error); }
        finally { this.state.loading = false; }
    }
    async useExisting(contact) { return this.select(contact); }
}

export class ChatterOrderPhone extends Component {
    static template = "ab_crm_sales_workspace.OrderPhone";
    static components = {Dialog};
    static props = ["close", "phones", "select"];
    setup() { this.title = _t("Choose order phone"); }
    async select(phone) { this.props.close(); await this.props.select(phone.id); }
}
