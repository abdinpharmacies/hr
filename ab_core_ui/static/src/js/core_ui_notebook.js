/** @odoo-module **/
import { Component, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

const COPY_TYPE_LABELS = {
    xml: "XML",
    component_id: "Component ID",
    ai_prompt: "AI Prompt",
    owl_usage: "OWL Usage",
    props: "Props",
    import: "Import",
};

const COPY_TYPE_ICONS = {
    xml: "fa-code",
    component_id: "fa-copy",
    ai_prompt: "fa-robot",
    owl_usage: "fa-file-code",
    props: "fa-tags",
    import: "fa-download",
};

export class CoreUINotebook extends Component {
    static template = "core_ui.notebook";
    static props = {
        items: { type: Array, optional: true },
        onRemove: { type: Function, optional: true },
        onClear: { type: Function, optional: true },
        onPin: { type: Function, optional: true },
        onJumpTo: { type: Function, optional: true },
    };

    static defaultProps = {
        items: [],
    };

    setup() {
        this.notification = useService("notification");
        this.state = useState({
            mode: 'collapsed',
        });
    }

    get itemCount() {
        return this.props.items.length;
    }

    get isEmpty() {
        return this.props.items.length === 0;
    }

    get flattenedForExport() {
        const lines = [];
        for (const card of this.props.items) {
            lines.push(`${card.name} (${card.componentId})`);
            for (const t of card.copiedTypes) {
                lines.push(`  [${COPY_TYPE_LABELS[t] || t}]`);
            }
            lines.push("");
        }
        return lines.join("\n");
    }

    get aiPromptsForExport() {
        return this.props.items
            .filter(c => c.copiedTypes.includes("ai_prompt"))
            .map(c => `- ${c.componentId} (${c.name})`)
            .join("\n");
    }

    get xmlForExport() {
        return this.props.items
            .filter(c => c.copiedTypes.includes("xml"))
            .map(c => `<t t-call="${c.templateRef || c.componentId}"/>`)
            .join("\n\n");
    }

    get markdownForExport() {
        const lines = ["# Core UI Notebook Export", ""];
        for (const card of this.props.items) {
            const types = card.copiedTypes.map(t => COPY_TYPE_LABELS[t] || t).join(", ");
            lines.push(`## ${card.name}`);
            lines.push(`- **ID:** \`${card.componentId}\``);
            lines.push(`- **Copied:** ${types}`);
            if (card.templateRef) {
                lines.push(`- **XML:** \`<t t-call="${card.templateRef}"/>\``);
            }
            lines.push("");
        }
        return lines.join("\n");
    }

    toggleMode() {
        this.state.mode = this.state.mode === 'collapsed' ? 'expanded' : 'collapsed';
    }

    removeItem(componentId) {
        if (this.props.onRemove) {
            this.props.onRemove(componentId);
        }
    }

    clearAll() {
        if (this.props.onClear) {
            this.props.onClear();
        }
    }

    togglePin(componentId) {
        if (this.props.onPin) {
            this.props.onPin(componentId);
        }
    }

    jumpTo(componentId) {
        if (this.props.onJumpTo) {
            this.props.onJumpTo(componentId);
        }
    }

    getCardTypes(item) {
        return item.copiedTypes.map(t => ({
            key: t,
            label: COPY_TYPE_LABELS[t] || t,
            icon: COPY_TYPE_ICONS[t] || "fa-copy",
        }));
    }

    formatTime(ts) {
        if (!ts) return "";
        const d = new Date(ts);
        const now = new Date();
        const diff = now - d;
        if (diff < 60000) return "Just now";
        if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
        if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
        return d.toLocaleDateString();
    }

    async copyCardAgain(item) {
        const parts = [];
        for (const t of item.copiedTypes) {
            if (t === "xml") {
                parts.push(`<t t-call="${item.templateRef || item.componentId}"/>`);
            } else if (t === "component_id") {
                parts.push(item.componentId);
            }
        }
        const text = parts.join("\n\n");
        try {
            await navigator.clipboard.writeText(text);
            this.notification.add(`Re-copied ${item.name}`, { type: "success" });
        } catch {
            this.notification.add("Failed to copy", { type: "danger" });
        }
    }

    async copyEverything() {
        try {
            await navigator.clipboard.writeText(this.flattenedForExport);
            this.notification.add("All notebook items copied", { type: "success" });
        } catch {
            this.notification.add("Failed to copy", { type: "danger" });
        }
    }

    async exportAiPrompts() {
        try {
            await navigator.clipboard.writeText(this.aiPromptsForExport);
            this.notification.add("AI Prompts copied", { type: "success" });
        } catch {
            this.notification.add("Failed to copy", { type: "danger" });
        }
    }

    async exportXml() {
        try {
            await navigator.clipboard.writeText(this.xmlForExport);
            this.notification.add("XML snippets copied", { type: "success" });
        } catch {
            this.notification.add("Failed to copy", { type: "danger" });
        }
    }

    async exportMarkdown() {
        try {
            await navigator.clipboard.writeText(this.markdownForExport);
            this.notification.add("Markdown export copied", { type: "success" });
        } catch {
            this.notification.add("Failed to copy", { type: "danger" });
        }
    }
}
