/** @odoo-module **/

import { rpc } from "@web/core/network/rpc";

async function openTelegramBot() {
    const url = await rpc(
        "/web/dataset/call_kw/ab_supplier_claim_cycle/get_telegram_bot_url",
        {
            model: "ab_supplier_claim_cycle",
            method: "get_telegram_bot_url",
            args: [],
            kwargs: {},
        }
    );
    if (url) {
        window.open(url, "_blank", "noopener,noreferrer");
    }
}

document.addEventListener(
    "click",
    (event) => {
        const button = event.target.closest("[data-scc-open-telegram-bot]");
        if (!button) {
            return;
        }
        event.preventDefault();
        event.stopPropagation();
        event.stopImmediatePropagation();
        openTelegramBot();
    },
    true
);
