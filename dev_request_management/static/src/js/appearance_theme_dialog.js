/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { useService } from "@web/core/utils/hooks";

export class DevRequestAppearanceDialog extends Component {
    static components = { Dialog };
    static template = "dev_request_management.AppearanceDialog";
    static props = {
        close: Function,
    };

    setup() {
        this.notification = useService("notification");
        this.appearance = useService("dev_request_appearance");
        const payload = this.appearance.getPayload() || {};
        this.state = useState({
            activeTab: "colors",
            scope: payload.can_edit_global ? "global" : "user",
            settings: {
                ...payload,
            },
            importExportJson: "",
            saving: false,
        });
    }

    onFieldInput(field, ev) {
        let value = ev.target.type === "checkbox" ? ev.target.checked : ev.target.value;
        if (ev.target.type === "range" || ev.target.type === "number") {
            value = Number(value);
        }
        this.state.settings[field] = value;
        this.appearance.previewTheme(this.state.settings);
    }

    onChangeScope(ev) {
        this.state.scope = ev.target.value;
    }

    async onBackgroundFileSelected(ev) {
        const file = ev.target.files?.[0];
        if (!file) {
            return;
        }
        const base64Value = await new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(reader.result);
            reader.onerror = reject;
            reader.readAsDataURL(file);
        });
        this.state.settings.background_image = base64Value;
        this.state.settings.background_image_src = base64Value;
        this.state.settings.background_type = "image";
        this.appearance.previewTheme(this.state.settings);
    }

    async save() {
        this.state.saving = true;
        try {
            const payload = { ...this.state.settings };
            if (payload.background_image?.startsWith("data:")) {
                payload.background_image = payload.background_image.split(",", 1)[1];
            }
            await this.appearance.saveTheme(payload, this.state.scope);
            this.notification.add("Appearance settings saved.", { type: "success" });
            this.props.close();
        } catch (error) {
            this.notification.add(error?.message || "Unable to save appearance settings.", { type: "danger" });
        } finally {
            this.state.saving = false;
        }
    }

    async applyPreset(presetTheme) {
        try {
            const payload = await this.appearance.applyPreset(presetTheme, this.state.scope);
            Object.assign(this.state.settings, payload);
            this.notification.add(`Preset ${presetTheme} applied.`, { type: "info" });
        } catch (error) {
            this.notification.add(error?.message || "Unable to apply preset.", { type: "danger" });
        }
    }

    async resetTheme() {
        try {
            const payload = await this.appearance.resetTheme(this.state.scope);
            Object.assign(this.state.settings, payload);
            this.notification.add("Theme reset to default.", { type: "warning" });
        } catch (error) {
            this.notification.add(error?.message || "Unable to reset theme.", { type: "danger" });
        }
    }

    async exportTheme() {
        try {
            const payloadJson = await this.appearance.exportTheme(this.state.scope);
            this.state.importExportJson = payloadJson;
            if (navigator.clipboard?.writeText) {
                await navigator.clipboard.writeText(payloadJson);
            }
            this.notification.add("Theme JSON exported.", { type: "success" });
        } catch (error) {
            this.notification.add(error?.message || "Unable to export theme.", { type: "danger" });
        }
    }

    async importTheme() {
        if (!this.state.importExportJson?.trim()) {
            this.notification.add("Paste theme JSON before importing.", { type: "warning" });
            return;
        }
        try {
            const payload = await this.appearance.importTheme(this.state.importExportJson, this.state.scope);
            Object.assign(this.state.settings, payload);
            this.notification.add("Theme JSON imported.", { type: "success" });
        } catch (error) {
            this.notification.add(error?.message || "Unable to import theme.", { type: "danger" });
        }
    }

    setTab(tabName) {
        this.state.activeTab = tabName;
    }
}
