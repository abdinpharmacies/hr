import { Component, onMounted, onWillDestroy, useExternalListener, useRef, useState, useSubEnv } from "@odoo/owl";
import { Builder } from "@html_builder/builder";
import { CORE_PLUGINS } from "@html_builder/core/core_plugins";
import { LocalOverlayContainer } from "@html_editor/local_overlay_container";
import { MediaPlugin } from "@html_editor/main/media/media_plugin";
import { loadBundle } from "@web/core/assets";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { uniqueId } from "@web/core/utils/functions";
import { useChildRef, useService } from "@web/core/utils/hooks";

class DraftMediaPlugin extends MediaPlugin {
    async openMediaDialog(params = {}) {
        const image = await this.config.pickDraftImage(params.node);
        if (image && this.editable.isConnected) {
            await (params.save || ((element) => this.onSaveMediaDialog(element, params)))(image);
        }
    }
}

class DraftDialog extends Dialog {
    static props = { ...Dialog.props, discard: Function };
    dismiss() {
        this.props.discard();
    }
}

export class SectionBuilder extends Component {
    static template = "ab_ecommerce_editor.SectionBuilder";
    static components = { Builder, DraftDialog, LocalOverlayContainer };
    static props = { pageBlocks: { type: Array, optional: true }, blockLabel: Function, fieldsFor: Function, thumbnail: Function, styleFor: Function, html: String, websiteId: Number, language: String, documentId: Number, apply: Function, close: Function };

    setup() {
        this.pageTitle = _t("Design page layout");
        this.sectionTitle = _t("Website section");
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.overlayRef = useChildRef();
        this.fileRef = useRef("upload");
        this.frameRef = useRef("frame");
        onMounted(() => this.loadFrame());
        this.linkedValues = new Map();
        this.state = useState({ selectedLink: null, frame: false, mobile: false, ready: false, saving: false, error: "" });
        useSubEnv({ localOverlayContainerKey: uniqueId("ab-section"), builderRef: useRef("builder") });
        this.plugins = [...new Set([...CORE_PLUGINS, ...registry.category("builder-plugins").getAll()])]
            .filter((plugin) => !["saveSnippet", "file", "many2OneOption", "monetaryField", "imageField"].includes(plugin.id))
            .map((plugin) => plugin === MediaPlugin ? DraftMediaPlugin : plugin);
        useExternalListener(window, "beforeunload", (event) => {
            if (this.hasChanges()) {
                event.preventDefault();
                event.returnValue = "";
            }
        });
        this.config = {
            onEditorReady: () => {
                this.originalLayout = new Map(Array.from(this.cleanWrap().children, (el) => [el.dataset.abBlock, el.outerHTML]));
                this.state.ready = true;
            },
            getRecordInfo: () => ({ resModel: "ab_ecommerce_editor_document", resId: this.props.documentId }),
            pickDraftImage: (previous) => this.pickImage(previous),
        };
        onWillDestroy(() => { this.finishPick?.(null); });
    }

    hasChanges() {
        return this.linkedValues.size > 0 || this.editor?.shared.history?.canUndo();
    }

    discard() {
        if (!this.state.saving && (!this.hasChanges() || window.confirm(_t("Discard unsaved changes?")))) {
            this.props.close();
        }
    }

    async loadFrame() {
        const frame = this.frameRef.el;
        if (!frame?.contentDocument?.body || this.frameDocument === frame.contentDocument) return;
        this.frameDocument = frame.contentDocument;
        try {
            const doc = frame.contentDocument;
            doc.documentElement.dir = this.props.language === "ar_001" ? "rtl" : "ltr";
            doc.documentElement.lang = this.props.language.replace("_", "-");
            doc.body.innerHTML = '<div id="wrapwrap"><div id="wrap" class="oe_structure oe_empty o_editable"></div></div>';
            const wrap = doc.getElementById("wrap");
            if (this.props.pageBlocks) {
                const styles = doc.createElement("style");
                styles.textContent = this.props.pageBlocks.map((block) =>
                    `[data-ab-block="${CSS.escape(block.id)}"] {${this.props.styleFor(block.style || {})}}`
                ).join("\n");
                doc.head.append(styles);
                for (const block of this.props.pageBlocks) wrap.append(this.renderBlock(doc, block));
            } else {
                wrap.innerHTML = this.props.html;
            }
            doc.addEventListener("click", (event) => {
                if (event.target.closest("a")) event.preventDefault();
                this.selectLinkedBlock(event.target);
            }, true);
            doc.addEventListener("focusin", (event) => this.selectLinkedBlock(event.target));
            const options = { targetDoc: doc, js: false };
            await Promise.all([
                loadBundle("web.assets_frontend", options),
                loadBundle("html_builder.assets_inside_builder_iframe", options),
                this.env.services["html_builder.snippets"].getSnippetModel("ab_ecommerce_editor.section_snippets")
                    .reload({ website_id: this.props.websiteId, lang: this.props.language }),
            ]);
            this.iframeLoaded = Promise.resolve(frame);
            this.state.frame = true;
        } catch (error) {
            this.state.error = error.message;
        }
    }

