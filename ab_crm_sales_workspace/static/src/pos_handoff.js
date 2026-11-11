import "@ab_sales/pos/pos_action";
import {registry} from "@web/core/registry";
import {useEffect, onWillUnmount} from "@odoo/owl";
import {useService} from "@web/core/utils/hooks";
import {user} from "@web/core/user";
import {_t} from "@web/core/l10n/translation";

const PosAction = registry.category("actions").get("ab_sales.pos");

export class CrmPosAction extends PosAction {
    setup() {
        super.setup();
        this.crmSession = useService("ab_chatter_session");
        const key = `ab_crm_pos_handoff:${user.userId}:${user.activeCompany.id}`;
        this.crmHandoffId = this.props.action.context?.crm_handoff_id || Number(sessionStorage.getItem(key));
        if (this.crmHandoffId) sessionStorage.setItem(key, String(this.crmHandoffId));
        this.crmSyncing = new Set();
        this.crmAcknowledged = new Map();
        this.crmStopped = false;
        onWillUnmount(() => { this.crmStopped = true; });
        useEffect(() => {
            if (this.state.draftCacheReady && this.state.abSalesHr?.session?.state === "active") {
                this.resumeHandoff().catch(error => this.crmError(error, () => this.resumeHandoff()));
            }
        }, () => [this.state.draftCacheReady, this._posDraftSessionToken()]);
        useEffect(() => {
            for (const bill of this.state.bills) {
                if (bill.crm_handoff_id && bill.crm_prefilled &&
                    this.crmAcknowledged.get(bill.id) !== (bill.header.customer_id || false)) {
                    this.syncContact(bill);
                }
            }
        }, () => [this.state.bills.map(bill => `${bill.id}:${bill.crm_prefilled}:${bill.header.customer_id}`).join("|"), this._posDraftSessionToken()]);
    }

    crmCall(method, values = {}) {
        return this.orm.call("ab_crm_chatter_api", method, [], {
            token: this.crmSession.current?.token || "",
            pos_token: this._posDraftSessionToken(), handoff_id: this.crmHandoffId, ...values,
        });
    }

    crmError(error, retry) {
        if (this.crmStopped) return;
        this.notification.add(this._getRpcErrorMessage(error), {
            type: "warning", sticky: true,
            buttons: [{name: _t("Retry CRM update"), onClick: () => Promise.resolve(retry()).catch(next => this.crmError(next, retry))}],
        });
    }

    async resumeHandoff() {
        if (!this.crmHandoffId || this.crmOpening || this.crmReady) return;
        this.crmOpening = true;
        try {
            const scope = this._draftRequestScope();
            const data = await this.crmCall("pos_handoff_prepare");
            if (this.crmStopped || scope !== this._draftRequestScope()) return;
            this.crmReturnConversation = data.conversation_id;
            this.crmReturnContact = data.id;
            const existing = this.state.bills.find(bill => bill.crm_handoff_id === this.crmHandoffId || bill.id === data.draft_token);
            if (existing) {
                this.selectBill(existing.id);
                if (!existing.crm_prefilled) await this.prefillHandoff(existing, data);
                await this.syncContact(existing);
                this.crmReady = true;
            } else if (data.draft_token) {
                await this.crmCall("pos_handoff_sync", {draft_token: data.draft_token});
                this.crmReady = true;
                this.notification.add(data.draft_state === "completed"
                    ? _t("This handoff has already been invoiced. Open Invoices to view it.")
                    : _t("This handoff already has a saved POS draft. Restore it from POS drafts."), {type: "info"});
            } else {
                this.crmPending = true;
                await this.openNewBillDialog();
            }
        } finally { this.crmOpening = false; }
    }

    async createNewBill(storeId) {
        if (!this.crmPending || !this.crmHandoffId) return super.createNewBill(storeId);
        if (this.crmCreating) return;
        this.crmCreating = true;
        try {
            const scope = this._draftRequestScope();
            const data = await this.crmCall("pos_handoff_prepare", {store_id: storeId});
            if (this.crmStopped || scope !== this._draftRequestScope()) return;
            if (data.draft_token) return this.resumeHandoff();
            const occupied = new Set(this.state.bills.map(bill => bill.id));
            const slot = this.emptyDraftSlots.find(candidate => !candidate.bill);
            if (!slot) { this._draftLimitWarning(); return; }
            this._requestedDraftSlot = slot.number;
            const created = await super.createNewBill(storeId);
            if (!created || this.crmStopped || scope !== this._draftRequestScope()) return;
            const bill = this.currentBill;
            if (!bill || occupied.has(bill.id)) throw new Error(_t("Create a separate POS draft for this contact."));
            await this.crmCall("pos_handoff_claim", {draft_token: bill.id, store_id: storeId});
            if (this.crmStopped || scope !== this._draftRequestScope() || this.currentBill !== bill) return;
            bill.crm_handoff_id = this.crmHandoffId;
            this.crmPending = false;
            await this.prefillHandoff(bill, data);
            this.crmReady = true;
            return created;
        } catch (error) { this.crmError(error, () => this.resumeHandoff()); }
        finally { this.crmCreating = false; }
    }

    async prefillHandoff(bill, data) {
        if (bill.crm_prefilled) return;
        const scope = this._draftRequestScope();
        if (data.catalog_customer_id) {
            await this.onCustomerM2OUpdate({id: data.catalog_customer_id, display_name: data.name});
            if (this.crmStopped || scope !== this._draftRequestScope() || this.currentBill !== bill) return;
            if (bill.header.customer_id !== data.catalog_customer_id) throw new Error(_t("Select an active POS customer."));
        } else {
            Object.assign(bill.header, {
                customer_mode: "new", new_customer_name: data.name,
                new_customer_phone: data.phone, new_customer_address: data.address,
            });
        }
        Object.assign(bill.header, {bill_customer_name: data.name, bill_customer_phone: data.phone,
            bill_customer_address: data.address, invoice_address: data.address});
        bill.crm_prefilled = true;
        bill.updated_at = new Date().toISOString();
        this.persistCache();
        await this.syncContact(bill);
    }

    async syncContact(bill) {
        if (this.crmSyncing.has(bill.id) || !bill.crm_prefilled) return;
        this.crmSyncing.add(bill.id);
        const selected = bill.header.customer_id || false;
        try {
            await this._saveCacheToServer({throwOnError: true, force: true});
            const result = await this.crmCall("pos_handoff_sync", {handoff_id: bill.crm_handoff_id, draft_token: bill.id});
            if (selected && result.catalog_customer_id !== selected) throw new Error(_t("Save the POS draft, then retry the CRM update."));
            this.crmAcknowledged.set(bill.id, selected);
        } catch (error) { this.crmError(error, () => this.syncContact(bill)); }
        finally { this.crmSyncing.delete(bill.id); }
    }

    async closeWindow() {
        await this._saveCacheToServer({throwOnError: true, force: true});
        return this.action.doAction("ab_crm_sales_workspace.action_workspace", {additionalContext: {
            chatter_conversation_id: this.crmReturnConversation || false,
            chatter_contact_id: this.crmReturnContact || false,
        }});
    }
}

registry.category("actions").add("ab_crm_sales_workspace.pos", CrmPosAction);
