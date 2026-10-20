/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Interaction } from "@web/public/interaction";
import { CatalogCache } from "@ab_ecommerce_storefront/js/catalog_cache";

export class AbStorefrontCatalogNavigation extends Interaction {
    static selector = ".ab-storefront-shop";

    start() {
        this.grid = this.el.querySelector("#products_grid[data-ab-catalog-scope]");
        if (!this.grid || document.body.classList.contains("editor_enable")) {
            return;
        }
        this.scope = this.grid.dataset.abCatalogScope;
        this.pageUrl = location.href;
        let storage;
        try {
            storage = window.sessionStorage;
        } catch {
            storage = { getItem: () => null, setItem: () => {}, removeItem: () => {} };
        }
        this.cache = new CatalogCache(storage, this.scope);
        this.capture(this.grid);
        this.lastValidated = Date.now();
        this.lastRefreshAttempt = this.lastValidated;
        this.events = new AbortController();
        const options = { signal: this.events.signal };
        this.el.addEventListener("click", (event) => this.onClick(event), { ...options, capture: true });
        window.addEventListener("popstate", () => this.load(location.href), options);
        window.addEventListener("pageshow", (event) => {
            if (event.persisted) {
                this.load(location.href, false, true);
            }
        }, options);
        window.addEventListener("pagehide", () => this.cancelPending(), options);
        document.addEventListener("visibilitychange", () => {
            if (document.visibilityState === "visible") {
                this.refresh();
            }
        }, options);
        window.addEventListener("focus", () => this.refresh(), options);
        for (const event of ["ab-storefront-location:set", "ab-storefront:commerce-context-changed"]) {
            document.addEventListener(event, () => this.load(location.href), options);
        }
    }

    refresh() {
        if (document.visibilityState === "visible" && !this.pending
            && Date.now() - this.lastRefreshAttempt >= 30000) {
            this.load(location.href, false, true);
        }
    }

    resetLoading() {
        clearTimeout(this.indicatorTimer);
        if (!this.loadingState) {
            return;
        }
        const { grid, busy, inert, loading } = this.loadingState;
        if (busy === null) {
            grid.removeAttribute("aria-busy");
        } else {
            grid.setAttribute("aria-busy", busy);
        }
        if (!inert) {
            grid.removeAttribute("inert");
        }
        if (!loading) {
            grid.classList.remove("ab-storefront-results-loading");
        }
        this.loadingState = null;
    }

    cancelPending() {
        this.pending?.abort();
        this.pending = null;
        this.resetLoading();
    }

    capture(grid) {
        for (const part of grid.querySelectorAll("[data-ab-catalog-key]")) {
            if (!part.hasAttribute("data-ab-catalog-cached")) {
                this.cache.put(part.dataset.abCatalogKey, part.outerHTML);
            }
        }
    }

    onClick(event) {
        const link = event.target.closest?.("#o_wsale_pager a[href]");
        if (!link || event.defaultPrevented || event.button !== 0 || event.metaKey
            || event.ctrlKey || event.shiftKey || event.altKey || link.hasAttribute("download")
            || (link.target && link.target !== "_self") || link.closest(".disabled")) {
            return;
        }
        event.preventDefault();
        event.stopPropagation();
        this.load(link.href, true);
    }

