/** @odoo-module **/
import { registry } from "@web/core/registry";
import { Component, useState, useRef, onWillStart, onMounted, onWillUnmount } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { getAllComponents, validateRegistry } from "../core_ui/registry";
import "../core_ui/components/index";
import { CoreUISearch } from "./core_ui_search";
import { CoreUISidebar } from "./core_ui_sidebar";
import { CoreUIGallery } from "./core_ui_gallery";
import { CoreUIInspector } from "./core_ui_inspector";
import { CoreUINotebook } from "./core_ui_notebook";
import { CoreUIDesignLab } from "../core_ui/design_lab/design_lab";
import { DEFAULT_LAB_STATE, BUILTIN_PROFILES, applyDesignVars, getActiveProfileConfig } from "../core_ui/design_lab/design_lab_config";
import { loadAll, saveAll, savePref, notifyPrefsChanged } from "../core_ui/preferences";

const ENTRY_DELAYS = {
    SETTINGS_BLUR: 50,
    OVERLAY_FADE: 300,
    WORKSPACE_GROW: 500,
    ELEMENTS_REVEAL: 900,
    ELEMENTS_DELAY: 100,
};

const EXIT_DELAYS = {
    ELEMENTS_HIDE: 50,
    WORKSPACE_SHRINK: 350,
    OVERLAY_FADE: 600,
    SETTINGS_RESTORE: 750,
    CLOSE: 900,
};

class CoreUIWorkspace extends Component {
    static template = "core_ui.workspace";
    static components = {
        CoreUISearch,
        CoreUISidebar,
        CoreUIGallery,
        CoreUIInspector,
        CoreUINotebook,
        CoreUIDesignLab,
    };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.workspaceRef = useRef("workspace");

        this.state = useState({
            phase: 'initial',
            overlayVisible: false,
            workspaceVisible: false,
            elementsVisible: false,
            exiting: false,
            searchQuery: "",
            selectedCategory: null,
            selectedComponent: null,
            inspectorVisible: true,
            categories: [],
            components: [],
            favorites: [],
            recentComponents: [],
            notebookItems: [],
            recentlyUsedComponents: [],
            loading: true,
            designLab: { ...DEFAULT_LAB_STATE },
            themeMode: 'light',
        });

        onWillStart(async () => {
            await this.loadData();
        });

        onMounted(() => {
            document.body.classList.add('core_ui_workspace_active');
            this.restorePreferences();
            this.startEntrySequence();
        });

