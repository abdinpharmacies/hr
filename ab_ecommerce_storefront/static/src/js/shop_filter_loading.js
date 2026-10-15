/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Interaction } from "@web/public/interaction";

export class AbStorefrontFilterLoading extends Interaction {
    static selector = ".ab-storefront-shop";

    start() {
        this.grid = this.el.querySelector("#products_grid");
        if (!this.grid) {
            return;
        }
        this.products = this.grid.querySelector(".o_wsale_products_grid_table_wrapper");
        this.originalBusy = this.grid.getAttribute("aria-busy");
        this.originalInert = this.products?.hasAttribute("inert");
        this.onClick = this.onClick.bind(this);
        this.reset = this.reset.bind(this);
        document.addEventListener("click", this.onClick, true);
        window.addEventListener("pageshow", this.reset);
        if (this.products) {
            this.observer = new MutationObserver(() => {
                if (this.products.classList.contains("opacity-50")) {
                    this.showLoading();
                }
            });
            this.observer.observe(this.products, { attributes: true, attributeFilter: ["class"] });
        }
    }

    onClick(event) {
        if (!(event.target instanceof Element) || event.button !== 0
            || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
            return;
        }
        const mobileDialog = event.target.closest("#o_wsale_offcanvas.ab-storefront-filter-dialog");
        if (mobileDialog && window.matchMedia("(max-width: 991.98px)").matches) {
            if (event.defaultPrevented && event.target.closest(".ab-storefront-filter-apply")) {
                this.showLoading();
            }
            return;
        }
        const link = event.target.closest(
            "#products_grid_before a[href], #o_wsale_offcanvas a[href]"
        );
        if (!link || event.defaultPrevented || link.hasAttribute("download")
            || (link.target && link.target !== "_self")
            || link.getAttribute("aria-disabled") === "true"
            || link.classList.contains("disabled")) {
            return;
        }
        const target = new URL(link.href, window.location.href);
        const current = new URL(window.location.href);
        if (target.origin !== current.origin || !/\/shop(?:\/|$)/.test(target.pathname)
            || (target.pathname === current.pathname && target.search === current.search)) {
            return;
        }
        this.showLoading();
    }

    showLoading() {
        if (this.loading) {
            return;
        }
        this.loading = true;
        this.grid.classList.add("ab-storefront-results-pending");
        this.grid.setAttribute("aria-busy", "true");
        this.products?.setAttribute("inert", "");
        this.indicatorTimer = setTimeout(() => {
            this.grid.classList.add("ab-storefront-results-loading");
        }, 180);
        this.recoveryTimer = setTimeout(this.reset, 30000);
    }

    reset() {
        if (!this.grid || !this.loading) {
            return;
        }
        clearTimeout(this.indicatorTimer);
        clearTimeout(this.recoveryTimer);
        this.loading = false;
        this.grid.classList.remove("ab-storefront-results-pending", "ab-storefront-results-loading");
        if (this.originalBusy === null) {
            this.grid.removeAttribute("aria-busy");
        } else {
            this.grid.setAttribute("aria-busy", this.originalBusy);
        }
        if (!this.originalInert) {
            this.products?.removeAttribute("inert");
        }
        this.products?.classList.remove("opacity-50");
    }

    destroy() {
        this.observer?.disconnect();
        document.removeEventListener("click", this.onClick, true);
        window.removeEventListener("pageshow", this.reset);
        this.reset();
    }
}

registry.category("public.interactions").add(
    "ab_ecommerce_storefront.filter_loading", AbStorefrontFilterLoading
);
