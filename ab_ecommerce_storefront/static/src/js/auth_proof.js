import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";

class AuthProof extends Interaction {
    static selector = "[data-ab-proof-page]";

    start() {
        const token = window.location.hash.slice(1);
        const form = this.el.querySelector("[data-ab-email-proof]");
        if (!form || !/^[A-Za-z0-9_-]{43}$/.test(token)) {
            return;
        }
        form.querySelector("input[name='proof']").value = token;
        form.hidden = false;
        const content = this.el.querySelector("[data-ab-without-proof]");
        if (content) {
            content.hidden = true;
        }
        window.history.replaceState(null, "", window.location.pathname);
    }
}

registry.category("public.interactions").add("ab_ecommerce_storefront.auth_proof", AuthProof);