        onWillUnmount(() => {
            document.body.classList.remove('core_ui_workspace_active');
        });
    }

    startEntrySequence() {
        const d = ENTRY_DELAYS;
        setTimeout(() => {
            document.body.classList.add('core_ui_transition_phase_1');
        }, d.SETTINGS_BLUR);
        setTimeout(() => {
            this.state.overlayVisible = true;
        }, d.OVERLAY_FADE);
        setTimeout(() => {
            this.state.workspaceVisible = true;
        }, d.WORKSPACE_GROW);
        setTimeout(() => {
            this.state.elementsVisible = true;
            this.applyDesignLab();
        }, d.ELEMENTS_REVEAL);
    }

    onUpdateDesignLab(newState) {
        this.state.designLab = newState;
        this.applyDesignLab();
        this.persistPrefs();
    }

    onSaveProfile(name) {
        const savedRaw = localStorage.getItem("core_ui_saved_profiles");
        const saved = savedRaw ? JSON.parse(savedRaw) : [];
        saved.push({
            key: "custom_" + Date.now(),
            label: name,
            config: getActiveProfileConfig(this.state.designLab),
        });
        localStorage.setItem("core_ui_saved_profiles", JSON.stringify(saved));
        this.notification.add("Profile saved: " + name, { type: "success" });
    }

    applyDesignLab() {
        if (this.workspaceRef && this.workspaceRef.el) {
            applyDesignVars(this.workspaceRef.el, this.state.designLab);
        }
    }

    _findProfileConfig(key) {
        const builtin = BUILTIN_PROFILES[key];
        if (builtin) return builtin.config;
        try {
            const savedRaw = localStorage.getItem("core_ui_saved_profiles");
            if (savedRaw) {
                const saved = JSON.parse(savedRaw);
                const found = saved.find(p => p.key === key);
                if (found) return found.config;
            }
        } catch (_) {}
        return null;
    }

    onLoadProfile(key) {
        if (key === "default") {
            this.state.designLab = {
                ...this.state.designLab,
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
            };
            this.applyDesignLab();
            return;
        }
        const cfg = this._findProfileConfig(key);
        if (!cfg) return;
        this.state.designLab = {
            ...this.state.designLab,
            theme: cfg.theme || DEFAULT_LAB_STATE.theme,
            palette: cfg.palette || DEFAULT_LAB_STATE.palette,
            typography: cfg.typography || DEFAULT_LAB_STATE.typography,
            spacing: cfg.spacing || DEFAULT_LAB_STATE.spacing,
            radius: cfg.radius || DEFAULT_LAB_STATE.radius,
            shadow: cfg.shadow || DEFAULT_LAB_STATE.shadow,
            border: cfg.border || DEFAULT_LAB_STATE.border,
            gradient: cfg.gradient || DEFAULT_LAB_STATE.gradient,
            motion: cfg.motion || DEFAULT_LAB_STATE.motion,
            hoverEffects: cfg.hoverEffects || DEFAULT_LAB_STATE.hoverEffects,
        };
        this.applyDesignLab();
    }

    async loadData() {
        try {
            const [categories, ormComponents] = await Promise.all([
                this.orm.searchRead('core_ui.category', [], ['id', 'name', 'icon', 'sequence', 'parent_id', 'component_count', 'description'], { order: 'sequence'}),
                this.orm.searchRead('core_ui.component', [['active', '=', true]], ['id', 'component_id', 'name', 'description', 'tags', 'keywords', 'version', 'status', 'template_ref', 'usage_count', 'is_favorite', 'when_to_use', 'when_not_to_use', 'accessibility_notes', 'dependencies'], { order: 'sequence'}),
            ]);

            validateRegistry();
            const registryComponents = getAllComponents();

            const ormMap = {};
            for (const oc of ormComponents) {
                ormMap[oc.component_id] = oc;
            }

            const components = registryComponents.map(rc => {
                const orm = ormMap[rc.component_id] || {};
                return {
                    id: rc.component_id,
                    component_id: rc.component_id,
                    name: rc.name,
                    category: rc.category,
                    version: rc.version,
                    status: rc.status,
                    description: rc.description,
                    keywords: rc.keywords,
                    template_ref: rc.templateRef || rc.component_id,
                    tags: orm.tags || "",
                    usage_count: orm.usage_count || 0,
                    is_favorite: orm.is_favorite || false,
                    when_to_use: orm.when_to_use || "",
                    when_not_to_use: orm.when_not_to_use || "",
                    accessibility_notes: orm.accessibility_notes || "",
                    dependencies: orm.dependencies || "",
                    _meta: rc,
                };
            });

            const updatedCategories = categories.map(cat => ({
                ...cat,
                component_count: components.filter(c => c.category === cat.name).length,
            }));

            this.state.categories = updatedCategories;
            this.state.components = components;
            this.state.loading = false;
        } catch (err) {
            console.error('[CoreUI Workspace] Failed to load:', err);
            this.state.loading = false;
        }
    }

    get selectedComponentMeta() {
        const comp = this.state.selectedComponent;
        return comp ? comp._meta || null : null;
    }

    get galleryCategoryFilter() {
        if (!this.state.selectedCategory) return null;
        const cat = this.state.categories.find(c => c.id === this.state.selectedCategory);
        return cat ? cat.name : null;
    }

    onSearch(query) {
        this.state.searchQuery = query;
    }

    onSelectCategory(catId) {
        this.state.selectedCategory = this.state.selectedCategory === catId ? null : catId;
        this.state.selectedComponent = null;
    }

    onSelectComponent(comp) {
        this.state.selectedComponent = comp;
        this.state.inspectorVisible = true;
        this.addToRecent(comp);
    }

    closeInspector() {
        this.state.inspectorVisible = false;
    }

    onCopiedAiPrompt(compId) {
        const existing = this.state.recentlyUsedComponents.findIndex(
            c => c.component_id === compId || c.id === compId
        );
        if (existing >= 0) {
            this.state.recentlyUsedComponents.splice(existing, 1);
        }
        const comp = this.state.components.find(
            c => c.component_id === compId || c.id === compId
        );
        if (comp) {
            this.state.recentlyUsedComponents.unshift(comp);
            if (this.state.recentlyUsedComponents.length > 10) {
                this.state.recentlyUsedComponents.length = 10;
            }
        }
    }

    persistPrefs() {
        savePref('theme', this.state.themeMode);
        savePref('designLabTheme', this.state.designLab.theme);
        savePref('palette', this.state.designLab.palette);
        savePref('typography', this.state.designLab.typography);
        savePref('spacing', this.state.designLab.spacing);
        savePref('radius', this.state.designLab.radius);
        savePref('shadow', this.state.designLab.shadow);
        savePref('border', this.state.designLab.border);
        savePref('gradient', this.state.designLab.gradient);
        savePref('motion', this.state.designLab.motion);
        savePref('hoverEffects', this.state.designLab.hoverEffects);
        savePref('previewMode', this.state.designLab.previewMode);
        notifyPrefsChanged({ theme: this.state.themeMode });
    }

    restorePreferences() {
        const prefs = loadAll();
        if (prefs.theme === 'dark') {
            this.state.themeMode = 'dark';
            const root = document.querySelector('.core_ui_workspace');
            if (root) {
                root.classList.add('core_ui_theme_dark');
            }
        }
        if (prefs.designLabTheme) {
            this.state.designLab.theme = prefs.designLabTheme;
        }
        if (prefs.palette) this.state.designLab.palette = prefs.palette;
        if (prefs.typography) this.state.designLab.typography = prefs.typography;
        if (prefs.spacing) this.state.designLab.spacing = prefs.spacing;
        if (prefs.radius) this.state.designLab.radius = prefs.radius;
        if (prefs.shadow) this.state.designLab.shadow = prefs.shadow;
        if (prefs.border) this.state.designLab.border = prefs.border;
        if (prefs.gradient) this.state.designLab.gradient = prefs.gradient;
        if (prefs.motion) this.state.designLab.motion = prefs.motion;
        if (prefs.hoverEffects) this.state.designLab.hoverEffects = prefs.hoverEffects;
        if (prefs.previewMode) this.state.designLab.previewMode = prefs.previewMode;
        this.applyDesignLab();
    }

    toggleTheme() {
        this.state.themeMode = this.state.themeMode === 'dark' ? 'light' : 'dark';
        const root = document.querySelector('.core_ui_workspace');
        if (root) {
            root.classList.toggle('core_ui_theme_dark', this.state.themeMode === 'dark');
        }
        this.persistPrefs();
    }

    addToRecent(comp) {
        const existing = this.state.recentComponents.findIndex(c => c.id === comp.id);
        if (existing >= 0) {
            this.state.recentComponents.splice(existing, 1);
        }
        this.state.recentComponents.unshift(comp);
        if (this.state.recentComponents.length > 10) {
            this.state.recentComponents.length = 10;
        }
    }

    _findComponentData(compIdOrObj) {
        const id = typeof compIdOrObj === "string" ? compIdOrObj : compIdOrObj?.component_id || compIdOrObj?.id;
        const comp = this.state.components.find(c => c.component_id === id || c.id === id);
        return comp || { component_id: id, id, name: id };
    }

    addToNotebook(compId) {
        this.addNotebookItem(compId, null);
    }

    addNotebookItem(compId, copyType) {
        const existing = this.state.notebookItems.find(
            item => item.componentId === compId
        );
        if (existing) {
            if (copyType && !existing.copiedTypes.includes(copyType)) {
                existing.copiedTypes.push(copyType);
            }
            existing.lastCopiedAt = Date.now();
            return;
        }
        const comp = this._findComponentData(compId);
        this.state.notebookItems.unshift({
            componentId: comp.component_id || comp.id,
            name: comp.name || comp.component_id || comp.id,
            category: comp.category || "",
            version: comp.version || "1.0.0",
            status: comp.status || "stable",
            templateRef: comp.template_ref || comp.component_id || comp.id,
            copiedTypes: copyType ? [copyType] : [],
            firstCopiedAt: Date.now(),
            lastCopiedAt: Date.now(),
            pinned: false,
        });
    }

    onNotebookCopy(compId, copyType) {
        this.addNotebookItem(compId, copyType);
        this.onCopiedAiPrompt(compId);
    }

    removeFromNotebook(componentId) {
        const idx = this.state.notebookItems.findIndex(
            item => item.componentId === componentId
        );
        if (idx >= 0) {
            this.state.notebookItems.splice(idx, 1);
        }
    }

    clearNotebook() {
        this.state.notebookItems.splice(0, this.state.notebookItems.length);
        this.notification.add("Notebook cleared", { type: "info" });
    }

    togglePinNotebook(componentId) {
        const item = this.state.notebookItems.find(i => i.componentId === componentId);
        if (item) {
            item.pinned = !item.pinned;
            if (item.pinned) {
                const idx = this.state.notebookItems.indexOf(item);
                this.state.notebookItems.splice(idx, 1);
                this.state.notebookItems.unshift(item);
            }
        }
    }

    jumpToComponent(componentId) {
        const comp = this._findComponentData(componentId);
        if (comp) {
            this.state.selectedComponent = comp;
            this.state.inspectorVisible = true;
            this.addToRecent(comp);
        }
    }

    async exitWorkspace() {
        const d = EXIT_DELAYS;
        this.state.exiting = true;
        this.state.elementsVisible = false;
        setTimeout(() => {
            this.state.workspaceVisible = false;
        }, d.WORKSPACE_SHRINK);
        setTimeout(() => {
            this.state.overlayVisible = false;
        }, d.OVERLAY_FADE);
        setTimeout(() => {
            document.body.classList.remove('core_ui_transition_phase_1');
        }, d.SETTINGS_RESTORE);
        setTimeout(() => {
            document.body.classList.remove('core_ui_workspace_active');
            this.action.doAction({
                type: 'ir.actions.act_window_close',
            });
        }, d.CLOSE);
    }
}

