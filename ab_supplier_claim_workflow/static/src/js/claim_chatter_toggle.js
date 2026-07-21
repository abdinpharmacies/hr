/** @odoo-module **/
import { registry } from "@web/core/registry";
import { onMounted, onRendered } from "@odoo/owl";
import { FormController } from "@web/views/form/form_controller";
import { formView } from "@web/views/form/form_view";

const STORAGE_KEY = "claim_chatter_visible";

function getChatterPref() {
    const v = localStorage.getItem(STORAGE_KEY);
    return v === null ? true : v === "true";
}
function setChatterPref(v) {
    localStorage.setItem(STORAGE_KEY, String(v));
}

// Client action handler: toggle localStorage & reload
registry.category("actions").add("toggle_claim_chatter", (env, action) => {
    setChatterPref(!getChatterPref());
    window.location.reload();
});

// Custom form controller for ab_supplier_claim_cycle
// Syncs show_chatter from localStorage on every render
class ClaimFormController extends FormController {
    setup() {
        super.setup();
        onMounted(() => this._syncChatter());
        onRendered(() => this._syncChatter());
    }

    async beforeExecuteActionButton(clickParams) {
        // Gear button (⚙️) opens Supplier Mappings via type="action".
        // All other header buttons in this form are type="object".
        // We skip record.save() here to prevent creating a new claim
        // record (and consuming a sequence number) when the user opens
        // mappings from an unsaved new claim form.
        // The subsequent navigation to the mapping triggers
        // clearUncommittedChanges → beforeLeave which handles
        // dirty/unsaved records identically to a navbar menu click.
        if (clickParams.type === "action") {
            return true;
        }
        return super.beforeExecuteActionButton(clickParams);
    }

    async _syncChatter() {
        if (!this.model?.root) return;
        const record = this.model.root;
        if (record.isNew) return;
        if (!("show_chatter" in (record.data || {}))) return;
        const pref = getChatterPref();
        if (record.data.show_chatter !== pref) {
            await record.update({ show_chatter: pref });
        }
    }
}

// Register custom form view for the claim cycle model
const claimFormView = {
    ...formView,
    Controller: ClaimFormController,
};
registry.category("views").add("ab_supplier_claim_cycle_form", claimFormView);
