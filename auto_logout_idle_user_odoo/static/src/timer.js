/** @odoo-module **/
import { Component, reactive, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

export function remainingSeconds(deadline, now) {
    return Math.max(0, Math.ceil((deadline - now) / 1000));
}

registry.category("services").add("ab_idle_logout", {
    async start() {
        const minutes = await rpc("/get_idle_time/timer");
        const state = reactive({ enabled: Boolean(minutes), seconds: 0 });
        if (!minutes) return state;
        const duration = minutes * 60000;
        let deadline = Date.now() + duration;
        let expired = false;
        const tick = () => {
            state.seconds = remainingSeconds(deadline, Date.now());
            if (!state.seconds && !expired) {
                expired = true;
                window.location.assign("/web/session/logout");
            }
        };
        const reset = (event) => {
            // Synthetic activity cannot keep a session alive. Never revive an expired timer.
            tick();
            if (!expired && event.isTrusted) deadline = Date.now() + duration;
        };
        for (const name of ["mousemove", "keydown", "click", "touchstart", "mousedown"]) {
            window.addEventListener(name, reset, { passive: true });
        }
        document.addEventListener("visibilitychange", tick);
        window.addEventListener("pageshow", tick);
        tick();
        window.setInterval(tick, 1000);
        return state;
    },
});

class IdleCountdown extends Component {
    static template = "auto_logout_idle_user_odoo.Countdown";
    static props = {};
    setup() {
        this.timer = useState(useService("ab_idle_logout"));
        this.label = _t("Idle logout countdown");
    }
    get countdown() {
        const seconds = this.timer.seconds;
        return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
    }
}
registry.category("systray").add("auto_logout_idle_user_odoo.countdown", { Component: IdleCountdown });