registry.category("actions").add("core_ui.workspace", CoreUIWorkspace);

class CoreUIGalleryOnly extends Component {
    static template = "core_ui.workspace";
    static components = {
        CoreUISearch,
        CoreUISidebar,
        CoreUIGallery,
        CoreUIInspector,
        CoreUINotebook,
        CoreUIDesignLab,
    };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.workspaceRef = useRef("workspace");

        this.state = useState({
            phase: 'initial',
            overlayVisible: true,
            workspaceVisible: true,
            elementsVisible: true,
            exiting: false,
            searchQuery: "",
            selectedCategory: null,
            selectedComponent: null,
            inspectorVisible: true,
            categories: [],
            components: [],
            favorites: [],
            recentComponents: [],
            notebookItems: [],
            recentlyUsedComponents: [],
            loading: true,
            designLab: { ...DEFAULT_LAB_STATE },
            themeMode: 'light',
        });

        onWillStart(async () => {
            await this.loadData();
        });

        onMounted(() => {
            document.body.classList.add('core_ui_workspace_active');
            this.restorePreferences();
        });

        onWillUnmount(() => {
            document.body.classList.remove('core_ui_workspace_active');
        });
    }

    persistPrefs() {
        savePref('theme', this.state.themeMode);
        savePref('designLabTheme', this.state.designLab.theme);
        savePref('palette', this.state.designLab.palette);
        savePref('typography', this.state.designLab.typography);
        savePref('spacing', this.state.designLab.spacing);
        savePref('radius', this.state.designLab.radius);
        savePref('shadow', this.state.designLab.shadow);
        savePref('border', this.state.designLab.border);
        savePref('gradient', this.state.designLab.gradient);
        savePref('motion', this.state.designLab.motion);
        savePref('hoverEffects', this.state.designLab.hoverEffects);
        savePref('previewMode', this.state.designLab.previewMode);
        notifyPrefsChanged({ theme: this.state.themeMode });
    }

    restorePreferences() {
        const prefs = loadAll();
        if (prefs.theme === 'dark') {
            this.state.themeMode = 'dark';
            const root = document.querySelector('.core_ui_workspace');
            if (root) {
                root.classList.add('core_ui_theme_dark');
            }
        }
        if (prefs.designLabTheme) {
            this.state.designLab.theme = prefs.designLabTheme;
        }
        if (prefs.palette) this.state.designLab.palette = prefs.palette;
        if (prefs.typography) this.state.designLab.typography = prefs.typography;
        if (prefs.spacing) this.state.designLab.spacing = prefs.spacing;
        if (prefs.radius) this.state.designLab.radius = prefs.radius;
        if (prefs.shadow) this.state.designLab.shadow = prefs.shadow;
        if (prefs.border) this.state.designLab.border = prefs.border;
        if (prefs.gradient) this.state.designLab.gradient = prefs.gradient;
        if (prefs.motion) this.state.designLab.motion = prefs.motion;
        if (prefs.hoverEffects) this.state.designLab.hoverEffects = prefs.hoverEffects;
        if (prefs.previewMode) this.state.designLab.previewMode = prefs.previewMode;
        this.applyDesignLab();
    }

    toggleTheme() {
        this.state.themeMode = this.state.themeMode === 'dark' ? 'light' : 'dark';
        const root = document.querySelector('.core_ui_workspace');
        if (root) {
            root.classList.toggle('core_ui_theme_dark', this.state.themeMode === 'dark');
        }
        this.persistPrefs();
    }

    async loadData() {
        try {
            const [categories, ormComponents] = await Promise.all([
                this.orm.searchRead('core_ui.category', [], ['id', 'name', 'icon', 'sequence', 'parent_id', 'component_count', 'description'], { order: 'sequence'}),
                this.orm.searchRead('core_ui.component', [['active', '=', true]], ['id', 'component_id', 'name', 'description', 'tags', 'keywords', 'version', 'status', 'template_ref', 'usage_count', 'is_favorite', 'when_to_use', 'when_not_to_use', 'accessibility_notes', 'dependencies'], { order: 'sequence'}),
            ]);

            validateRegistry();
            const registryComponents = getAllComponents();

            const ormMap = {};
            for (const oc of ormComponents) {
                ormMap[oc.component_id] = oc;
            }

            const components = registryComponents.map(rc => {
                const orm = ormMap[rc.component_id] || {};
                return {
                    id: rc.component_id,
                    component_id: rc.component_id,
                    name: rc.name,
                    category: rc.category,
                    version: rc.version,
                    status: rc.status,
                    description: rc.description,
                    keywords: rc.keywords,
                    template_ref: rc.templateRef || rc.component_id,
                    tags: orm.tags || "",
                    usage_count: orm.usage_count || 0,
                    is_favorite: orm.is_favorite || false,
                    when_to_use: orm.when_to_use || "",
                    when_not_to_use: orm.when_not_to_use || "",
                    accessibility_notes: orm.accessibility_notes || "",
                    dependencies: orm.dependencies || "",
                    _meta: rc,
                };
            });

            const updatedCategories = categories.map(cat => ({
                ...cat,
                component_count: components.filter(c => c.category === cat.name).length,
            }));

            this.state.categories = updatedCategories;
            this.state.components = components;
            this.state.loading = false;
        } catch (err) {
            console.error('[CoreUI Workspace] Failed to load:', err);
            this.state.loading = false;
        }
    }

    get selectedComponentMeta() {
        const comp = this.state.selectedComponent;
        return comp ? comp._meta || null : null;
    }

    get galleryCategoryFilter() {
        if (!this.state.selectedCategory) return null;
        const cat = this.state.categories.find(c => c.id === this.state.selectedCategory);
        return cat ? cat.name : null;
    }

    onSearch(query) {
        this.state.searchQuery = query;
    }

    onSelectCategory(catId) {
        this.state.selectedCategory = this.state.selectedCategory === catId ? null : catId;
        this.state.selectedComponent = null;
    }

    onSelectComponent(comp) {
        this.state.selectedComponent = comp;
        this.state.inspectorVisible = true;
        const existing = this.state.recentComponents.findIndex(c => c.id === comp.id);
        if (existing >= 0) {
            this.state.recentComponents.splice(existing, 1);
        }
        this.state.recentComponents.unshift(comp);
        if (this.state.recentComponents.length > 10) {
            this.state.recentComponents.length = 10;
        }
    }

    closeInspector() {
        this.state.inspectorVisible = false;
    }

    onCopiedAiPrompt(compId) {
        const existing = this.state.recentlyUsedComponents.findIndex(
            c => c.component_id === compId || c.id === compId
        );
        if (existing >= 0) {
            this.state.recentlyUsedComponents.splice(existing, 1);
        }
        const comp = this.state.components.find(
            c => c.component_id === compId || c.id === compId
        );
        if (comp) {
            this.state.recentlyUsedComponents.unshift(comp);
            if (this.state.recentlyUsedComponents.length > 10) {
                this.state.recentlyUsedComponents.length = 10;
            }
        }
    }

    onUpdateDesignLab(newState) {
        this.state.designLab = newState;
        this.applyDesignLab();
        this.persistPrefs();
    }

    _findProfileConfig(key) {
        const builtin = BUILTIN_PROFILES[key];
        if (builtin) return builtin.config;
        try {
            const savedRaw = localStorage.getItem("core_ui_saved_profiles");
            if (savedRaw) {
                const saved = JSON.parse(savedRaw);
                const found = saved.find(p => p.key === key);
                if (found) return found.config;
            }
        } catch (_) {}
        return null;
    }

    onLoadProfile(key) {
        if (key === "default") {
            this.state.designLab = {
                ...this.state.designLab,
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
            };
            this.applyDesignLab();
            return;
        }
        const cfg = this._findProfileConfig(key);
        if (!cfg) return;
        this.state.designLab = {
            ...this.state.designLab,
            theme: cfg.theme || DEFAULT_LAB_STATE.theme,
            palette: cfg.palette || DEFAULT_LAB_STATE.palette,
            typography: cfg.typography || DEFAULT_LAB_STATE.typography,
            spacing: cfg.spacing || DEFAULT_LAB_STATE.spacing,
            radius: cfg.radius || DEFAULT_LAB_STATE.radius,
            shadow: cfg.shadow || DEFAULT_LAB_STATE.shadow,
            border: cfg.border || DEFAULT_LAB_STATE.border,
            gradient: cfg.gradient || DEFAULT_LAB_STATE.gradient,
            motion: cfg.motion || DEFAULT_LAB_STATE.motion,
            hoverEffects: cfg.hoverEffects || DEFAULT_LAB_STATE.hoverEffects,
        };
        this.applyDesignLab();
    }

    onSaveProfile(name) {
        const savedRaw = localStorage.getItem("core_ui_saved_profiles");
        const saved = savedRaw ? JSON.parse(savedRaw) : [];
        saved.push({
            key: "custom_" + Date.now(),
            label: name,
            config: getActiveProfileConfig(this.state.designLab),
        });
        localStorage.setItem("core_ui_saved_profiles", JSON.stringify(saved));
        this.notification.add("Profile saved: " + name, { type: "success" });
    }

    applyDesignLab() {
        if (this.workspaceRef && this.workspaceRef.el) {
            applyDesignVars(this.workspaceRef.el, this.state.designLab);
        }
    }

    _findComponentData(compIdOrObj) {
        const id = typeof compIdOrObj === "string" ? compIdOrObj : compIdOrObj?.component_id || compIdOrObj?.id;
        const comp = this.state.components.find(c => c.component_id === id || c.id === id);
        return comp || { component_id: id, id, name: id };
    }

    addToNotebook(compId) {
        this.addNotebookItem(compId, null);
    }

    addNotebookItem(compId, copyType) {
        const existing = this.state.notebookItems.find(
            item => item.componentId === compId
        );
        if (existing) {
            if (copyType && !existing.copiedTypes.includes(copyType)) {
                existing.copiedTypes.push(copyType);
            }
            existing.lastCopiedAt = Date.now();
            return;
        }
        const comp = this._findComponentData(compId);
        this.state.notebookItems.unshift({
            componentId: comp.component_id || comp.id,
            name: comp.name || comp.component_id || comp.id,
            category: comp.category || "",
            version: comp.version || "1.0.0",
            status: comp.status || "stable",
            templateRef: comp.template_ref || comp.component_id || comp.id,
            copiedTypes: copyType ? [copyType] : [],
            firstCopiedAt: Date.now(),
            lastCopiedAt: Date.now(),
            pinned: false,
        });
    }

    onNotebookCopy(compId, copyType) {
        this.addNotebookItem(compId, copyType);
        this.onCopiedAiPrompt(compId);
    }

    removeFromNotebook(componentId) {
        const idx = this.state.notebookItems.findIndex(
            item => item.componentId === componentId
        );
        if (idx >= 0) {
            this.state.notebookItems.splice(idx, 1);
        }
    }

    clearNotebook() {
        this.state.notebookItems.splice(0, this.state.notebookItems.length);
        this.notification.add("Notebook cleared", { type: "info" });
    }

    togglePinNotebook(componentId) {
        const item = this.state.notebookItems.find(i => i.componentId === componentId);
        if (item) {
            item.pinned = !item.pinned;
            if (item.pinned) {
                const idx = this.state.notebookItems.indexOf(item);
                this.state.notebookItems.splice(idx, 1);
                this.state.notebookItems.unshift(item);
            }
        }
    }

    jumpToComponent(componentId) {
        const comp = this._findComponentData(componentId);
        if (comp) {
            this.state.selectedComponent = comp;
            this.state.inspectorVisible = true;
        }
    }

    async exitWorkspace() {
        document.body.classList.remove('core_ui_workspace_active');
        this.action.doAction({
            type: 'ir.actions.act_window_close',
        });
    }
}

registry.category("actions").add("core_ui.gallery", CoreUIGalleryOnly);
