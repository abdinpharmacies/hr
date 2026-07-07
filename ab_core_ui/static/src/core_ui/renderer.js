/** @odoo-module **/
import { App } from "@odoo/owl";
import { getTemplate } from "@web/core/templates";

const activeMounts = new WeakMap();

export async function renderComponent(container, componentMeta, props) {
    destroyComponent(container);

    const { component } = componentMeta;
    const app = new App(component, {
        props: props || componentMeta.demoData(),
        getTemplate,
    });
    await app.mount(container);
    activeMounts.set(container, app);
    return app;
}

export function destroyComponent(container) {
    const existing = activeMounts.get(container);
    if (existing) {
        existing.destroy();
        activeMounts.delete(container);
    }
}
