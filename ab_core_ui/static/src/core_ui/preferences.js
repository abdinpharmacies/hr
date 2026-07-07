/** @odoo-module **/

const STORAGE_KEY = 'core_ui_workspace_preferences';

const DEFAULTS = {
    theme: 'light',
    designProfile: 'default',
    palette: 'default',
    typography: 'default',
    spacing: 'default',
    radius: 'default',
    shadow: 'default',
    border: 'default',
    gradient: 'default',
    motion: 'default',
    hoverEffects: 'default',
    previewMode: 'grid',
    lastOpenedSection: null,
    sidebarCollapsed: false,
    notebookCollapsed: true,
    workspaceLayout: 'default',
};

function fullKey(key) {
    return `${STORAGE_KEY}.${key}`;
}

export function loadPref(key) {
    try {
        const raw = localStorage.getItem(fullKey(key));
        if (raw === null) return DEFAULTS[key];
        return JSON.parse(raw);
    } catch {
        return DEFAULTS[key];
    }
}

export function savePref(key, value) {
    try {
        localStorage.setItem(fullKey(key), JSON.stringify(value));
    } catch (e) {
        console.warn('[CoreUI] Failed to save preference:', key, e);
    }
}

export function loadAll() {
    const result = {};
    for (const key of Object.keys(DEFAULTS)) {
        result[key] = loadPref(key);
    }
    return result;
}

export function saveAll(prefs) {
    for (const [key, value] of Object.entries(prefs)) {
        if (key in DEFAULTS) {
            savePref(key, value);
        }
    }
}

export function resetAll() {
    for (const key of Object.keys(DEFAULTS)) {
        try {
            localStorage.removeItem(fullKey(key));
        } catch (_) {}
    }
}

export function notifyPrefsChanged(prefs) {
    document.dispatchEvent(new CustomEvent('core_ui_prefs_changed', { detail: prefs }));
}
