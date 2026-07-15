/** @odoo-module **/
import { Component, useState } from "@odoo/owl";
import { CoreUIDesignLab } from "../core_ui/design_lab/design_lab";

export class CoreUISidebar extends Component {
    static template = "core_ui.sidebar";
    static components = { CoreUIDesignLab };
    static props = {
        categories: { type: Array, optional: true },
        selectedCategory: { type: [Number, String, { value: null }], optional: true },
        onSelectCategory: { type: Function },
        favorites: { type: Array, optional: true },
        recentComponents: { type: Array, optional: true },
        usedComponents: { type: Array, optional: true },
        onSelectComponent: { type: Function, optional: true },
        designLab: { type: Object, optional: true },
        onUpdateDesignLab: { type: Function, optional: true },
        onLoadProfile: { type: Function, optional: true },
        onSaveProfile: { type: Function, optional: true },
    };

    static defaultProps = {
        categories: [],
        favorites: [],
        recentComponents: [],
        usedComponents: [],
    };

    setup() {
        this.state = useState({
            collapsedSections: [],
        });
    }

    toggleSection(name) {
        const idx = this.state.collapsedSections.indexOf(name);
        if (idx >= 0) {
            this.state.collapsedSections.splice(idx, 1);
        } else {
            this.state.collapsedSections.push(name);
        }
    }

    isCollapsed(name) {
        return this.state.collapsedSections.includes(name);
    }

    selectCategory(catId) {
        this.props.onSelectCategory(catId);
    }

    selectComponent(compId) {
        if (this.props.onSelectComponent) {
            this.props.onSelectComponent(compId);
        }
    }
}
