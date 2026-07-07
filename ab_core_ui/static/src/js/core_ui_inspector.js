/** @odoo-module **/
import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { CoreUIPreviewCard } from "../core_ui/preview_card";
import { generateAiPrompt } from "../core_ui/design_lab/design_lab_config";

export class CoreUIInspector extends Component {
    static template = "core_ui.inspector";
    static components = { CoreUIPreviewCard };
    static props = {
        component: { type: [Object, { value: null }], optional: true },
        componentMeta: { type: [Object, { value: null }], optional: true },
        onAddToNotebook: { type: Function, optional: true },
        onClose: { type: Function, optional: true },
        onCopyAiPrompt: { type: Function, optional: true },
        onNotebookCopy: { type: Function, optional: true },
        designLab: { type: Object, optional: true },
    };

    setup() {
        this.notification = useService("notification");
    }

    addToNotebook() {
        if (this.props.onAddToNotebook && this.props.component) {
            this.props.onAddToNotebook(this.props.component.component_id);
        }
    }

    copyXmlTemplate() {
        const comp = this.props.component;
        if (!comp) return;
        const ref = comp.template_ref || comp.component_id;
        const xml = `<t t-call="${ref}"/>`;
        this.copyText(xml, "XML copied to clipboard");
        if (this.props.onNotebookCopy) {
            this.props.onNotebookCopy(comp.component_id, "xml");
        }
    }

    copyComponentId() {
        const comp = this.props.component;
        if (!comp) return;
        this.copyText(comp.component_id, "Component ID copied");
        if (this.props.onNotebookCopy) {
            this.props.onNotebookCopy(comp.component_id, "component_id");
        }
    }

    get aiPrompt() {
        const comp = this.props.component;
        if (!comp) return "";
        return generateAiPrompt(comp.component_id, this.props.designLab || {});
    }

    get aiPromptLines() {
        return this.aiPrompt.split("\n");
    }

    copyAiPrompt() {
        if (!this.props.component) return;
        this.copyText(this.aiPrompt, "AI Prompt copied");
        if (this.props.onCopyAiPrompt) {
            this.props.onCopyAiPrompt(this.props.component.component_id);
        }
        if (this.props.onNotebookCopy) {
            this.props.onNotebookCopy(this.props.component.component_id, "ai_prompt");
        }
    }

    copyText(text, label) {
        navigator.clipboard.writeText(text).then(() => {
            this.notification.add(label || "Copied to clipboard", { type: "success" });
        }).catch(() => {
            this.notification.add("Failed to copy", { type: "danger" });
        });
    }

    get safeComponent() {
        return this.props.component || {};
    }
}
