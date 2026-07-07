/** @odoo-module **/
import { Component } from "@odoo/owl";
import { THEME_PACKS, TYPOGRAPHY, RADIUS, SHADOWS, getProfileVars } from "./design_lab_config";

export class ProfilePreviewCard extends Component {
    static template = "core_ui.profile_preview_card";
    static props = {
        profile: { type: Object },
        isSelected: { type: Boolean, optional: true },
        onSelect: { type: Function },
    };

    get profileVars() {
        return getProfileVars(this.props.profile.config);
    }

    get profileStyle() {
        const vars = this.profileVars;
        const parts = [];
        for (const [k, v] of Object.entries(vars)) {
            parts.push(k + ": " + v);
        }
        return parts.join("; ");
    }

    get themeLabel() {
        const t = THEME_PACKS[this.props.profile.config.theme];
        return t ? t.label : this.props.profile.config.theme;
    }

    get typographyLabel() {
        const t = TYPOGRAPHY[this.props.profile.config.typography];
        return t ? t.label : this.props.profile.config.typography;
    }

    get radiusLabel() {
        const r = RADIUS[this.props.profile.config.radius];
        return r ? r.label : this.props.profile.config.radius;
    }

    get shadowLabel() {
        const s = SHADOWS[this.props.profile.config.shadow];
        return s ? s.label : this.props.profile.config.shadow;
    }

    select() {
        this.props.onSelect(this.props.profile.key);
    }
}
