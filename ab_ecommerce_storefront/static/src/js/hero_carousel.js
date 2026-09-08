/** @odoo-module ignore **/
(function () {
    "use strict";

    const SELECTOR = "#abStorefrontHeroCarousel";
    const SWIPE_THRESHOLD = 45;
    const HORIZONTAL_RATIO = 1.15;
    const SLIDE_LOCK_TIMEOUT = 900;
    const FULL_SLIDE_LINK_SELECTOR = ".ab-storefront-banner-link";

    function isInteractiveTarget(target) {
        const interactiveTarget = target.closest(
            "a, button, input, textarea, select, .carousel-control-prev, .carousel-control-next, .carousel-indicators"
        );
        return !!interactiveTarget && !interactiveTarget.matches(FULL_SLIDE_LINK_SELECTOR);
    }

    function getCarouselInstance(el) {
        const Carousel = window.bootstrap?.Carousel || window.Carousel;
        if (!Carousel) {
            return null;
        }
        return Carousel.getOrCreateInstance(el, { touch: false, interval: 6500, ride: "carousel" });
    }

    function isRTL() {
        return document.documentElement.dir === "rtl"
            || document.documentElement.lang?.toLowerCase().startsWith("ar");
    }

    function getContainedImageBox(container, image) {
        const box = {
            left: 0,
            top: 0,
            width: container.clientWidth,
            height: container.clientHeight,
        };
        if (!box.width || !box.height || !image.naturalWidth || !image.naturalHeight) {
            return box;
        }
        const containerRatio = box.width / box.height;
        const imageRatio = image.naturalWidth / image.naturalHeight;
        if (imageRatio > containerRatio) {
            const height = box.width / imageRatio;
            return {
                left: 0,
                top: (box.height - height) / 2,
                width: box.width,
                height,
            };
        }
        const width = box.height * imageRatio;
        return {
            left: (box.width - width) / 2,
            top: 0,
            width,
            height: box.height,
        };
    }

    function positionSlideCTA(slide) {
        const image = slide.querySelector(".ab-storefront-banner-art");
        const cta = slide.querySelector(".ab-storefront-banner-cta-layer");
        if (!image || !cta) {
            return;
        }
        const imageBox = getContainedImageBox(slide, image);
        if (!imageBox.width || !imageBox.height) {
            return;
        }
        const x = Math.min(100, Math.max(0, Number.parseFloat(cta.dataset.abPositionX) || 0));
        const y = Math.min(100, Math.max(0, Number.parseFloat(cta.dataset.abPositionY) || 0));
        cta.style.left = `${imageBox.left + imageBox.width * x / 100}px`;
        cta.style.right = "auto";
        cta.style.top = `${imageBox.top + imageBox.height * y / 100}px`;
        cta.style.transform = "translate(-50%, -50%)";
    }

    function setupCTAPlacement(el) {
        const slides = Array.from(el.querySelectorAll(".carousel-item"));
        const positionVisibleSlides = () => slides.forEach(positionSlideCTA);
        let positionFrame = null;
        const schedulePlacement = () => {
            if (positionFrame !== null) {
                window.cancelAnimationFrame(positionFrame);
            }
            positionFrame = window.requestAnimationFrame(() => {
                positionFrame = window.requestAnimationFrame(() => {
                    positionFrame = null;
                    positionVisibleSlides();
                });
            });
        };
        slides.forEach((slide) => {
            const image = slide.querySelector(".ab-storefront-banner-art");
            image?.addEventListener("load", schedulePlacement);
        });
        el.addEventListener("slide.bs.carousel", (ev) => {
            window.requestAnimationFrame(() => positionSlideCTA(ev.relatedTarget));
        });
        el.addEventListener("slid.bs.carousel", schedulePlacement);
        if (window.ResizeObserver) {
            const resizeObserver = new ResizeObserver(schedulePlacement);
            slides.forEach((slide) => resizeObserver.observe(slide));
        }
        window.addEventListener("resize", schedulePlacement);
        schedulePlacement();
    }

    function startCarousel(el) {
        if (!el || el.dataset.abSwipeReady === "1") {
            return;
        }
        el.dataset.abSwipeReady = "1";
        setupCTAPlacement(el);
        if (el.querySelectorAll(".carousel-item").length < 2) {
            return;
        }

        let startX = 0;
        let startY = 0;
        let activePointerId = null;
        let dragging = false;
        let horizontalDrag = false;
        let sliding = false;
        let unlockTimer = null;
        let lastPointerDownAt = 0;

        function unlock() {
            sliding = false;
            window.clearTimeout(unlockTimer);
            unlockTimer = null;
        }

        function lock() {
            sliding = true;
            window.clearTimeout(unlockTimer);
            unlockTimer = window.setTimeout(unlock, SLIDE_LOCK_TIMEOUT);
        }

        function beginDrag(clientX, clientY, pointerId = null) {
            dragging = true;
            horizontalDrag = false;
            activePointerId = pointerId;
            startX = clientX;
            startY = clientY;
            el.classList.add("is-dragging");
        }

        function trackDrag(clientX, clientY, ev) {
            if (!dragging) {
                return;
            }
            const deltaX = clientX - startX;
            const deltaY = clientY - startY;
            if (Math.abs(deltaX) > 10 && Math.abs(deltaX) > Math.abs(deltaY) * HORIZONTAL_RATIO) {
                horizontalDrag = true;
                ev?.preventDefault?.();
            }
        }

        function endDrag(clientX, clientY, ev) {
            if (!dragging) {
                return;
            }
            dragging = false;
            activePointerId = null;
            el.classList.remove("is-dragging");
            if (!navigateByDelta(clientX - startX, clientY - startY)) {
                horizontalDrag = false;
                return;
            }
            ev?.preventDefault?.();
            window.setTimeout(() => {
                horizontalDrag = false;
            }, 0);
        }

        function cancelDrag() {
            dragging = false;
            horizontalDrag = false;
            activePointerId = null;
            el.classList.remove("is-dragging");
        }

        function onPointerDown(ev) {
            if (isInteractiveTarget(ev.target) || (ev.pointerType === "mouse" && ev.button !== 0)) {
                return;
            }
            lastPointerDownAt = Date.now();
            beginDrag(ev.clientX, ev.clientY, ev.pointerId);
            try {
                el.setPointerCapture?.(ev.pointerId);
            } catch {
                // Drag still works through document-level listeners.
            }
        }

        function onPointerMove(ev) {
            if (!dragging || activePointerId !== ev.pointerId) {
                return;
            }
            trackDrag(ev.clientX, ev.clientY, ev);
        }

        function onPointerUp(ev) {
            if (!dragging || activePointerId !== ev.pointerId) {
                return;
            }
            try {
                el.releasePointerCapture?.(ev.pointerId);
            } catch {
                // Capture may not have been granted.
            }
            endDrag(ev.clientX, ev.clientY, ev);
        }

        function onMouseDown(ev) {
            if (Date.now() - lastPointerDownAt < 400 || ev.button !== 0 || isInteractiveTarget(ev.target)) {
                return;
            }
            beginDrag(ev.clientX, ev.clientY);
        }

        function onMouseMove(ev) {
            if (activePointerId !== null) {
                return;
            }
            trackDrag(ev.clientX, ev.clientY, ev);
        }

        function onMouseUp(ev) {
            if (activePointerId !== null) {
                return;
            }
            endDrag(ev.clientX, ev.clientY, ev);
        }

        function onTouchStart(ev) {
            if (Date.now() - lastPointerDownAt < 400) {
                return;
            }
            if (isInteractiveTarget(ev.target) || ev.touches.length !== 1) {
                return;
            }
            beginDrag(ev.touches[0].clientX, ev.touches[0].clientY);
        }

        function onTouchMove(ev) {
            if (!dragging || ev.touches.length !== 1) {
                return;
            }
            const deltaX = ev.touches[0].clientX - startX;
            const deltaY = ev.touches[0].clientY - startY;
            if (Math.abs(deltaY) > Math.abs(deltaX)) {
                return;
            }
            trackDrag(ev.touches[0].clientX, ev.touches[0].clientY, ev);
        }

        function onTouchEnd(ev) {
            const touch = ev.changedTouches[0];
            if (!touch) {
                cancelDrag();
                return;
            }
            endDrag(touch.clientX, touch.clientY, ev);
        }

        function onWheel(ev) {
            if (sliding || isInteractiveTarget(ev.target)) {
                return;
            }
            if (Math.abs(ev.deltaX) < SWIPE_THRESHOLD || Math.abs(ev.deltaX) <= Math.abs(ev.deltaY) * HORIZONTAL_RATIO) {
                return;
            }
            ev.preventDefault();
            navigateByDelta(ev.deltaX, ev.deltaY);
        }

        function navigateByDelta(deltaX, deltaY) {
            if (
                sliding ||
                Math.abs(deltaX) < SWIPE_THRESHOLD ||
                Math.abs(deltaX) <= Math.abs(deltaY) * HORIZONTAL_RATIO
            ) {
                return false;
            }
            const carousel = getCarouselInstance(el);
            if (!carousel) {
                return false;
            }
            lock();
            const shouldMoveNext = isRTL() ? deltaX > 0 : deltaX < 0;
            if (shouldMoveNext) {
                carousel.next();
            } else {
                carousel.prev();
            }
            return true;
        }

        function onClick(ev) {
            if (!horizontalDrag || isInteractiveTarget(ev.target)) {
                return;
            }
            horizontalDrag = false;
            ev.preventDefault();
            ev.stopPropagation();
        }

        el.addEventListener("pointerdown", onPointerDown);
        el.addEventListener("mousedown", onMouseDown);
        el.addEventListener("touchstart", onTouchStart, { passive: true });
        el.addEventListener("touchmove", onTouchMove, { passive: false });
        el.addEventListener("touchend", onTouchEnd, { passive: false });
        el.addEventListener("touchcancel", cancelDrag, { passive: true });
        el.addEventListener("wheel", onWheel, { passive: false });
        el.addEventListener("lostpointercapture", cancelDrag);
        el.addEventListener("slid.bs.carousel", unlock);
        el.addEventListener("click", onClick, true);
        document.addEventListener("pointermove", onPointerMove);
        document.addEventListener("pointerup", onPointerUp);
        document.addEventListener("pointercancel", cancelDrag);
        document.addEventListener("mousemove", onMouseMove);
        document.addEventListener("mouseup", onMouseUp);
        getCarouselInstance(el);
    }

    function start() {
        document.querySelectorAll(SELECTOR).forEach(startCarousel);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", start, { once: true });
    } else {
        start();
    }
}());
