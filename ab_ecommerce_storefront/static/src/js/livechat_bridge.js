/** @odoo-module **/

import { registry } from "@web/core/registry";
import { session } from "@web/session";

registry.category("services").add("ab_ecommerce_storefront.livechat_bridge", {
    dependencies: ["im_livechat.livechat", "mail.store"],
    start(env, services) {
        if (!session.livechatData?.can_load_livechat) {
            return {};
        }

        const activate = () => {
            if (!document.body?.classList.contains("ab-storefront")) {
                return;
            }
            document.body.classList.add("ab-livechat-integrated");
            const markRoot = () => {
                const root = document.querySelector(".o-livechat-root");
                if (!root) {
                    return false;
                }
                root.classList.add("ab-storefront-livechat");
                return true;
            };
            if (!markRoot()) {
                const observer = new MutationObserver(() => {
                    if (markRoot()) {
                        observer.disconnect();
                    }
                });
                observer.observe(document.body, { childList: true });
            }
            window.dispatchEvent(new Event("ab-storefront:livechat-ready"));
        };
        const open = async () => {
            if (!document.body?.classList.contains("ab-storefront")) {
                return;
            }
            const store = services["mail.store"];
            const activeThread = store.activeLivechats[0];
            if (activeThread) {
                await activeThread.openChatWindow({ focus: true });
            } else {
                await services["im_livechat.livechat"].open();
            }
        };

        window.addEventListener("ab-storefront:open-livechat", open);
        if (document.readyState === "loading") {
            document.addEventListener("DOMContentLoaded", activate, { once: true });
        } else {
            activate();
        }
        return {};
    },
});
