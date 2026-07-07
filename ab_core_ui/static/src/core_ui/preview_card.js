/** @odoo-module **/
import { Component, onMounted, onWillUnmount, onWillUpdateProps, useRef } from "@odoo/owl";
import { renderComponent, destroyComponent } from "./renderer";

export class CoreUIPreviewCard extends Component {
    static template = "core_ui.preview_card";
    static props = {
        componentMeta: { type: Object },
    };

    setup() {
        this.rootRef = useRef("root");
        onMounted(() => {
            renderComponent(this.rootRef.el, this.props.componentMeta);
        });
        onWillUpdateProps((nextProps) => {
            if (nextProps.componentMeta !== this.props.componentMeta) {
                renderComponent(this.rootRef.el, nextProps.componentMeta);
            }
        });
        onWillUnmount(() => {
            destroyComponent(this.rootRef.el);
        });
    }
}