    async load(href, push = false, background = false) {
        const url = new URL(href, location.href);
        if (url.origin !== location.origin) {
            return;
        }
        if (background && this.pending && this.pendingUrl === url.href) {
            return;
        }
        this.cancelPending();
        const selections = new Map();
        const pending = new AbortController();
        this.pending = pending;
        this.pendingUrl = url.href;
        this.lastRefreshAttempt = Date.now();
        this.loadingState = {
            grid: this.grid, busy: this.grid.getAttribute("aria-busy"),
            inert: this.grid.hasAttribute("inert"),
            loading: this.grid.classList.contains("ab-storefront-results-loading"),
        };
        this.grid.setAttribute("aria-busy", "true");
        if (!background) {
            this.grid.setAttribute("inert", "");
            this.indicatorTimer = setTimeout(() => {
                this.grid.classList.add("ab-storefront-results-loading");
            }, 180);
        }
        const timeout = setTimeout(() => pending.abort("timeout"), 20000);
        try {
            const response = await fetch(url, {
                credentials: "same-origin", cache: "no-store", signal: pending.signal,
                headers: {
                    "X-Ab-Catalog-Page": "1", "X-Ab-Catalog-Scope": this.scope,
                    "X-Ab-Catalog-Known": this.cache.known(),
                },
            });
            if (!response.ok || response.redirected || !response.headers.get("Content-Type")?.includes("application/json")) {
                throw new Error("Catalog navigation requires a full page");
            }
            const data = await response.json();
            if (data.reload || data.scope !== this.scope) {
                background = false;
                throw new Error("Catalog context changed");
            }
            const parsed = new DOMParser().parseFromString(data.grid, "text/html");
            const next = parsed.querySelector("#products_grid");
            if (!next || next.dataset.abCatalogScope !== this.scope) {
                throw new Error("Invalid catalog page");
            }
            for (const part of next.querySelectorAll("[data-ab-catalog-cached]")) {
                const stored = this.cache.get(part.dataset.abCatalogKey);
                if (!stored) {
                    throw new Error("Catalog cache miss");
                }
                const fragment = new DOMParser().parseFromString(stored, "text/html").body.firstElementChild;
                if (!fragment || fragment.dataset.abCatalogKey !== part.dataset.abCatalogKey
                    || fragment.dataset.abCatalogStatic !== part.dataset.abCatalogStatic) {
                    throw new Error("Invalid catalog cache entry");
                }
                part.replaceWith(fragment);
            }
            if (pending.signal.aborted) {
                return;
            }
            if (!push && url.href === this.pageUrl) {
                for (const card of this.grid.querySelectorAll(".ab-storefront-product-card")) {
                    selections.set(card.querySelector("[name='product_id']")?.value, {
                        quantity: card.querySelector("[name='add_qty']")?.value,
                        unit: card.querySelector(".ab-storefront-unit-option.is-selected")?.dataset.unitKey,
                    });
                }
            }
            this.capture(next);
            if (push) {
                history.pushState({ ...history.state, abCatalog: true }, "", url);
            }
            this.lastValidated = Date.now();
            this.resetLoading();
            this.pending = null;
            const interactions = this.services["public.interactions"];
            interactions.stopInteractions(this.el);
            this.grid.replaceWith(next);
            await interactions.startInteractions(this.el);
            for (const card of next.querySelectorAll(".ab-storefront-product-card")) {
                const selection = selections.get(card.querySelector("[name='product_id']")?.value);
                if (!selection) {
                    continue;
                }
                const unit = [...card.querySelectorAll(".ab-storefront-unit-option")]
                    .find((option) => option.dataset.unitKey === selection.unit);
                unit?.click();
                const quantity = card.querySelector("[name='add_qty']");
                if (quantity && selection.quantity) {
                    quantity.value = selection.quantity;
                    quantity.dispatchEvent(new Event("change", { bubbles: true }));
                }
            }
            if (push) {
                next.scrollIntoView({ block: "start" });
            }
        } catch (error) {
            if (!background && (!pending.signal.aborted
                || (this.pending === pending && pending.signal.reason === "timeout"))) {
                this.resetLoading();
                location.assign(url.href);
            }
        } finally {
            clearTimeout(timeout);
            if (this.pending === pending) {
                this.resetLoading();
                this.pending = null;
            }
        }
    }

    destroy() {
        this.events?.abort();
        this.cancelPending();
    }
}

registry.category("public.interactions").add(
    "ab_ecommerce_storefront.catalog_navigation", AbStorefrontCatalogNavigation
);
