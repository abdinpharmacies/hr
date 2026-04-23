/** @odoo-module **/

import { Reactive } from "@web/core/utils/reactive";
import { registry } from "@web/core/registry";

class DevRequestAppearanceService extends Reactive {
    constructor(env, orm) {
        super();
        this.env = env;
        this.orm = orm;
        this.payload = null;
    }

    _defaultPayload() {
        return {
            id: false,
            name: "Global Development Requests Theme",
            scope: "global",
            theme_mode: "light",
            effective_mode: "light",
            preset_theme: "default",
            primary_color: "#1e4f8c",
            secondary_color: "#f4f7fb",
            accent_color: "#2e9cca",
            text_color: "#1f2937",
            background_type: "solid",
            background_color: "#eef4fb",
            background_gradient: "linear-gradient(135deg, #eef4fb 0%, #dfeaf7 100%)",
            background_image_url: "",
            background_image_src: "",
            background_image_opacity: 0.2,
            background_image_blur: 0,
            background_image_size: "cover",
            enable_parallax: false,
            card_style: "shadowed",
            card_border_radius: 14,
            font_family: "Inter, 'Segoe UI', sans-serif",
            font_size_base: 14,
            kanban_density: "normal",
            enable_animations: true,
            enable_hover_effects: true,
            auto_dark_mode: false,
            custom_css: "",
            can_customize: false,
            can_edit_global: false,
            can_edit_personal: true,
        };
    }

    async load() {
        try {
            this.payload = await this.orm.silent.call(
                "ui.appearance.settings",
                "get_current_theme_payload",
                [],
                {}
            );
        } catch {
            this.payload = this._defaultPayload();
        }
        this.applyTheme(this.payload);
        return this.payload;
    }

    getPayload() {
        return this.payload;
    }

    _ensureStyleNode() {
        let styleNode = document.getElementById("o_dev_request_custom_css");
        if (!styleNode) {
            styleNode = document.createElement("style");
            styleNode.id = "o_dev_request_custom_css";
            document.head.appendChild(styleNode);
        }
        return styleNode;
    }

    _toBackground(payload) {
        if (payload.background_type === "gradient" && payload.background_gradient) {
            return payload.background_gradient;
        }
        if (payload.background_type === "image") {
            return payload.background_image_src || payload.background_image_url || payload.background_color;
        }
        return payload.background_color || "#eef4fb";
    }

    _computeTextContrast(color, fallback = "#111827") {
        if (!color || !color.startsWith("#") || color.length < 7) {
            return fallback;
        }
        const r = parseInt(color.slice(1, 3), 16);
        const g = parseInt(color.slice(3, 5), 16);
        const b = parseInt(color.slice(5, 7), 16);
        const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
        return luminance > 0.65 ? "#111827" : "#f8fafc";
    }

    applyTheme(payload) {
        if (!payload) {
            payload = this._defaultPayload();
        }
        this.payload = payload;
        const root = document.documentElement;
        const textOnPrimary = this._computeTextContrast(payload.primary_color);
        root.style.setProperty("--devreq-primary-color", payload.primary_color || "#1e4f8c");
        root.style.setProperty("--devreq-secondary-color", payload.secondary_color || "#f4f7fb");
        root.style.setProperty("--devreq-accent-color", payload.accent_color || "#2e9cca");
        root.style.setProperty("--devreq-text-color", payload.text_color || "#1f2937");
        root.style.setProperty("--devreq-text-on-primary", textOnPrimary);
        root.style.setProperty("--devreq-background", this._toBackground(payload));
        root.style.setProperty("--devreq-card-radius", `${payload.card_border_radius || 14}px`);
        root.style.setProperty("--devreq-font-size", `${payload.font_size_base || 14}px`);
        root.style.setProperty("--devreq-font-family", payload.font_family || "Inter, 'Segoe UI', sans-serif");
        root.style.setProperty("--devreq-background-opacity", payload.background_image_opacity ?? 0.2);
        root.style.setProperty("--devreq-background-blur", `${payload.background_image_blur || 0}px`);
        root.style.setProperty("--devreq-background-size", payload.background_image_size || "cover");
        root.style.setProperty("--devreq-card-padding", payload.kanban_density === "compact" ? "0.75rem" : payload.kanban_density === "spacious" ? "1.35rem" : "1rem");
        root.style.setProperty("--devreq-card-gap", payload.kanban_density === "compact" ? "0.5rem" : payload.kanban_density === "spacious" ? "1rem" : "0.75rem");
        root.style.setProperty("--devreq-background-image", payload.background_type === "image" && (payload.background_image_src || payload.background_image_url) ? `url("${payload.background_image_src || payload.background_image_url}")` : "none");
        document.body.classList.toggle("o_dev_request_theme_dark", payload.effective_mode === "dark");
        document.body.classList.toggle("o_dev_request_theme_animations", !!payload.enable_animations);
        document.body.classList.toggle("o_dev_request_theme_hover", !!payload.enable_hover_effects);
        document.body.dataset.devreqCardStyle = payload.card_style || "shadowed";
        document.body.dataset.devreqBackgroundType = payload.background_type || "solid";
        const styleNode = this._ensureStyleNode();
        styleNode.textContent = payload.custom_css || "";
    }

    previewTheme(payload) {
        const previewPayload = {
            ...(this.payload || {}),
            ...payload,
        };
        previewPayload.effective_mode = previewPayload.auto_dark_mode
            ? ((new Date().getHours() >= 18 || new Date().getHours() < 6) ? "dark" : previewPayload.theme_mode)
            : previewPayload.theme_mode;
        if (previewPayload.background_image && !previewPayload.background_image_src) {
            previewPayload.background_image_src = previewPayload.background_image.startsWith("data:")
                ? previewPayload.background_image
                : `data:image/*;base64,${previewPayload.background_image}`;
        }
        this.applyTheme(previewPayload);
    }

    async saveTheme(payload, scope = "auto") {
        this.payload = await this.orm.call("ui.appearance.settings", "save_theme_payload", [payload, scope], {});
        this.applyTheme(this.payload);
        return this.payload;
    }

    async applyPreset(presetTheme, scope = "auto") {
        this.payload = await this.orm.call("ui.appearance.settings", "apply_preset_theme", [presetTheme, scope], {});
        this.applyTheme(this.payload);
        return this.payload;
    }

    async resetTheme(scope = "auto") {
        this.payload = await this.orm.call("ui.appearance.settings", "reset_theme_payload", [scope], {});
        this.applyTheme(this.payload);
        return this.payload;
    }

    async exportTheme(scope = "auto") {
        return await this.orm.call("ui.appearance.settings", "export_theme_payload", [scope], {});
    }

    async importTheme(payloadJson, scope = "auto") {
        this.payload = await this.orm.call("ui.appearance.settings", "import_theme_payload", [payloadJson, scope], {});
        this.applyTheme(this.payload);
        return this.payload;
    }
}

registry.category("services").add("dev_request_appearance", {
    dependencies: ["orm"],
    async start(env, { orm }) {
        const service = new DevRequestAppearanceService(env, orm);
        await service.load();
        return service;
    },
});
