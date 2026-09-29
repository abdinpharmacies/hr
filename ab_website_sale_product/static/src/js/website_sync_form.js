/** @odoo-module **/

import { onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { FormController } from "@web/views/form/form_controller";
import { formView } from "@web/views/form/form_view";

export class WebsiteSyncFormController extends FormController {
    setup() {
        super.setup();
        this.syncPollActive = false;
        onMounted(() => {
            this.syncPollActive = true;
            this.pollSyncProgress();
        });
        onWillUnmount(() => {
            this.syncPollActive = false;
            clearTimeout(this.syncPollTimer);
        });
    }

    async pollSyncProgress() {
        const record = this.model.root;
        try {
            if (record.resId && !(await record.isDirty())) {
                const progress = await this.orm.call(
                    "ab_website_product_sync_job", "get_background_progress", [[record.resId]]
                );
                if (this.syncPollActive && this.model.root === record && !(await record.isDirty())) {
                    const changed = ["state", "processed_count", "total_count", "already_synced_count", "background_requested", "background_error"]
                        .some((field) => (record.data[field] || false) !== (progress[field] || false));
                    if (changed) {
                        await record.load();
                    }
                }
            }
        } catch (error) {
            console.warn("Website Product Sync progress refresh failed", error);
        } finally {
            if (this.syncPollActive) {
                this.syncPollTimer = setTimeout(() => this.pollSyncProgress(), 2000);
            }
        }
    }
}

registry.category("views").add("ab_website_product_sync_form", {
    ...formView,
    Controller: WebsiteSyncFormController,
});
