/** @odoo-module **/

import { Component, onWillStart, onWillUnmount, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

export class ProductClassification extends Component {
    static template = "ab_website_sale_product.ProductClassification";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.runId = this.props.action.params?.run_id || false;
        this.state = useState({ loading: true, busy: false, error: "", scope: this.props.action.params?.scope || "website", batchSize: 250, websiteId: this.props.action.params?.website_id || false, data: null });
        this.alive = true;
        this.refreshSequence = 0;
        onWillStart(() => this.refresh());
        onWillUnmount(() => { this.alive = false; clearTimeout(this.timer); });
    }

    async refresh() {
        clearTimeout(this.timer);
        const sequence = ++this.refreshSequence;
        try {
            const data = await this.orm.call("ab_product_classification_run", "dashboard", [], {
                run_id: this.runId, scope: this.state.scope, website_id: this.state.websiteId,
            });
            if (!this.alive || sequence !== this.refreshSequence) return;
            this.state.data = data;
            this.state.websiteId = data.website_id;
            this.runId = data.run?.id || false;
            this.state.error = "";
        } catch (error) {
            if (this.alive && sequence === this.refreshSequence) this.state.error = error.data?.message || _t("Progress could not be refreshed. Retrying automatically.");
        } finally {
            if (this.alive && sequence === this.refreshSequence) {
                this.state.loading = false;
                this.timer = setTimeout(() => this.refresh(), 3000);
            }
        }
    }

    get canStart() {
        return this.state.data?.taxonomy_ready && !["queued", "running", "paused", "stopping"].includes(this.state.data?.run?.state) && !["queued", "running"].includes(this.state.data?.run?.force?.state);
    }

    async perform(method) {
        if (this.state.busy) return;
        this.state.busy = true;
        try {
            if (method === "start_classification") {
                this.runId = await this.orm.call("ab_product_classification_run", method, [], {
                    scope: this.state.scope, website_id: this.state.websiteId, batch_size: Number(this.state.batchSize),
                });
            } else {
                const applied = await this.orm.call("ab_product_classification_run", method, [[this.runId]]);
                if (applied === false) {
                    this.notification.add(_t("The request is queued and will apply after the current batch."), { type: "info" });
                }
            }
            await this.refresh();
        } catch (error) {
            this.notification.add(error.data?.message || _t("The classification action failed. Please try again."), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    async prepareTaxonomy() {
        this.state.busy = true;
        try {
            const result = await this.orm.call("ab_product_classification_taxonomy", "action_prepare", []);
            if (result.unresolved.length) {
                this.notification.add(_t("Some categories need an administrator to resolve their existing name or parent in Taxonomy Bindings."), { type: "warning", sticky: true });
                await this.openTaxonomy();
            }
            await this.refresh();
        } catch (error) {
            this.notification.add(error.data?.message || _t("Taxonomy preparation failed."), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    async openForce(method) {
        if (this.state.busy) return;
        this.state.busy = true;
        try {
            const action = await this.orm.call("ab_product_classification_run", method, [[this.runId]]);
            await this.action.doAction(action);
        } catch (error) {
            this.notification.add(error.data?.message || _t("The force categorization action failed. Please try again."), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    openTaxonomy() {
        return this.action.doAction("ab_website_sale_product.classification_taxonomy_action");
    }

    openDescriptions() {
        return this.action.doAction("ab_website_sale_product.classification_roots_action");
    }

    openRuns() {
        return this.action.doAction("ab_website_sale_product.classification_run_action");
    }

    openResults(status = false, rootId = false) {
        const domain = [["run_id", "=", this.runId]];
        if (status) domain.push(["status", "=", status]);
        if (rootId) domain.push(["root_id", "=", rootId]);
        return this.action.doAction({
            type: "ir.actions.act_window", name: status === "needs_review" ? _t("Review Queue") : _t("Classification Results"),
            res_model: "ab_product_classification_result", views: [[false, "list"], [false, "form"]], domain,
        });
    }

    async changeScope(event) {
        this.runId = false;
        this.state.scope = event.target.value;
        await this.refresh();
    }

    async changeWebsite(event) {
        this.runId = false;
        this.state.websiteId = Number(event.target.value);
        await this.refresh();
    }
}

registry.category("actions").add("ab_product_classification", ProductClassification);
