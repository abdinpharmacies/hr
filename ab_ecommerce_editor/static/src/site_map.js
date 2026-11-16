/** @odoo-module **/

import { Component, useState } from "@odoo/owl";

export class EditorSiteMap extends Component {
    static template = "ab_ecommerce_editor.SiteMap";
    static props = { nodes: Array, onOpen: Function, onBack: Function };

    setup() {
        this.state = useState({ source: "/", links: {}, loaded: {}, failed: {} });
    }

    get nodes() {
        return this.props.nodes.map((node, index) => ({
            ...node,
            x: index === 0 ? 420 : 60 + ((index - 1) % 3) * 360,
            y: index === 0 ? 30 : 390 + Math.floor((index - 1) / 3) * 360,
        }));
    }

    get height() { return 420 + Math.ceil((this.nodes.length - 1) / 3) * 360; }

    get connections() {
        const source = this.nodes.find((node) => node.url === this.state.source);
        if (!source) return [];
        return (this.state.links[source.url] || []).map((url) => {
            const target = this.nodes.find((node) => node.url === url);
            const x1 = source.x + 150;
            const y1 = source.y + 282;
            const x2 = target.x + 150;
            const y2 = target.y - 8;
            const bend = Math.max(60, Math.abs(y2 - y1) / 2);
            return { url, path: `M ${x1} ${y1} C ${x1} ${y1 + bend}, ${x2} ${y2 - bend}, ${x2} ${y2}` };
        });
    }

    outgoing(node) {
        return this.nodes.filter((target) => (this.state.links[node.url] || []).includes(target.url));
    }

    previewLoaded(node, event) {
        const frame = event.currentTarget;
        try {
            const doc = frame.contentDocument;
            const location = new URL(frame.contentWindow.location.href);
            if (location.href === "about:blank") return;
            if (!doc?.body || location.origin !== window.location.origin || !doc.querySelector("#wrapwrap")) {
                this.state.failed[node.url] = true;
                return;
            }
            const normalize = (path) => path.replace(/^\/(?:ar|ar_001|en|en_US)(?=\/|$)/, "").replace(/\/$/, "") || "/";
            const links = new Set();
            for (const anchor of doc.querySelectorAll("a[href]")) {
                const url = new URL(anchor.getAttribute("href"), location);
                if (url.origin !== location.origin) continue;
                const normalized = normalize(url.pathname);
                const path = normalized === "/shop/category" && url.searchParams.get("deal") === "discount" ? "/shop/offers" : { "/offers": "/shop/offers", "/categories": "/shop/category" }[normalized] || normalized;
                if (path !== node.url && this.props.nodes.some((target) => target.url === path)) links.add(path);
            }
            this.state.links[node.url] = [...links];
            this.state.loaded[node.url] = true;
            this.state.failed[node.url] = false;
            const style = doc.createElement("style");
            style.textContent = "html,body{overflow:hidden!important}header.o_main_navbar,.o_frontend_to_backend_nav{display:none!important}*,*::before,*::after{animation:none!important;transition:none!important}";
            doc.head.appendChild(style);
        } catch {
            this.state.failed[node.url] = true;
        }
    }
}
