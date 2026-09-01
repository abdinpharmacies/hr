import { registry } from "@web/core/registry";
import { Interaction } from "@web/public/interaction";

export class AbStorefrontHeroCarousel extends Interaction {
    static selector = "#abStorefrontHeroCarousel";

    setup() {
        this.dragStartX = 0;
        this.dragStartY = 0;
        this.dragging = false;
        this.suppressClick = false;
        this.onPointerDown = this.onPointerDown.bind(this);
        this.onPointerMove = this.onPointerMove.bind(this);
        this.onPointerUp = this.onPointerUp.bind(this);
        this.onClick = this.onClick.bind(this);
    }

    start() {
        this.el.addEventListener("pointerdown", this.onPointerDown);
        this.el.addEventListener("pointermove", this.onPointerMove);
        this.el.addEventListener("pointerup", this.onPointerUp);
        this.el.addEventListener("pointercancel", this.onPointerUp);
        this.el.addEventListener("click", this.onClick, true);
    }

    destroy() {
        this.el.removeEventListener("pointerdown", this.onPointerDown);
        this.el.removeEventListener("pointermove", this.onPointerMove);
        this.el.removeEventListener("pointerup", this.onPointerUp);
        this.el.removeEventListener("pointercancel", this.onPointerUp);
        this.el.removeEventListener("click", this.onClick, true);
    }

    onPointerDown(ev) {
        if (ev.pointerType === "mouse" && ev.button !== 0) {
            return;
        }
        if (this.isInteractiveTarget(ev.target)) {
            return;
        }
        this.dragging = true;
        this.suppressClick = false;
        this.dragStartX = ev.clientX;
        this.dragStartY = ev.clientY;
        this.el.setPointerCapture?.(ev.pointerId);
    }

    onPointerMove(ev) {
        if (!this.dragging) {
            return;
        }
        const deltaX = ev.clientX - this.dragStartX;
        const deltaY = ev.clientY - this.dragStartY;
        if (Math.abs(deltaX) > 12 && Math.abs(deltaX) > Math.abs(deltaY)) {
            ev.preventDefault();
        }
    }

    onPointerUp(ev) {
        if (!this.dragging) {
            return;
        }
        this.dragging = false;
        this.el.releasePointerCapture?.(ev.pointerId);

        const deltaX = ev.clientX - this.dragStartX;
        const deltaY = ev.clientY - this.dragStartY;
        if (Math.abs(deltaX) < 48 || Math.abs(deltaX) <= Math.abs(deltaY)) {
            return;
        }

        const Carousel = window.Carousel || window.bootstrap?.Carousel;
        const carousel = Carousel?.getOrCreateInstance(this.el);
        if (!carousel) {
            return;
        }
        this.suppressClick = true;
        setTimeout(() => {
            this.suppressClick = false;
        });
        deltaX < 0 ? carousel.next() : carousel.prev();
    }

    onClick(ev) {
        if (!this.suppressClick || this.isInteractiveTarget(ev.target)) {
            return;
        }
        this.suppressClick = false;
        ev.preventDefault();
        ev.stopPropagation();
    }

    isInteractiveTarget(target) {
        return !!target.closest(
            "a, button, input, textarea, select, .carousel-control-prev, .carousel-control-next, .carousel-indicators"
        );
    }
}

registry
    .category("public.interactions")
    .add("ab_ecommerce_storefront.hero_carousel", AbStorefrontHeroCarousel);
