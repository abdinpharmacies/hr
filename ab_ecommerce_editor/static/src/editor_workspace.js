/** @odoo-module **/

import { Component, onMounted, onPatched, onWillStart, onWillUnmount, useRef, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";
import { useSetupAction } from "@web/search/action_hook";

const clone = (value) => JSON.parse(JSON.stringify(value));
const LAYOUT_FIELDS = ["tools_open", "layers_open", "inspector_open", "canvas_toolbar_open", "dark_mode", "tools_width", "layers_height", "inspector_width"];

const DOCUMENT_FIELDS = [
    "name", "kind", "website_id", "slug", "category", "image_url", "title_en", "title_ar",
    "summary_en", "summary_ar", "blocks_en", "blocks_ar", "design_tokens", "web_overrides",
    "flutter_overrides", "seo_title_en", "seo_title_ar", "seo_description_en", "seo_description_ar",
    "state", "scheduled_at", "published_at", "published_revision_id", "version", "active", "write_date", "draft_token",
];
const EDITABLE_FIELDS = DOCUMENT_FIELDS.filter((field) => ![
    "state", "scheduled_at", "published_at", "published_revision_id", "version", "active", "write_date", "draft_token",
].includes(field));
const BLOCKS = [
    { type: "hero", label: _t("Hero"), icon: "fa fa-window-maximize" },
    { type: "heading", label: _t("Heading"), icon: "fa fa-header" },
    { type: "text", label: _t("Text"), icon: "fa fa-align-left" },
    { type: "image", label: _t("Image"), icon: "fa fa-image" },
    { type: "button", label: _t("Button"), icon: "fa fa-hand-pointer-o" },
    { type: "divider", label: _t("Divider"), icon: "fa fa-minus" },
];
const FONTS = ["system", "arabic", "georgia", "monospace"];
const DEFAULT_BLOCK = {
    hero: { title: _t("A fresh story starts here"), body: _t("Share a clear message with your customers."), label: _t("Explore"), url: "/shop" },
    heading: { title: _t("Your heading") },
    text: { body: _t("Write your story here.") },
    image: { url: "", alt: "" },
    button: { label: _t("Explore"), url: "/shop" },
    divider: {},
};

export class EditorWorkspace extends Component {
    static template = "ab_ecommerce_editor.Workspace";
    static props = { ...standardActionServiceProps };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.root = useRef("root");
        this.motionAnimations = new Set();
        this.motionPositions = null;
        this.pressTimer = null;
        this.pressStart = null;
        this.ignorePreviewClickId = null;
        this.removingIds = new Set();
        this.savedDraftSnapshot = null;
        this.destroyed = false;
        this.layoutId = null;
        this.layoutTimer = null;
        this.layoutSaving = Promise.resolve();
        this.resizeSession = null;
        this.state = useState({
            ready: false, workspaceOpen: false, view: "library", filter: "all", documents: [], templates: [], websites: [], templateId: null, websiteId: null,
            currentId: null, draft: null, selectedId: null, armedDeleteId: null, actionMenuId: null, deletedBlocks: [], trashOpen: false, inspector: "content", language: "en_US",
            device: "desktop", toolsOpen: true, layersOpen: true, inspectorOpen: true, canvasToolbarOpen: true, darkMode: false, toolsWidth: 224, layersHeight: 180, inspectorWidth: 290, history: [], future: [], dirty: false, busy: false, canReview: false,
            canPublish: false, scheduleAt: "", dragId: null, trashDragId: null, trashDropActive: false, dropId: null, dropAfter: false, navigating: false, versions: [],
        });
        useSetupAction({
            beforeLeave: () => !this.state.dirty || window.confirm(_t("Discard unsaved changes?")),
            beforeUnload: this.beforeUnload,
        });
        onWillStart(async () => {
            const [review, publish] = await Promise.all([
                user.hasGroup("ab_ecommerce_editor.group_editor_reviewer"),
                user.hasGroup("ab_ecommerce_editor.group_editor_publisher"),
            ]);
            this.state.canReview = review;
            this.state.canPublish = publish;
            await Promise.all([this.loadLibrary(), this.loadLayout()]);
            this.state.ready = true;
        });
        onMounted(() => {
            window.addEventListener("keydown", this.onKeydown);
            window.addEventListener("pointermove", this.onResizeMove);
            window.addEventListener("pointerup", this.endResize);
            window.addEventListener("pointercancel", this.endResize);
        });
        onWillUnmount(() => {
            if (this.layoutTimer) this.saveLayout(true);
            this.destroyed = true;
            this.cancelPreviewPress();
            for (const animation of this.motionAnimations) animation.cancel();
            document.body.classList.remove("ab_editor_active");
            window.removeEventListener("keydown", this.onKeydown);
            window.removeEventListener("pointermove", this.onResizeMove);
            window.removeEventListener("pointerup", this.endResize);
            window.removeEventListener("pointercancel", this.endResize);
        });
        onPatched(() => this.animatePositions());
    }

    get reducedMotion() { return window.matchMedia("(prefers-reduced-motion: reduce)").matches; }
    get workspaceToggleLabel() { return this.state.workspaceOpen ? _t("Close workspace") : _t("Open workspace"); }
    get toolsToggleLabel() { return this.state.toolsOpen ? _t("Hide tools panel") : _t("Show tools panel"); }
    get layersToggleLabel() { return this.state.layersOpen ? _t("Hide deleted blocks panel") : _t("Show deleted blocks panel"); }
    get inspectorToggleLabel() { return this.state.inspectorOpen ? _t("Hide inspector panel") : _t("Show inspector panel"); }
    get themeToggleLabel() { return this.state.darkMode ? _t("Switch to light theme") : _t("Switch to dark theme"); }
    get canvasToolbarToggleLabel() { return this.state.canvasToolbarOpen ? _t("Hide preview controls") : _t("Show preview controls"); }
    get layoutStyle() {
        return `--ae-tools-width:${this.state.toolsWidth}px;--ae-inspector-width:${this.state.inspectorWidth}px;--ae-layers-height:${this.state.layersHeight}px`;
    }

    async loadLayout() {
        const layouts = await this.orm.searchRead("ab_ecommerce_editor_layout", [["user_id", "=", user.userId]], LAYOUT_FIELDS, { limit: 1 });
        if (!layouts.length) return;
        const layout = layouts[0];
        this.layoutId = layout.id;
        this.state.toolsOpen = layout.tools_open;
        this.state.layersOpen = layout.layers_open;
        this.state.inspectorOpen = layout.inspector_open;
        this.state.canvasToolbarOpen = layout.canvas_toolbar_open;
        this.state.darkMode = layout.dark_mode;
        this.state.toolsWidth = layout.tools_width;
        this.state.layersHeight = layout.layers_height;
        this.state.inspectorWidth = layout.inspector_width;
    }

    saveLayout(immediate = false) {
        clearTimeout(this.layoutTimer);
        const persist = () => {
            this.layoutTimer = null;
            const values = {
                tools_open: this.state.toolsOpen,
                layers_open: this.state.layersOpen,
                inspector_open: this.state.inspectorOpen,
                canvas_toolbar_open: this.state.canvasToolbarOpen,
                dark_mode: this.state.darkMode,
                tools_width: this.state.toolsWidth,
                layers_height: this.state.layersHeight,
                inspector_width: this.state.inspectorWidth,
            };
            this.layoutSaving = this.layoutSaving.then(async () => {
                if (this.layoutId) await this.orm.write("ab_ecommerce_editor_layout", [this.layoutId], values);
                else [this.layoutId] = await this.orm.create("ab_ecommerce_editor_layout", [values]);
            }).catch(() => this.notification.add(_t("Could not save the editor layout."), { type: "warning" }));
        };
        if (immediate) persist();
        else this.layoutTimer = setTimeout(persist, 300);
    }

    togglePanel(panel) {
        const field = { tools: "toolsOpen", layers: "layersOpen", inspector: "inspectorOpen" }[panel];
        this.state[field] = !this.state[field];
        this.saveLayout(true);
    }

    toggleTheme() {
        this.state.darkMode = !this.state.darkMode;
        this.saveLayout(true);
    }

    toggleCanvasToolbar() {
        this.state.canvasToolbarOpen = !this.state.canvasToolbarOpen;
        this.saveLayout(true);
        requestAnimationFrame(() => this.root.el?.querySelector(this.state.canvasToolbarOpen ? ".ab_editor__canvas-toolbar-toggle" : ".ab_editor__canvas-toolbar-reveal")?.focus());
    }

    startResize(panel, event) {
        if (event.button !== 0) return;
        const workspace = this.root.el?.querySelector(".ab_editor__workspace");
        if (!workspace) return;
        event.preventDefault();
        event.currentTarget.setPointerCapture(event.pointerId);
        const panelElement = workspace.querySelector({ tools: ".ab_editor__rail", layers: ".ab_editor__layers-panel", inspector: ".ab_editor__inspector" }[panel]);
        const otherElement = workspace.querySelector(panel === "tools" ? ".ab_editor__inspector" : ".ab_editor__rail");
        this.resizeSession = {
            panel, pointerId: event.pointerId, x: event.clientX, y: event.clientY,
            value: panel === "layers" ? panelElement.clientHeight : panelElement.clientWidth,
            width: workspace.clientWidth, height: workspace.clientHeight,
            rtl: this.interfaceDirection === "rtl",
            other: otherElement?.hidden ? 0 : otherElement?.clientWidth || 0,
        };
        this.root.el.classList.add("is-resizing");
    }

    onResizeMove = (event) => {
        const resize = this.resizeSession;
        if (!resize || event.pointerId !== resize.pointerId) return;
        const clamp = (value, min, max) => Math.round(Math.max(min, Math.min(max, value)));
        if (resize.panel === "layers") {
            this.state.layersHeight = clamp(resize.value + resize.y - event.clientY, 100, Math.min(500, resize.height - 240));
            return;
        }
        const direction = resize.rtl ? -1 : 1;
        const delta = (event.clientX - resize.x) * direction * (resize.panel === "tools" ? 1 : -1);
        const minimum = resize.panel === "tools" ? 150 : 180;
        const maximum = resize.panel === "tools" ? 500 : 520;
        this.state[resize.panel === "tools" ? "toolsWidth" : "inspectorWidth"] = clamp(resize.value + delta, minimum, Math.min(maximum, resize.width - resize.other - 280));
    };

    endResize = (event) => {
        if (!this.resizeSession || event.pointerId !== this.resizeSession.pointerId) return;
        this.resizeSession = null;
        this.root.el?.classList.remove("is-resizing");
        this.saveLayout(true);
    };

    onResizeKeydown(panel, event) {
        const increment = event.shiftKey ? 20 : 10;
        let delta = 0;
        if (panel === "layers") delta = event.key === "ArrowUp" ? increment : event.key === "ArrowDown" ? -increment : 0;
        else if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
            const direction = this.interfaceDirection === "rtl" ? -1 : 1;
            delta = (event.key === "ArrowRight" ? 1 : -1) * direction * (panel === "tools" ? 1 : -1) * increment;
        }
        if (!delta) return;
        event.preventDefault();
        const field = { tools: "toolsWidth", layers: "layersHeight", inspector: "inspectorWidth" }[panel];
        const minimum = panel === "tools" ? 150 : panel === "inspector" ? 180 : 100;
        const maximum = panel === "tools" ? 500 : panel === "inspector" ? 520 : 500;
        this.state[field] = Math.max(minimum, Math.min(maximum, this.state[field] + delta));
        this.saveLayout();
    }

    toggleWorkspace() {
        return this.state.workspaceOpen ? this.closeWorkspace() : this.openWorkspace();
    }

    openWorkspace() {
        if (this.state.workspaceOpen || this.state.navigating) return;
        this.state.workspaceOpen = true;
        document.body.classList.add("ab_editor_active");
        requestAnimationFrame(() => this.root.el?.querySelector(".ab_editor__brand")?.focus());
    }

    async closeWorkspace() {
        if (!this.state.workspaceOpen || this.state.navigating) return;
        this.state.navigating = true;
        const animation = this.animateElement(this.root.el, [
            { opacity: 1, transform: "none" },
            { opacity: 0, transform: "scale(.985) translateY(10px)" },
        ], 180);
        if (animation) await animation.finished.catch(() => {});
        if (this.destroyed) return;
        this.state.workspaceOpen = false;
        document.body.classList.remove("ab_editor_active");
        this.state.navigating = false;
        requestAnimationFrame(() => this.root.el?.querySelector(".ab_editor__brand")?.focus());
    }

    animateElement(element, frames, duration = 320, fill = "none") {
        if (!element || this.reducedMotion || this.destroyed) return null;
        const animation = element.animate(frames, { duration, easing: "cubic-bezier(.22, 1, .36, 1)", fill });
        this.motionAnimations.add(animation);
        animation.finished.then(() => this.motionAnimations.delete(animation), () => this.motionAnimations.delete(animation));
        return animation;
    }

    capturePositions() {
        if (this.reducedMotion) return;
        this.motionPositions = new Map(Array.from(this.root.el?.querySelectorAll("[data-motion-id]") || [], (element) => [element.dataset.motionId, element.getBoundingClientRect()]));
        for (const animation of this.motionAnimations) {
            if (animation.effect?.target?.dataset.motionId) animation.cancel();
        }
    }

    animatePositions() {
        const positions = this.motionPositions;
        this.motionPositions = null;
        if (!positions || this.reducedMotion) return;
        const elements = Array.from(this.root.el.querySelectorAll("[data-motion-id]"));
        const movements = elements.map((element) => ({ element, previous: positions.get(element.dataset.motionId), next: element.getBoundingClientRect() }));
        for (const { element, previous, next } of movements) {
            if (!previous) {
                this.animateElement(element, [{ opacity: 0, transform: "translateY(12px) scale(.98)" }, { opacity: 1, transform: "none" }]);
            } else if (Math.abs(previous.top - next.top) > 1 || Math.abs(previous.left - next.left) > 1) {
                const x = previous.left - next.left;
                const y = previous.top - next.top;
                const hop = y > 0 ? 16 : -16;
                this.animateElement(element, [
                    { transform: `translate(${x}px, ${y}px) scale(1)`, offset: 0 },
                    { transform: `translate(${x / 2 + hop}px, ${y / 2 - 10}px) scale(1.025)`, offset: .45 },
                    { transform: "translate(0, 0) scale(1)", offset: 1 },
                ], 520);
            }
        }
    }

    async navigate(prepare) {
        if (this.state.navigating) return;
        this.state.navigating = true;
        let animation;
        try {
            const commit = await prepare();
            if (!commit || this.destroyed) return;
            const element = this.root.el.querySelector(".ab_editor__workspace, .ab_editor__library");
            animation = this.animateElement(element, [{ opacity: 1, transform: "none" }, { opacity: 0, transform: "translateY(10px) scale(.985)" }], 160, "forwards");
            if (animation) await animation.finished.catch(() => {});
            if (!this.destroyed) {
                commit();
                if (animation) await new Promise(requestAnimationFrame);
            }
        } finally {
            animation?.cancel();
            if (!this.destroyed) this.state.navigating = false;
        }
    }

    async loadLibrary() {
        const [documents, templates, websites] = await Promise.all([
            this.orm.searchRead("ab_ecommerce_editor_document", [], ["name", "kind", "website_id", "slug", "title_en", "title_ar", "state", "version"], { order: "write_date desc" }),
            this.orm.searchRead("ab_ecommerce_editor_template", [["active", "=", true]], ["name", "website_id", "scope", "blocks", "design_tokens"]),
            this.orm.searchRead("website", [], ["name", "company_id"]),
        ]);
        this.state.documents = documents;
        this.state.templates = templates;
        this.state.websites = websites.filter((website) => user.context.allowed_company_ids.includes(website.company_id[0]));
        if (!this.state.websites.some((website) => website.id === this.state.websiteId)) {
            this.state.websiteId = (this.state.websites.find((website) => website.company_id[0] === user.context.allowed_company_ids[0]) || this.state.websites[0])?.id || null;
        }
    }

    get filteredDocuments() {
        return this.state.documents.filter((document) => document.website_id[0] === this.state.websiteId && (this.state.filter === "all" || document.kind === this.state.filter));
    }

    get filteredTemplates() { return this.state.templates.filter((template) => template.website_id[0] === this.state.websiteId); }

    get blocks() {
        if (!this.state.draft) return [];
        if (this.state.language === "ar_001") return this.state.draft.blocks_ar?.length ? this.state.draft.blocks_ar : this.state.draft.blocks_en || [];
        return this.state.draft.blocks_en || [];
    }

    get previewBlocks() {
        const templates = new Map(this.state.templates.map((template) => [template.id, template]));
        return this.blocks.flatMap((block) => {
            if (block.type !== "template") return [{ ...block, sourceId: block.id }];
            const template = templates.get(block.template_id);
            return (template?.blocks || []).map((item) => ({ ...item, style: { ...template.design_tokens, ...item.style }, id: `${block.id}_${item.id}`, sourceId: block.id }));
        });
    }

    get selectedBlock() {
        return this.blocks.find((block) => block.id === this.state.selectedId);
    }

    get sessionTrash() {
        const scope = this.state.templateId ? `template:${this.state.templateId}` : `document:${this.state.currentId}`;
        const activeIds = new Set(this.blocks.map((block) => block.id));
        return this.state.deletedBlocks.filter((entry) => entry.scope === scope && entry.language === this.state.language && !activeIds.has(entry.block.id));
    }

    get trashScope() {
        return this.state.templateId ? `template:${this.state.templateId}` : `document:${this.state.currentId}`;
    }

    trashTitle(entry) {
        return entry.block.title || entry.block.label || entry.block.body || this.blockLabel(entry.block.type);
    }

    get blockPalette() { return BLOCKS; }
    get fonts() { return FONTS; }
    fontLabel(font) { return { system: _t("System font"), arabic: _t("Arabic font"), georgia: _t("Georgia"), monospace: _t("Monospace") }[font]; }

    blockLabel(type) {
        return BLOCKS.find((block) => block.type === type)?.label || _t("Reusable block");
    }

    stateLabel(state) {
        return { draft: _t("Draft"), review: _t("In review"), scheduled: _t("Scheduled"), published: _t("Published") }[state];
    }

    kindLabel(kind) { return kind === "blog" ? _t("Article") : _t("Page"); }
    get interfaceDirection() { return (user.context.lang || "").startsWith("ar") ? "rtl" : "ltr"; }
    documentTitle(document) { return this.interfaceDirection === "rtl" ? document.title_ar || document.title_en : document.title_en; }
    get inspectorTitle() { return this.selectedBlock ? this.blockLabel(this.selectedBlock.type) : _t("Page settings"); }
    get designHint() { return this.selectedBlock ? _t("Style the selected block.") : _t("Set the design tokens for this page."); }

    get isLocked() {
        return this.state.busy || this.state.navigating || ["review", "scheduled"].includes(this.state.draft?.state);
    }

    editableSnapshot(draft) {
        if (!draft) return null;
        const fields = this.state.templateId ? ["name", "blocks_en", "design_tokens"] : EDITABLE_FIELDS;
        return JSON.stringify(Object.fromEntries(fields.map((field) => [field, draft[field]])));
    }

    refreshDirty() {
        this.state.dirty = this.editableSnapshot(this.state.draft) !== this.savedDraftSnapshot;
    }

    get liveUrl() {
        const draft = this.state.draft;
        return draft?.published_revision_id?.[0] ? `/editor/${draft.kind}/${draft.slug}` : "";
    }

    get previewTitle() {
        const draft = this.state.draft;
        return this.state.language === "ar_001" ? draft.title_ar || draft.title_en : draft.title_en;
    }

    get previewSummary() {
        const draft = this.state.draft;
        return this.state.language === "ar_001" ? draft.summary_ar || draft.summary_en : draft.summary_en;
    }

    get tokenStyle() {
        return this.styleFor({ ...this.state.draft?.design_tokens, ...this.state.draft?.web_overrides });
    }

    styleFor(style = {}) {
        const rules = [];
        if (style.weight) rules.push(`font-weight:${style.weight};--ae-font-weight:${style.weight}`);
        if (style.italic) rules.push("font-style:italic");
        if (style.border_color) rules.push(`border-color:${style.border_color};border-style:solid`);
        if (Number.isInteger(style.border_width)) rules.push(`border-width:${style.border_width}px;border-style:solid`);
        if (Number.isInteger(style.mobile_size)) rules.push(`--ae-mobile-size:${style.mobile_size}px`);
        if (style.color) rules.push(`color:${style.color}`);
        if (style.background) rules.push(`background-color:${style.background}`);
        if (style.font) {
            const family = { system: "system-ui,sans-serif", arabic: "Abdin Editor Arabic,sans-serif", monospace: "monospace", georgia: "Georgia,serif" }[style.font];
            if (family) rules.push(`font-family:${family}`);
        }
        for (const [field, css] of [["size", "font-size"], ["padding", "padding"], ["radius", "border-radius"]]) {
            if (Number.isInteger(style[field])) rules.push(`${css}:${style[field]}px`);
        }
        if (["start", "center", "end"].includes(style.align)) rules.push(`text-align:${style.align}`);
        return rules.join(";");
    }

    async openDocument(id) {
        if (this.state.dirty && !window.confirm(_t("Discard unsaved changes?"))) return;
        await this.navigate(async () => {
            const records = await this.orm.searchRead("ab_ecommerce_editor_document", [["id", "=", id]], DOCUMENT_FIELDS);
            if (!records.length) return;
            const versions = await this.orm.searchRead("ab_ecommerce_editor_revision", [["document_id", "=", id]], ["number", "author_id", "create_date"], { order: "number desc", limit: 30 });
            return () => {
                this.state.currentId = id;
                this.state.templateId = null;
                this.state.draft = clone(records[0]);
                this.savedDraftSnapshot = this.editableSnapshot(this.state.draft);
                this.state.selectedId = null;
                this.state.armedDeleteId = null;
                this.state.actionMenuId = null;
                this.state.history = [];
                this.state.future = [];
                this.state.dirty = false;
                this.state.view = "editor";
                this.state.versions = versions;
            };
        });
    }

    async loadVersions() {
        this.state.versions = await this.orm.searchRead("ab_ecommerce_editor_revision", [["document_id", "=", this.state.currentId]], ["number", "author_id", "create_date"], { order: "number desc", limit: 30 });
    }

    async createDocument(kind) {
        if (this.state.dirty && !window.confirm(_t("Discard unsaved changes?"))) return;
        this.state.dirty = false;
        const website = this.state.websites.find((item) => item.id === this.state.websiteId);
        if (!website) {
            this.notification.add(_t("Set up a website before creating content."), { type: "warning" });
            return;
        }
        const slug = `new-${kind}-${Date.now().toString(36)}`;
        const [id] = await this.orm.create("ab_ecommerce_editor_document", [{
            name: kind === "blog" ? _t("New article") : _t("New page"),
            kind, website_id: website.id, slug,
            title_en: kind === "blog" ? _t("New article") : _t("New page"),
            blocks_en: [{ id: "hero_1", type: "hero", ...DEFAULT_BLOCK.hero, style: { padding: 48, align: "center" } }],
        }]);
        await this.loadLibrary();
        await this.openDocument(id);
    }

    edit(mutator) {
        if (this.isLocked) return;
        this.capturePositions();
        const next = clone(this.state.draft);
        mutator(next);
        this.state.history = [...this.state.history.slice(-29), clone(this.state.draft)];
        this.state.future = [];
        this.state.draft = next;
        this.refreshDirty();
    }

    updateField(field, event) {
        this.edit((draft) => { draft[field] = event.target.value; });
    }

    updateStyle(field, event, scope = "block") {
        if (scope === "block" && this.selectedBlock?.type === "template") return;
        const value = ["size", "padding", "radius", "border_width", "mobile_size"].includes(field) ? Number(event.target.value) : field === "italic" ? event.target.checked : event.target.value;
        this.edit((draft) => {
            if (scope === "global") {
                draft.design_tokens = { ...draft.design_tokens, [field]: value };
                return;
            }
            const block = this.editableBlocks(draft).find((item) => item.id === this.state.selectedId);
            if (block) block.style = { ...block.style, [field]: value };
        });
    }

    editableBlocks(draft) {
        if (this.state.language === "ar_001") {
            if (!draft.blocks_ar?.length) draft.blocks_ar = clone(draft.blocks_en || []);
            return draft.blocks_ar;
        }
        if (!draft.blocks_en) draft.blocks_en = [];
        return draft.blocks_en;
    }

    updateBlock(field, event) {
        this.edit((draft) => {
            const block = this.editableBlocks(draft).find((item) => item.id === this.state.selectedId);
            if (block) block[field] = event.target.value;
        });
    }

    addBlock(type) {
        this.edit((draft) => {
            const block = { id: `b_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 6)}`, type, ...DEFAULT_BLOCK[type], style: {} };
            this.editableBlocks(draft).push(block);
            this.state.selectedId = block.id;
        });
    }

    moveBlock(id, delta) {
        this.edit((draft) => {
            const blocks = this.editableBlocks(draft);
            const index = blocks.findIndex((block) => block.id === id);
            const target = index + delta;
            if (index < 0 || target < 0 || target >= blocks.length) return;
            [blocks[index], blocks[target]] = [blocks[target], blocks[index]];
        });
    }

    async removeBlock(id) {
        if (this.isLocked || this.removingIds.has(id)) return;
        const index = this.blocks.findIndex((block) => block.id === id);
        if (index < 0) return;
        const entry = {
            id: `trash_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 6)}`,
            scope: this.trashScope,
            language: this.state.language,
            index,
            block: clone(this.blocks[index]),
        };
        this.removingIds.add(id);
        let hiddenElements = [];
        try {
            const elements = Array.from(this.root.el?.querySelectorAll(".ab_editor__preview-block, .ab_editor__layer") || [])
                .filter((element) => element.dataset.sourceId === id);
            const animations = elements.map((element) => this.animateElement(element, [
                { opacity: 1, transform: window.getComputedStyle(element).transform },
                { opacity: 0, transform: "scale(.82) translateY(-12px)" },
            ], 220)).filter(Boolean);
            await Promise.all(animations.map((animation) => animation.finished.catch(() => {})));
            if (this.destroyed || this.isLocked || entry.scope !== this.trashScope || entry.language !== this.state.language) return;
            hiddenElements = elements;
            for (const element of hiddenElements) element.style.opacity = "0";
            this.edit((draft) => {
                const blocks = this.editableBlocks(draft);
                draft[this.state.language === "ar_001" ? "blocks_ar" : "blocks_en"] = blocks.filter((block) => block.id !== id);
            });
            this.state.deletedBlocks = [entry, ...this.state.deletedBlocks.filter((item) => item.scope !== entry.scope || item.language !== entry.language || item.block.id !== id)];
            if (this.state.selectedId === id) this.state.selectedId = null;
            this.state.armedDeleteId = null;
            this.state.actionMenuId = null;
        } finally {
            if (hiddenElements.length) requestAnimationFrame(() => {
                for (const element of hiddenElements) element.style.opacity = "";
            });
            this.removingIds.delete(id);
        }
    }

    async restoreDeletedBlock(entryId, targetIndex = null) {
        if (this.isLocked) return;
        const entry = this.sessionTrash.find((item) => item.id === entryId);
        if (!entry) return;
        const card = Array.from(this.root.el?.querySelectorAll(".ab_editor__trash-item") || []).find((element) => element.dataset.trashId === entryId);
        const animation = this.animateElement(card, [
            { opacity: 1, transform: "translateY(0) scale(1)" },
            { opacity: 0, transform: "translateY(-8px) scale(.96)" },
        ], 160);
        if (animation) await animation.finished.catch(() => {});
        if (this.destroyed || this.isLocked || entry.scope !== this.trashScope || entry.language !== this.state.language) return;
        this.edit((draft) => {
            const blocks = this.editableBlocks(draft);
            const restored = clone(entry.block);
            if (blocks.some((block) => block.id === restored.id)) restored.id = `b_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 6)}`;
            blocks.splice(Math.min(targetIndex ?? entry.index, blocks.length), 0, restored);
            this.state.selectedId = restored.id;
        });
        this.state.armedDeleteId = null;
        this.state.actionMenuId = null;
    }

    duplicateBlock(id) {
        if (this.isLocked) return;
        this.edit((draft) => {
            const blocks = this.editableBlocks(draft);
            const index = blocks.findIndex((block) => block.id === id);
            if (index < 0) return;
            const copy = clone(blocks[index]);
            copy.id = `b_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 6)}`;
            blocks.splice(index + 1, 0, copy);
            this.state.selectedId = copy.id;
        });
        this.state.actionMenuId = null;
        this.state.armedDeleteId = null;
    }

    cancelPreviewPress() {
        clearTimeout(this.pressTimer);
        this.pressTimer = null;
        this.pressStart = null;
    }

    onPreviewPointerDown(id, previewId, event) {
        if (this.isLocked || this.removingIds.has(id) || event.button !== 0) return;
        this.cancelPreviewPress();
        this.pressStart = { x: event.clientX, y: event.clientY };
        this.pressTimer = setTimeout(() => {
            this.pressTimer = null;
            this.pressStart = null;
            this.state.actionMenuId = null;
            this.state.armedDeleteId = previewId;
            this.state.selectedId = id;
            this.ignorePreviewClickId = previewId;
        }, 550);
    }

    onPreviewPointerMove(event) {
        if (this.pressStart && Math.hypot(event.clientX - this.pressStart.x, event.clientY - this.pressStart.y) > 8) this.cancelPreviewPress();
    }

    onPreviewPointerUp() {
        this.cancelPreviewPress();
        setTimeout(() => { this.ignorePreviewClickId = null; }, 400);
    }

    onPreviewClick(id, previewId, event) {
        if (this.removingIds.has(id)) return;
        if (this.ignorePreviewClickId === previewId) {
            this.ignorePreviewClickId = null;
            return;
        }
        if (this.state.armedDeleteId === previewId) {
            if (!this.isLocked) this.removeBlock(id);
            else this.state.armedDeleteId = null;
            return;
        }
        this.state.armedDeleteId = null;
        this.state.selectedId = id;
        if (event.detail >= 2 && !this.isLocked) this.state.actionMenuId = previewId;
        else if (this.state.actionMenuId !== previewId) this.state.actionMenuId = null;
    }

    onPreviewKeydown(id, previewId, event) {
        if (this.isLocked || !((event.key === "F10" && event.shiftKey) || event.key === "ContextMenu")) return;
        event.preventDefault();
        this.state.armedDeleteId = null;
        this.state.selectedId = id;
        this.state.actionMenuId = previewId;
        requestAnimationFrame(() => this.root.el?.querySelector(".ab_editor__preview-item.has-actions .ab_editor__preview-actions button")?.focus());
    }

    onDragStart(id, event) {
        this.cancelPreviewPress();
        this.ignorePreviewClickId = null;
        this.state.armedDeleteId = null;
        this.state.actionMenuId = null;
        if (this.isLocked) { event.preventDefault(); return; }
        this.state.dragId = id;
        this.state.trashDragId = null;
        this.state.selectedId = id;
        event.dataTransfer.effectAllowed = "move";
        event.dataTransfer.setData("text/plain", id);
    }

    onTrashDragStart(entryId, event) {
        if (this.isLocked) { event.preventDefault(); return; }
        this.state.trashDragId = entryId;
        this.state.dragId = null;
        event.dataTransfer.effectAllowed = "move";
        event.dataTransfer.setData("text/plain", entryId);
    }

    onTrashDragOver(event) {
        if (!this.state.dragId || this.isLocked) return;
        event.preventDefault();
        event.dataTransfer.dropEffect = "move";
        this.state.dropId = null;
        this.state.trashDropActive = true;
    }

    onTrashDragLeave(event) {
        if (!event.currentTarget.contains(event.relatedTarget)) this.state.trashDropActive = false;
    }

    onTrashDrop(event) {
        if (!this.state.dragId) return;
        event.preventDefault();
        const id = this.state.dragId;
        this.onDragEnd();
        if (!this.isLocked) this.removeBlock(id);
    }

    onRestoreDragOver(event) {
        if (!this.state.trashDragId || this.isLocked) return;
        event.preventDefault();
        event.dataTransfer.dropEffect = "move";
        this.state.dropId = null;
    }

    onRestoreDrop(event) {
        if (!this.state.trashDragId) return;
        event.preventDefault();
        const entryId = this.state.trashDragId;
        this.onDragEnd();
        if (!this.isLocked) this.restoreDeletedBlock(entryId, this.blocks.length);
    }

    onDragOver(id, event) {
        if (this.isLocked || (!this.state.dragId && !this.state.trashDragId) || this.state.dragId === id) return;
        event.preventDefault();
        event.stopPropagation();
        event.dataTransfer.dropEffect = "move";
        this.state.trashDropActive = false;
        this.state.dropId = id;
        this.state.dropAfter = this.state.dragId ? this.blocks.findIndex((block) => block.id === this.state.dragId) < this.blocks.findIndex((block) => block.id === id) : false;
    }

    onDragEnd() {
        this.state.dragId = null;
        this.state.trashDragId = null;
        this.state.trashDropActive = false;
        this.state.dropId = null;
        this.state.dropAfter = false;
    }

    dragClass(id) {
        return `${this.state.dragId === id ? " is-dragging" : ""}${this.state.dropId === id ? (this.state.dropAfter ? " is-drop-after" : " is-drop-before") : ""}`;
    }

    onDrop(id, event) {
        if (!this.state.dragId && !this.state.trashDragId) return;
        event.preventDefault();
        event.stopPropagation();
        const source = this.state.dragId;
        const entryId = this.state.trashDragId;
        const after = this.blocks.findIndex((block) => block.id === source) < this.blocks.findIndex((block) => block.id === id);
        const targetIndex = this.blocks.findIndex((block) => block.id === id);
        this.onDragEnd();
        if (entryId) {
            if (!this.isLocked && targetIndex >= 0) this.restoreDeletedBlock(entryId, targetIndex);
            return;
        }
        if (this.isLocked || !source || source === id) return;
        this.edit((draft) => {
            const blocks = this.editableBlocks(draft);
            const from = blocks.findIndex((block) => block.id === source);
            if (from < 0 || !blocks.some((block) => block.id === id)) return;
            const [moved] = blocks.splice(from, 1);
            const to = blocks.findIndex((block) => block.id === id);
            blocks.splice(to + (after ? 1 : 0), 0, moved);
        });
    }

    undo() {
        if (this.isLocked || !this.state.history.length) return;
        this.capturePositions();
        this.state.future = [clone(this.state.draft), ...this.state.future];
        this.restoreHistory(this.state.history.at(-1));
        this.state.history = this.state.history.slice(0, -1);
        this.refreshDirty();
    }

    redo() {
        if (this.isLocked || !this.state.future.length) return;
        this.capturePositions();
        this.state.history = [...this.state.history, clone(this.state.draft)];
        this.restoreHistory(this.state.future[0]);
        this.state.future = this.state.future.slice(1);
        this.refreshDirty();
    }

    restoreHistory(snapshot) {
        const metadata = Object.fromEntries(DOCUMENT_FIELDS.filter((field) => !EDITABLE_FIELDS.includes(field)).map((field) => [field, this.state.draft[field]]));
        this.state.draft = { ...snapshot, ...metadata };
    }

    onKeydown = (event) => {
        if (this.state.view === "editor" && event.key === "Escape") {
            this.cancelPreviewPress();
            this.state.armedDeleteId = null;
            this.state.actionMenuId = null;
            return;
        }
        if (this.state.view !== "editor" || !(event.ctrlKey || event.metaKey)) return;
        if (event.target.closest("input,textarea,[contenteditable]")) return;
        if (event.key.toLowerCase() === "z") {
            event.preventDefault();
            event.shiftKey ? this.redo() : this.undo();
        } else if (event.key.toLowerCase() === "y") {
            event.preventDefault();
            this.redo();
        }
    };

    beforeUnload = (event) => {
        if (this.state.dirty) {
            event.preventDefault();
            event.returnValue = "";
        }
    };

    async saveDraft(showToast = true) {
        if (!this.state.dirty) return;
        if (this.state.templateId) {
            if (this.isLocked) return;
            this.state.busy = true;
            const snapshot = this.editableSnapshot(this.state.draft);
            try {
                await this.orm.write("ab_ecommerce_editor_template", [this.state.templateId], {
                    name: this.state.draft.name, blocks: clone(this.state.draft.blocks_en || []), design_tokens: clone(this.state.draft.design_tokens || {}),
                });
                this.savedDraftSnapshot = snapshot;
                this.refreshDirty();
                await this.loadLibrary();
                this.notification.add(_t("Reusable template updated. Published versions stay fixed."), { type: "success" });
            } finally {
                this.state.busy = false;
            }
            return;
        }
        if (!this.state.currentId || this.isLocked) return;
        this.state.busy = true;
        try {
            const snapshot = this.editableSnapshot(this.state.draft);
            const values = Object.fromEntries(EDITABLE_FIELDS.map((field) => [field, this.state.draft[field]]));
            values.website_id = Array.isArray(values.website_id) ? values.website_id[0] : values.website_id;
            const saved = await this.orm.call("ab_ecommerce_editor_document", "save_draft", [[this.state.currentId], values, this.state.draft.draft_token]);
            this.state.draft.write_date = saved.write_date;
            this.state.draft.draft_token = saved.draft_token;
            this.state.draft.state = saved.state;
            this.savedDraftSnapshot = snapshot;
            this.refreshDirty();
            if (showToast) this.notification.add(_t("Draft saved. The live site is unchanged."), { type: "success" });
            await this.loadLibrary();
        } catch (error) {
            this.notification.add(error.data?.message || error.message || _t("The draft could not be saved."), { type: "danger" });
            throw error;
        } finally {
            this.state.busy = false;
        }
    }

    async saveVersion() {
        await this.saveDraft(false);
        await this.orm.call("ab_ecommerce_editor_document", "action_save_version", [[this.state.currentId]]);
        await this.reloadCurrent();
        this.notification.add(_t("A version was saved."), { type: "success" });
    }

    async submitReview() {
        await this.saveDraft(false);
        await this.orm.call("ab_ecommerce_editor_document", "action_submit_review", [[this.state.currentId]]);
        await this.reloadCurrent();
        this.notification.add(_t("Content sent for review."), { type: "success" });
    }

    async returnDraft() {
        await this.orm.call("ab_ecommerce_editor_document", "action_return_draft", [[this.state.currentId]]);
        await this.reloadCurrent();
    }

    async publish() {
        await this.orm.call("ab_ecommerce_editor_document", "action_publish", [[this.state.currentId]]);
        await this.reloadCurrent();
        this.notification.add(_t("Published version is live."), { type: "success" });
    }

    async schedule() {
        if (!this.state.scheduleAt) return;
        await this.orm.call("ab_ecommerce_editor_document", "action_schedule", [[this.state.currentId], new Date(this.state.scheduleAt).toISOString().slice(0, 19).replace("T", " ")]);
        await this.reloadCurrent();
        this.notification.add(_t("Publication scheduled."), { type: "success" });
    }

    async restoreVersion(id) {
        if (!window.confirm(_t("Restore this saved version into a new draft?"))) return;
        await this.orm.call("ab_ecommerce_editor_document", "action_restore_revision", [[this.state.currentId], id]);
        await this.reloadCurrent();
        this.notification.add(_t("Version restored as a draft."), { type: "success" });
    }

    async reloadCurrent() {
        const id = this.state.currentId;
        this.state.dirty = false;
        await this.loadLibrary();
        await this.openDocument(id);
    }

    async duplicateDocument() {
        if (this.state.templateId) {
            const [id] = await this.orm.create("ab_ecommerce_editor_template", [{
                name: `${this.state.draft.name} ${_t("Copy")}`, website_id: this.state.draft.website_id[0],
                blocks: clone(this.blocks), design_tokens: clone(this.state.draft.design_tokens || {}),
            }]);
            this.state.dirty = false;
            await this.loadLibrary();
            this.openTemplate(id);
            return;
        }
        const draft = this.state.draft;
        const values = Object.fromEntries(EDITABLE_FIELDS.map((field) => [field, draft[field]]));
        values.name = `${draft.name} ${_t("Copy")}`;
        values.slug = `${draft.slug}-copy-${Date.now().toString(36)}`;
        values.website_id = Array.isArray(values.website_id) ? values.website_id[0] : values.website_id;
        const [id] = await this.orm.create("ab_ecommerce_editor_document", [values]);
        this.state.dirty = false;
        await this.loadLibrary();
        await this.openDocument(id);
    }

    async saveReusable() {
        const block = this.selectedBlock;
        if (!block || block.type === "template") return;
        const name = window.prompt(_t("Reusable block name"));
        if (!name) return;
        await this.orm.create("ab_ecommerce_editor_template", [{
            name, website_id: this.state.draft.website_id[0], scope: this.state.draft.kind,
            blocks: [clone(block)],
        }]);
        await this.loadLibrary();
        this.notification.add(_t("Reusable block saved."), { type: "success" });
    }

    async savePageTemplate() {
        const name = window.prompt(_t("Template name"));
        if (!name) return;
        const blocks = this.previewBlocks.map(({ sourceId, ...block }, index) => ({ ...clone(block), id: `block_${index}` }));
        await this.orm.create("ab_ecommerce_editor_template", [{
            name, website_id: this.state.draft.website_id[0], blocks, scope: this.state.draft.kind,
            design_tokens: clone(this.state.draft.design_tokens || {}),
        }]);
        await this.loadLibrary();
        this.notification.add(_t("Page template saved."), { type: "success" });
    }

    openTemplate(id) {
        if (this.state.dirty && !window.confirm(_t("Discard unsaved changes?"))) return;
        const template = this.state.templates.find((item) => item.id === id);
        if (!template) return;
        return this.navigate(async () => () => {
            this.state.templateId = id;
            this.state.currentId = null;
            this.state.draft = {
                name: template.name, title_en: template.name, kind: template.scope === "blog" ? "blog" : "page",
                website_id: clone(template.website_id), slug: "template", state: "draft", version: 0,
                blocks_en: clone(template.blocks || []), blocks_ar: [], design_tokens: clone(template.design_tokens || {}),
            };
            this.savedDraftSnapshot = this.editableSnapshot(this.state.draft);
            this.state.language = "en_US";
            this.state.inspector = "content";
            this.state.selectedId = null;
            this.state.armedDeleteId = null;
            this.state.actionMenuId = null;
            this.state.dirty = false;
            this.state.history = [];
            this.state.future = [];
            this.state.versions = [];
            this.state.view = "editor";
        });
    }

    async useTemplate() {
        const draft = this.state.draft;
        const [id] = await this.orm.create("ab_ecommerce_editor_document", [{
            name: draft.name, title_en: draft.name, kind: draft.kind, website_id: draft.website_id[0],
            slug: `page-${Date.now().toString(36)}`, blocks_en: clone(draft.blocks_en || []),
            design_tokens: clone(draft.design_tokens || {}),
        }]);
        this.state.dirty = false;
        await this.loadLibrary();
        await this.openDocument(id);
    }

    addTemplate(id) {
        this.edit((draft) => {
            const block = { id: `t_${Date.now().toString(36)}`, type: "template", template_id: id };
            this.editableBlocks(draft).push(block);
            this.state.selectedId = block.id;
        });
    }

    detachTemplate() {
        const selected = this.selectedBlock;
        const template = this.state.templates.find((item) => item.id === selected?.template_id);
        if (!template) return;
        this.edit((draft) => {
            const blocks = this.editableBlocks(draft);
            const index = blocks.findIndex((item) => item.id === selected.id);
            const detached = template.blocks.map((item, index) => ({ ...clone(item), style: { ...template.design_tokens, ...item.style }, id: `d_${Date.now().toString(36)}_${index}` }));
            blocks.splice(index, 1, ...detached);
            this.state.selectedId = detached[0]?.id || null;
        });
    }

    backToLibrary() {
        if (this.state.dirty && !window.confirm(_t("Discard unsaved changes?"))) return;
        return this.navigate(async () => () => {
            this.state.view = "library";
            this.state.currentId = null;
            this.state.templateId = null;
            this.state.draft = null;
            this.state.dirty = false;
            this.state.armedDeleteId = null;
            this.state.actionMenuId = null;
        });
    }

    onWorkspaceClick(event) {
        if (this.state.view !== "editor") return;
        if (event.target.closest(".ab_editor__preview-block, .ab_editor__preview-actions, .ab_editor__layer, .ab_editor__inspector, .ab_editor__block-palette, .ab_editor__template-option, .ab_editor__trash, .ab_editor__brand, .ab_editor__layout-controls, .ab_editor__theme-toggle, .ab_editor__canvas-toolbar-toggle, .ab_editor__canvas-toolbar-reveal, .ab_editor__layers-panel, .ab_editor__resize-handle")) return;
        this.state.selectedId = null;
        this.state.armedDeleteId = null;
        this.state.actionMenuId = null;
    }

    openLive() {
        if (this.liveUrl) window.open(this.liveUrl, "_blank", "noopener,noreferrer");
    }

    async uploadImage(event) {
        const file = event.target.files[0];
        if (!file || !this.state.currentId) return;
        if (file.size > 5 * 1024 * 1024) {
            this.notification.add(_t("Choose an image smaller than 5 MB."), { type: "warning" });
            return;
        }
        const data = await new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(reader.result.split(",")[1]);
            reader.onerror = reject;
            reader.readAsDataURL(file);
        });
        const url = await this.orm.call("ab_ecommerce_editor_document", "upload_image", [[this.state.currentId], file.name, data]);
        this.updateBlock("url", { target: { value: url } });
        event.target.value = "";
    }

    previewStorefront() {
        if (this.state.currentId && !this.state.dirty) window.open(`/editor/preview/${this.state.currentId}`, "_blank", "noopener,noreferrer");
    }
}

registry.category("actions").add("ab_ecommerce_editor.workspace", EditorWorkspace);
