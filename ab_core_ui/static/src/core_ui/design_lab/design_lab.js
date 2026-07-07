/** @odoo-module **/
import { Component, useState } from "@odoo/owl";
import {
    THEME_PACKS, PALETTES, TYPOGRAPHY, SPACING, RADIUS,
    SHADOWS, BORDERS, GRADIENTS, MOTION, HOVER_EFFECTS,
    BUILTIN_PROFILES, DEFAULT_LAB_STATE,
} from "./design_lab_config";
import { ProfilePreviewCard } from "./profile_preview_card";

const SESSION_KEY = "core_ui_design_lab_expanded";

export class CoreUIDesignLab extends Component {
    static template = "core_ui.design_lab";
    static components = { ProfilePreviewCard };
    static props = {
        designLab: { type: Object },
        onUpdate: { type: Function },
        profiles: { type: Array, optional: true },
        onSaveProfile: { type: Function, optional: true },
        onLoadProfile: { type: Function, optional: true },
    };

    setup() {
        const saved = sessionStorage.getItem(SESSION_KEY);
        this.state = useState({
            expandedSection: saved || null,
        });
    }

    get themePacks() { return THEME_PACKS; }
    get palettes() { return PALETTES; }
    get typography() { return TYPOGRAPHY; }
    get spacing() { return SPACING; }
    get radius() { return RADIUS; }
    get shadows() { return SHADOWS; }
    get borders() { return BORDERS; }
    get gradients() { return GRADIENTS; }
    get motion() { return MOTION; }
    get hoverEffects() { return HOVER_EFFECTS; }
    get builtinProfiles() { return BUILTIN_PROFILES; }

    get profileCards() {
        const cards = [{
            key: "default",
            label: "Core UI Default",
            config: {
                theme: DEFAULT_LAB_STATE.theme,
                palette: DEFAULT_LAB_STATE.palette,
                typography: DEFAULT_LAB_STATE.typography,
                spacing: DEFAULT_LAB_STATE.spacing,
                radius: DEFAULT_LAB_STATE.radius,
                shadow: DEFAULT_LAB_STATE.shadow,
                border: DEFAULT_LAB_STATE.border,
                gradient: DEFAULT_LAB_STATE.gradient,
                motion: DEFAULT_LAB_STATE.motion,
                hoverEffects: DEFAULT_LAB_STATE.hoverEffects,
            },
            builtin: true,
        }];
        for (const [key, val] of Object.entries(BUILTIN_PROFILES)) {
            if (key === "default") continue;
            cards.push({
                key,
                label: val.label,
                config: val.config,
                builtin: true,
            });
        }
        try {
            const savedRaw = localStorage.getItem("core_ui_saved_profiles");
            if (savedRaw) {
                const saved = JSON.parse(savedRaw);
                for (const p of saved) {
                    if (!cards.find(x => x.key === p.key)) {
                        cards.push({
                            key: p.key,
                            label: p.label,
                            config: p.config || {},
                            builtin: false,
                        });
                    }
                }
            }
        } catch (_) {}
        return cards;
    }

    isProfileSelected(key) {
        const dl = this.props.designLab;
        if (key === "default") {
            return (
                dl.theme === DEFAULT_LAB_STATE.theme &&
                dl.palette === DEFAULT_LAB_STATE.palette &&
                dl.typography === DEFAULT_LAB_STATE.typography &&
                dl.spacing === DEFAULT_LAB_STATE.spacing &&
                dl.radius === DEFAULT_LAB_STATE.radius &&
                dl.shadow === DEFAULT_LAB_STATE.shadow &&
                dl.border === DEFAULT_LAB_STATE.border &&
                dl.gradient === DEFAULT_LAB_STATE.gradient &&
                dl.motion === DEFAULT_LAB_STATE.motion &&
                dl.hoverEffects === DEFAULT_LAB_STATE.hoverEffects
            );
        }
        const profile = BUILTIN_PROFILES[key];
        const cfg = profile ? profile.config : this.profileCards.find(p => p.key === key)?.config;
        if (!cfg) return false;
        return (
            dl.theme === cfg.theme &&
            dl.palette === cfg.palette &&
            dl.typography === cfg.typography &&
            dl.spacing === cfg.spacing &&
            dl.radius === cfg.radius &&
            dl.shadow === cfg.shadow &&
            dl.border === cfg.border &&
            dl.gradient === cfg.gradient &&
            dl.motion === cfg.motion &&
            dl.hoverEffects === cfg.hoverEffects
        );
    }

    toggleSection(name) {
        if (this.state.expandedSection === name) {
            this.state.expandedSection = null;
            sessionStorage.removeItem(SESSION_KEY);
        } else {
            this.state.expandedSection = name;
            sessionStorage.setItem(SESSION_KEY, name);
        }
    }

    isExpanded(name) {
        return this.state.expandedSection === name;
    }

    update(field, value) {
        this.props.onUpdate({ ...this.props.designLab, [field]: value });
    }

    updateAccessibility(field, value) {
        this.props.onUpdate({
            ...this.props.designLab,
            accessibility: { ...this.props.designLab.accessibility, [field]: value },
        });
    }

    selectProfile(key) {
        if (this.props.onLoadProfile) {
            this.props.onLoadProfile(key);
        }
    }

    saveCurrentProfile() {
        const name = prompt("Profile name:");
        if (name && this.props.onSaveProfile) {
            this.props.onSaveProfile(name);
        }
    }

    get currentPaletteLabel() {
        const p = PALETTES[this.props.designLab.palette];
        return p ? p.label : "Odoo Default";
    }

    get currentTypographyLabel() {
        const t = TYPOGRAPHY[this.props.designLab.typography];
        return t ? t.label : "Default";
    }
}