    rememberEditor(editor) {
        editor.config.publicAttachments = false;
        this.editor = editor;
    }

    cleanWrap() {
        return this.editor.getElContent().querySelector("#wrap");
    }

    renderBlock(doc, block) {
        const section = doc.createElement("section");
        section.className = "s_text_block";
        section.dataset.snippet = "s_text_block";
        section.dataset.abBlock = block.id;
        section.dataset.name = this.props.blockLabel(block.type);
        const container = doc.createElement("div");
        container.className = "container";
        section.append(container);
        const add = (tag, text) => {
            const element = doc.createElement(tag);
            element.textContent = text || "";
            container.append(element);
            return element;
        };
        switch (block.type) {
            case "website_section":
                container.className = "oe_structure";
                container.innerHTML = block.html;
                break;
            case "hero":
                add("h2", block.title);
                add("p", block.body);
                if (block.label) add("a", block.label).setAttribute("href", block.url || "/");
                break;
            case "heading": add("h2", block.title); break;
            case "text": add("p", block.body); break;
            case "button": {
                const button = add("a", block.label);
                button.className = "btn btn-primary";
                button.setAttribute("href", block.url || "/");
                break;
            }
            case "image": {
                const image = add("img");
                image.setAttribute("src", block.url || "");
                image.alt = block.alt || "";
                break;
            }
            case "divider": add("hr"); break;
            default:
                container.className = "o_not_editable alert alert-secondary";
                if (this.props.fieldsFor(block).length) section.tabIndex = 0;
                add("strong", section.dataset.name);
                if (this.props.thumbnail(block)) {
                    const frame = doc.createElement("iframe");
                    frame.setAttribute("sandbox", "");
                    frame.tabIndex = -1;
                    frame.title = section.dataset.name;
                    frame.style.cssText = "pointer-events:none;border:0;width:100%;height:240px";
                    frame.srcdoc = this.props.thumbnail(block);
                    container.append(frame);
                }
        }
        return section;
    }

    selectLinkedBlock(target) {
        const section = target.closest("[data-ab-block]");
        const block = this.props.pageBlocks?.find((item) => item.id === section?.dataset.abBlock);
        this.state.selectedLink = block && this.props.fieldsFor(block).length ? block.id : null;
    }

    get linkedBlock() {
        return this.props.pageBlocks?.find((block) => block.id === this.state.selectedLink);
    }

    linkedValue(key) {
        return this.linkedValues.get(this.linkedBlock.id)?.[key] ?? this.linkedBlock.content?.[key] ?? "";
    }

    editLinkedValue(field, event) {
        const block = this.linkedBlock;
        const content = { ...block.content, ...this.linkedValues.get(block.id), [field.key]: event.target.value };
        this.linkedValues.set(block.id, content);
        const source = this.props.thumbnail(block);
        const frame = this.frameDocument.querySelector(`[data-ab-block="${CSS.escape(block.id)}"] iframe`);
        if (frame && source) {
            const preview = new DOMParser().parseFromString(source, "text/html");
            for (const element of preview.querySelectorAll("[data-ae-field]")) {
                if (Object.hasOwn(content, element.dataset.aeField)) element.textContent = content[element.dataset.aeField];
            }
            frame.srcdoc = "<!doctype html>" + preview.documentElement.outerHTML;
        }
    }

