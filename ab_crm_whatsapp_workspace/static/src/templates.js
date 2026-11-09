import {Component, onMounted, useState} from "@odoo/owl";
import {Dialog} from "@web/core/dialog/dialog";
import {_t} from "@web/core/l10n/translation";
import {patch} from "@web/core/utils/patch";
import {SalesWorkspace} from "@ab_crm_sales_workspace/workspace";

export class WhatsAppTemplates extends Component {
    static template = "ab_crm_whatsapp_workspace.Templates";
    static components = {Dialog};
    static props = {call: Function, conversationId: Number, close: Function};
    setup() {
        this.title = _t("Approved WhatsApp templates");
        this.state = useState({items: [], selected: false, values: {}, query: "", busy: true, error: ""});
        onMounted(async () => {
            try {
                this.state.items = await this.props.call("ab_crm_conversation", "whatsapp_templates", [[this.props.conversationId]]);
                this.state.selected = this.state.items[0]?.id || false;
            } catch (error) {
                this.state.error = error.data?.message || error.message;
            } finally { this.state.busy = false; }
        });
    }
    get selected() { return this.state.items.find(item => item.id === this.state.selected); }
    get filteredItems() {
        const query = this.state.query.trim().toLocaleLowerCase();
        return this.state.items.filter(item => `${item.name} ${item.language} ${item.body}`.toLocaleLowerCase().includes(query));
    }
    get missingValues() { return !this.selected || this.selected.parameters.some(index => !this.state.values[index]?.trim()); }
    get preview() { return (this.selected?.body || "").replace(/\{\{\s*(\d+)\s*\}\}/g, (match, index) => this.state.values[index]?.trim() || match); }
    select(id) { this.state.selected = id; this.state.values = {}; }
    async send() {
        if (this.state.busy || this.missingValues) return;
        this.state.busy = true;
        try {
            await this.props.call("ab_crm_conversation", "action_whatsapp_template", [[this.props.conversationId], this.selected.id], {parameters: this.selected.parameters.map(index => this.state.values[index]?.trim() || "")});
            this.props.close();
        } catch (error) {
            this.state.error = error.data?.message || error.message;
        } finally {
            this.state.busy = false;
        }
    }
}

patch(SalesWorkspace.prototype, {
    messageStateLabel(state) {
        if (this.state.detail?.provider === "whatsapp") {
            if (state === "waiting") return _t("Queued");
            if (state === "sent") return _t("Accepted");
        }
        return super.messageStateLabel(state);
    },
    whatsappTemplates() {
        this.dialog.add(WhatsAppTemplates, {call: this.call.bind(this), conversationId: this.state.detail.id});
    },
});
