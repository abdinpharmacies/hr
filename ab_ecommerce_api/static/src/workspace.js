/** @odoo-module **/

import { Component, onMounted, onWillUnmount, useRef, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";

export class ApiWorkspace extends Component {
    static template = "ab_ecommerce_api.Workspace";
    static props = { ...standardActionServiceProps };

    setup() {
        this.frame = useRef("documentation");
        this.state = useState({ tab: "docs", revision: 0, loading: true, error: "" });
        this.baseUrl = `${window.location.origin}/api/v1`;
        this.docsUrl = `/api/v1/docs?embedded=1&lang=${encodeURIComponent(user.context.lang || "en_US")}`;
        onMounted(() => this.startTimeout());
        onWillUnmount(() => window.clearTimeout(this.timeout));
    }

    startTimeout() {
        window.clearTimeout(this.timeout);
        this.timeout = window.setTimeout(() => {
            if (this.state.loading) {
                this.state.loading = false;
                this.state.error = _t("Documentation took too long to load. Check your connection and retry.");
            }
        }, 20000);
    }

    onFrameLoaded() {
        window.clearTimeout(this.timeout);
        this.state.loading = false;
        try {
            const root = this.frame.el.contentDocument?.getElementById("ab-ecommerce-api-swagger");
            this.state.error = root ? "" : _t("Documentation is unavailable. Sign in as a System Administrator and retry.");
        } catch {
            this.state.error = _t("Documentation is unavailable. Sign in as a System Administrator and retry.");
        }
    }

    reloadDocs() {
        this.state.error = "";
        this.state.loading = true;
        this.state.revision++;
        this.startTimeout();
    }

    showDocs() {
        this.state.tab = "docs";
    }

    showGuide() {
        this.state.tab = "guide";
    }
}

registry.category("actions").add("ab_ecommerce_api.workspace", ApiWorkspace);