    async readPage(wrap) {
        const originals = new Map(this.props.pageBlocks.map((block) => [block.id, block]));
        const seen = new Set();
        const result = [];
        const changed = [];
        for (const element of wrap.children) {
            const id = element.dataset.abBlock;
            const block = originals.get(id);
            const protectedBlock = block && !["website_section", "hero", "heading", "text", "image", "button", "divider"].includes(block.type);
            if (protectedBlock && block.type !== "template" && seen.has(id)) throw new Error(_t("Keep a single copy of each linked section."));
            const same = block && (protectedBlock || element.outerHTML === this.originalLayout.get(id));
            const copyId = block && !seen.has(id) ? id : uniqueId("layout_") + "_" + Date.now().toString(36);
            seen.add(id);
            if (same) {
                const linkedContent = this.linkedValues.get(id);
                result.push(linkedContent ? { ...block, id: copyId, content: linkedContent } : { ...block, id: copyId });
            } else {
                let richContent = element.outerHTML;
                if (block?.type === "website_section" && element.children.length === 1 && element.firstElementChild.className === "oe_structure") {
                    const original = wrap.ownerDocument.createElement("template");
                    original.innerHTML = this.originalLayout.get(id);
                    const shell = original.content.firstElementChild;
                    if (shell && shell.cloneNode().isEqualNode(element.cloneNode()) &&
                        shell.firstElementChild?.cloneNode().isEqualNode(element.firstElementChild.cloneNode())) {
                        richContent = element.firstElementChild.innerHTML;
                    }
                }
                const section = { id: copyId, type: "website_section", html: richContent, active: block?.active !== false, style: block?.style || {} };
                changed.push(section);
                result.push(section);
            }
        }
        if (this.props.pageBlocks.some((block) => block.type === "storefront_page" && !seen.has(block.id))) {
            throw new Error(_t("Keep the original storefront section in this page."));
        }
        if (result.length > 80) throw new Error(_t("A page can contain up to 80 blocks."));
        if (changed.length) {
            const cleaned = await this.prepareSections(changed.map((section) => section.html));
            changed.forEach((section, index) => { section.html = cleaned[index]; });
        }
        return result;
    }

    prepareSections(sources) {
        return this.orm.call("ab_ecommerce_editor_document", "prepare_website_sections", [sources]);
    }

    pickImage(previous) {
        if (!this.props.documentId) {
            this.notification.add(_t("Upload images from a saved document."), { type: "info" });
            return Promise.resolve(null);
        }
        this.previousImage = previous;
        return new Promise((resolve) => {
            this.finishPick?.(null);
            this.finishPick = resolve;
            this.fileRef.el.click();
        });
    }

    async uploadImage(event) {
        const file = event.target.files[0];
        event.target.value = "";
        const resolve = this.finishPick;
        this.finishPick = null;
        if (!resolve || !file) return resolve?.(null);
        try {
            if (file.size > 5 * 1024 * 1024) throw new Error(_t("Choose an image smaller than 5 MB."));
            const data = await new Promise((done, fail) => {
                const reader = new FileReader();
                reader.onload = () => done(reader.result.split(",")[1]);
                reader.onerror = () => fail(reader.error);
                reader.readAsDataURL(file);
            });
            const url = await this.orm.call("ab_ecommerce_editor_document", "upload_image", [[this.props.documentId], file.name, data]);
            const img = this.editor.document.createElement("img");
            img.src = url;
            img.alt = this.previousImage?.alt || "";
            resolve(img);
        } catch (error) {
            resolve(null);
            this.notification.add(error.message, { type: "danger" });
        }
    }

    async stageEmbeddedImages(wrap) {
        for (const image of wrap.querySelectorAll('img[src^="data:"]')) {
            const match = /^data:image\/(png|jpeg|webp);base64,([a-zA-Z0-9+/=]+)$/.exec(image.getAttribute("src"));
            if (!match || !this.props.documentId) throw new Error(_t("Upload images from a saved document."));
            image.src = await this.orm.call("ab_ecommerce_editor_document", "upload_image", [
                [this.props.documentId], `image.${match[1]}`, match[2],
            ]);
        }
    }

    async apply() {
        if (this.state.saving || !this.state.ready) return;
        this.state.saving = true;
        try {
            await this.editor.shared.operation.next(async () => {
                const wrap = this.cleanWrap();
                await this.stageEmbeddedImages(wrap);
                const source = this.props.pageBlocks ? await this.readPage(wrap) : (await this.prepareSections([wrap.innerHTML]))[0];
                this.props.apply(source);
                this.props.close();
            }, { withLoadingEffect: false, canTimeout: false });
        } catch (error) {
            this.state.error = error.message;
        } finally {
            this.state.saving = false;
        }
    }
}

registry.category("lazy_components").add("ab_ecommerce_editor.SectionBuilder", SectionBuilder);
