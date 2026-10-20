/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { Interaction } from "@web/public/interaction";

export class AbStorefrontTestimonials extends Interaction {
    static selector = ".ab-storefront-testimonials";

    dynamicContent = {
        ".ab-storefront-testimonial-previous": { "t-on-click": () => this.move(-1) },
        ".ab-storefront-testimonial-next": { "t-on-click": () => this.move(1) },
        ".ab-storefront-testimonial-rail": { "t-on-keydown": this.onKeydown },
        ".ab-storefront-testimonial-media": { "t-on-click": this.openReview },
        ".ab-storefront-testimonial-close": { "t-on-click": this.closeReview },
    };

    start() {
        this.rail = this.el.querySelector(".ab-storefront-testimonial-rail");
        this.cards = [...this.rail.querySelectorAll(".ab-storefront-testimonial-card")];
        this.controls = this.el.querySelector(".ab-storefront-testimonial-controls");
        this.previous = this.controls.querySelector("button:first-child");
        this.next = this.controls.querySelector("button:last-child");
        this.position = this.el.querySelector(".ab-storefront-testimonial-position");
        this.dialog = this.el.querySelector("dialog");
        this.addListener(this.rail, "scroll", () => {
            clearTimeout(this.scrollTimer);
            this.scrollTimer = setTimeout(() => {
                this.targetIndex = null;
                this.updatePosition();
            }, 140);
        }, { passive: true });
        this.addListener(this.dialog, "close", this.restoreFocus);
        this.addListener(this.dialog, "click", (event) => {
            if (event.target !== this.dialog) {
                return;
            }
            const bounds = this.dialog.getBoundingClientRect();
            if (event.clientX < bounds.left || event.clientX > bounds.right
                || event.clientY < bounds.top || event.clientY > bounds.bottom) {
                this.closeReview();
            }
        });
        this.resizeObserver = new ResizeObserver(() => {
            this.targetIndex = null;
            this.updatePosition();
        });
        this.resizeObserver.observe(this.rail);
        this.updatePosition();
    }

    getGeometry() {
        const rtl = getComputedStyle(this.rail).direction === "rtl";
        const bounds = this.rail.getBoundingClientRect();
        const cards = this.cards.map((card) => card.getBoundingClientRect());
        const offsets = cards.map((card) => rtl ? bounds.right - card.right : card.left - bounds.left);
        const index = offsets.reduce((nearest, offset, candidate) =>
            Math.abs(offset) < Math.abs(offsets[nearest]) ? candidate : nearest, 0);
        return { rtl, bounds, cards, offsets, index };
    }

    updatePosition() {
        if (!this.cards.length) {
            this.controls.hidden = true;
            return;
        }
        const { rtl, bounds, cards, index } = this.getGeometry();
        const overflow = this.rail.scrollWidth > this.rail.clientWidth + 2;
        this.controls.hidden = !overflow;
        this.previous.disabled = !overflow || (rtl ? cards[0].right <= bounds.right + 2 : cards[0].left >= bounds.left - 2);
        const last = cards.at(-1);
        this.next.disabled = !overflow || (rtl ? last.left >= bounds.left - 2 : last.right <= bounds.right + 2);
        const currentReview = this.next.disabled ? this.cards.length : index + 1;
        this.position.textContent = overflow ? _t("Review %s of %s", currentReview, this.cards.length) : "";
    }

    move(step) {
        const { rtl, offsets, index } = this.getGeometry();
        const target = Math.max(0, Math.min(this.cards.length - 1, (this.targetIndex ?? index) + step));
        this.scrollToReview(target, rtl, offsets);
    }

    scrollToReview(index, rtl, offsets) {
        this.targetIndex = index;
        this.rail.scrollBy({
            left: offsets[index] * (rtl ? -1 : 1),
            behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth",
        });
    }

    onKeydown(event) {
        if (event.target !== this.rail || event.altKey || event.ctrlKey || event.metaKey) {
            return;
        }
        const { rtl, offsets } = this.getGeometry();
        if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
            event.preventDefault();
            this.move((event.key === "ArrowRight") !== rtl ? 1 : -1);
        } else if (event.key === "Home" || event.key === "End") {
            event.preventDefault();
            this.scrollToReview(event.key === "Home" ? 0 : this.cards.length - 1, rtl, offsets);
        }
    }

    openReview(event) {
        if (event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey
            || typeof this.dialog.showModal !== "function") {
            return;
        }
        event.preventDefault();
        this.opener = event.currentTarget;
        const image = this.dialog.querySelector("img");
        image.src = this.opener.href;
        image.alt = this.opener.querySelector("img").alt;
        const source = this.opener.closest("article").querySelector(".ab-storefront-testimonial-link");
        const original = this.dialog.querySelector("a");
        original.hidden = !source;
        if (source) {
            original.href = source.href;
            original.textContent = source.textContent.trim();
        }
        this.dialog.showModal();
    }

    closeReview() {
        this.dialog.close();
    }

    restoreFocus() {
        this.dialog.querySelector("img").removeAttribute("src");
        this.opener?.focus({ preventScroll: true });
        this.opener = null;
    }

    destroy() {
        clearTimeout(this.scrollTimer);
        this.resizeObserver?.disconnect();
        if (this.dialog?.open) {
            this.dialog.close();
        }
        this.controls.hidden = true;
        this.position.textContent = "";
        super.destroy();
    }
}

registry.category("public.interactions").add("ab_ecommerce_storefront.customer_testimonials", AbStorefrontTestimonials);
