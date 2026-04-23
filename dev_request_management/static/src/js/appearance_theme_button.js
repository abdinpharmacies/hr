/** @odoo-module **/

import { Component, useExternalListener, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { DevRequestAppearanceDialog } from "./appearance_theme_dialog";

export class DevRequestAppearanceButton extends Component {
    static template = "dev_request_management.AppearanceButton";
    static props = [];

    setup() {
        this.action = useService("action");
        this.dialog = useService("dialog");
        this.appearance = useService("dev_request_appearance");
        this.state = useState({ tick: 0 });
        useExternalListener(window, "hashchange", () => this.refresh());
    }

    refresh() {
        this.state.tick++;
    }

    get shouldDisplay() {
        const payload = this.appearance.getPayload();
        if (!payload?.can_customize) {
            return false;
        }
        const model = this.action.currentController?.action?.res_model;
        return ["development.request", "ui.appearance.settings"].includes(model);
    }

    openAppearanceDialog() {
        this.dialog.add(DevRequestAppearanceDialog, {});
    }
}

registry.category("systray").add(
    "dev_request_management.appearance_button",
    { Component: DevRequestAppearanceButton },
    { sequence: 1000 }
);
