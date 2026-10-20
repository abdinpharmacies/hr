/** @odoo-module **/

export const CATALOG_CACHE_KEY = "ab_storefront_catalog_v1";
const MAX_ENTRIES = 160;
const MAX_CHARACTERS = 256000;

export class CatalogCache {
    constructor(storage, scope) {
        this.storage = storage;
        this.scope = scope;
        this.entries = new Map();
        try {
            const saved = JSON.parse(storage.getItem(CATALOG_CACHE_KEY) || "null");
            if (saved?.scope === scope && Array.isArray(saved.entries)) {
                for (const [key, value] of saved.entries.slice(-MAX_ENTRIES)) {
                    if (/^[a-f0-9]{24}$/.test(key) && typeof value === "string") {
                        this.entries.set(key, value);
                    }
                }
            }
        } catch {
            this.entries.clear();
        }
        this.save();
    }

    get(key) {
        const value = this.entries.get(key);
        if (value !== undefined) {
            this.entries.delete(key);
            this.entries.set(key, value);
        }
        return value;
    }

    put(key, value) {
        if (!/^[a-f0-9]{24}$/.test(key) || typeof value !== "string" || value.length > MAX_CHARACTERS) {
            return;
        }
        this.entries.delete(key);
        this.entries.set(key, value);
        this.save();
    }

    known() {
        return [...this.entries.keys()].join(",");
    }

    save() {
        let payload;
        while (true) {
            payload = JSON.stringify({ scope: this.scope, entries: [...this.entries] });
            if (!this.entries.size || (this.entries.size <= MAX_ENTRIES && payload.length <= MAX_CHARACTERS)) {
                break;
            }
            this.entries.delete(this.entries.keys().next().value);
        }
        try {
            this.storage.setItem(CATALOG_CACHE_KEY, payload);
        } catch {
            try {
                this.storage.removeItem(CATALOG_CACHE_KEY);
            } catch {
                return;
            }
        }
    }
}
