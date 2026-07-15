/** @odoo-module **/
import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { CoreUIPreviewCard } from "../core_ui/preview_card";

export class CoreUIGallery extends Component {
    static template = "core_ui.gallery";
    static components = { CoreUIPreviewCard };
    static props = {
        components: { type: Array, optional: true },
        selectedComponent: { type: [Object, { value: null }], optional: true },
        onSelect: { type: Function },
        filterQuery: { type: String, optional: true },
        categoryId: { type: [String, { value: null }], optional: true },
        onAddToNotebook: { type: Function, optional: true },
        onNotebookCopy: { type: Function, optional: true },
        previewMode: { type: String, optional: true },
    };

    static defaultProps = {
        components: [],
        filterQuery: "",
    };

    setup() {
        this.notification = useService("notification");
    }

    get filteredComponents() {
        let items = this.props.components;
        const query = (this.props.filterQuery || "").toLowerCase();

        if (query) {
            items = items.filter(c =>
                (c.name || "").toLowerCase().includes(query) ||
                (c.component_id || "").toLowerCase().includes(query) ||
                (c.description || "").toLowerCase().includes(query) ||
                (c.keywords || "").toLowerCase().includes(query)
            );
        }

        if (this.props.categoryId) {
            const catName = this.props.categoryId;
            items = items.filter(c => c.category === catName);
        }

        return items;
    }

    selectComponent(comp) {
        this.props.onSelect(comp);
    }

    addToNotebook(comp) {
        if (this.props.onAddToNotebook) {
            this.props.onAddToNotebook(comp.component_id);
        }
    }

    copyComponentId(comp, ev) {
        if (ev) ev.stopPropagation();
        navigator.clipboard.writeText(comp.component_id).then(() => {
            this.notification.add("Copied: " + comp.component_id, { type: "info" });
        }).catch(() => {
            this.notification.add("Failed to copy", { type: "danger" });
        });
        if (this.props.onNotebookCopy) {
            this.props.onNotebookCopy(comp.component_id, "component_id");
        }
    }

    copyXml(comp, ev) {
        if (ev) ev.stopPropagation();
        const ref = comp.template_ref || comp.component_id;
        const xml = `<t t-call="${ref}"/>`;
        navigator.clipboard.writeText(xml).then(() => {
            this.notification.add("XML copied to clipboard", { type: "success" });
        }).catch(() => {
            this.notification.add("Failed to copy", { type: "danger" });
        });
        if (this.props.onNotebookCopy) {
            this.props.onNotebookCopy(comp.component_id, "xml");
        }
    }
}
