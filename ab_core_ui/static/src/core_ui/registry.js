/** @odoo-module **/

const _registry = new Map();
let _validated = false;

export function registerComponent(id, meta) {
    if (!id) {
        throw new Error(`[CoreUI Registry] Component ID is required`);
    }
    if (_registry.has(id)) {
        throw new Error(
            `[CoreUI Registry] Component "${id}" is already registered.` +
            ` Duplicate registration detected. Each component must have a unique ID.`
        );
    }
    if (!meta.component) {
        throw new Error(`[CoreUI Registry] Component "${id}" missing required field: component`);
    }
    if (!meta.name) {
        throw new Error(`[CoreUI Registry] Component "${id}" missing required field: name`);
    }
    if (!meta.category) {
        throw new Error(`[CoreUI Registry] Component "${id}" missing required field: category`);
    }

    _registry.set(id, {
        component_id: id,
        component: meta.component,
        name: meta.name,
        category: meta.category,
        version: meta.version || '1.0.0',
        status: meta.status || 'stable',
        description: meta.description || '',
        keywords: meta.keywords || '',
        templateRef: meta.templateRef || id,
        propsSchema: meta.propsSchema || {},
        demoData: meta.demoData || (() => ({})),
    });

    if (typeof window !== 'undefined' && window.coreUIRegistryDebug) {
        console.log(`[CoreUI Registry] Registered: ${id}`);
    }
}

export function unregisterComponent(id) {
    _registry.delete(id);
}

export function getComponent(id) {
    return _registry.get(id) || null;
}

export function getAllComponents() {
    return Array.from(_registry.values());
}

export function getByCategory(category) {
    return getAllComponents().filter(c => c.category === category);
}

export function search(query) {
    if (!query) return getAllComponents();
    const q = query.toLowerCase();
    return getAllComponents().filter(c =>
        c.name.toLowerCase().includes(q) ||
        c.component_id.toLowerCase().includes(q) ||
        c.description.toLowerCase().includes(q) ||
        c.keywords.toLowerCase().includes(q)
    );
}

export function validateRegistry() {
    if (_validated) return;
    const errors = [];

    for (const [id, entry] of _registry) {
        if (!entry.component) {
            errors.push(`Missing component class: ${id}`);
        }
        if (typeof entry.demoData !== 'function') {
            errors.push(`demoData must be a function: ${id}`);
        }
    }

    if (errors.length) {
        console.error('[CoreUI Registry] ❌ Validation failed:');
        for (const err of errors) {
            console.error(`  ✗ ${err}`);
        }
        throw new Error(
            `[CoreUI Registry] ${errors.length} validation error(s). Fix before continuing.\n` +
            errors.join('\n')
        );
    }

    _validated = true;
    console.info(`[CoreUI Registry] ✅ ${_registry.size} components registered. Validation passed.`);
}
