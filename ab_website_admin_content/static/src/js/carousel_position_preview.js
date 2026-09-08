/** @odoo-module ignore **/
(function () {
    "use strict";

    const PREVIEW_SELECTOR = ".ab_carousel_position_preview";
    const CTA_SELECTOR = ".ab_carousel_position_preview_cta";
    const RESIZE_HANDLE_SELECTOR = ".ab_carousel_position_resize_handle";
    const MIN_CTA_WIDTH = 40;
    const MAX_CTA_WIDTH = 520;

    function findInput(preview, fieldName) {
        const root = preview.closest(".o_form_sheet, .o_form_view") || document;
        return root.querySelector(`.o_field_widget[name="${fieldName}"] input, [name="${fieldName}"] input`);
    }

    function setInputValue(input, value) {
        if (!input) {
            return;
        }
        const stringValue = String(value);
        const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value")?.set;
        if (setter) {
            setter.call(input, stringValue);
        } else {
            input.value = stringValue;
        }
        input.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertReplacementText", data: stringValue }));
        input.dispatchEvent(new Event("change", { bubbles: true }));
        input.dispatchEvent(new Event("focusout", { bubbles: true }));
    }

    function getContentRect(element) {
        const rect = element.getBoundingClientRect();
        return {
            left: rect.left + element.clientLeft,
            top: rect.top + element.clientTop,
            width: element.clientWidth,
            height: element.clientHeight,
        };
    }

    function getContainedImageBox(preview, image) {
        const box = {
            left: 0,
            top: 0,
            width: preview.clientWidth,
            height: preview.clientHeight,
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

    function attachPreview(preview) {
        const cta = preview.querySelector(CTA_SELECTOR);
        const image = preview.querySelector(":scope > img");
        if (!cta || !image || cta.dataset.abPositionReady === "1") {
            return;
        }
        cta.dataset.abPositionReady = "1";
        let dragging = false;
        let pointerId = null;
        let rafId = null;
        let pendingEvent = null;
        let grabOffsetX = 0;
        let grabOffsetY = 0;
        let currentX = Number.parseFloat(cta.dataset.abPositionX) || 0;
        let currentY = Number.parseFloat(cta.dataset.abPositionY) || 0;
        let currentWidth = Number.parseFloat(cta.dataset.abWidth) || 220;
        let interactionMode = "move";
        let resizeStartX = 0;
        let resizeStartWidth = currentWidth;
        let resizeDirection = 1;

        function renderPosition() {
            const imageBox = getContainedImageBox(preview, image);
            if (!imageBox.width || !imageBox.height) {
                return;
            }
            cta.style.left = `${imageBox.left + imageBox.width * currentX / 100}px`;
            cta.style.right = "auto";
            cta.style.top = `${imageBox.top + imageBox.height * currentY / 100}px`;
            cta.style.setProperty("--ab-preview-cta-width", `${currentWidth}px`);
            cta.style.transform = "translate(-50%, -50%)";
        }

        function updateFromPointer(ev) {
            const previewRect = getContentRect(preview);
            const imageBox = getContainedImageBox(preview, image);
            if (!imageBox.width || !imageBox.height) {
                return;
            }
            const rect = {
                left: previewRect.left + imageBox.left,
                top: previewRect.top + imageBox.top,
                width: imageBox.width,
                height: imageBox.height,
            };
            const x = Math.min(100, Math.max(0, ((ev.clientX - grabOffsetX - rect.left) / rect.width) * 100));
            const y = Math.min(100, Math.max(0, ((ev.clientY - grabOffsetY - rect.top) / rect.height) * 100));
            currentX = Math.round(x);
            currentY = Math.round(y);
            renderPosition();
            cta.dataset.abCurrentX = String(currentX);
            cta.dataset.abCurrentY = String(currentY);
        }

        function updateSizeFromPointer(ev) {
            const deltaX = (ev.clientX - resizeStartX) * resizeDirection;
            currentWidth = Math.round(Math.min(MAX_CTA_WIDTH, Math.max(MIN_CTA_WIDTH, resizeStartWidth + deltaX * 2)));
            cta.dataset.abCurrentWidth = String(currentWidth);
            renderPosition();
        }

        function updateInteraction(ev) {
            if (interactionMode === "resize") {
                updateSizeFromPointer(ev);
            } else {
                updateFromPointer(ev);
            }
        }

        function savePosition() {
            setInputValue(findInput(preview, "cta_position_x"), currentX);
            setInputValue(findInput(preview, "cta_position_y"), currentY);
            setInputValue(findInput(preview, "cta_width"), currentWidth);
        }

        function requestUpdate(ev) {
            pendingEvent = ev;
            if (rafId) {
                return;
            }
            rafId = window.requestAnimationFrame(() => {
                rafId = null;
                if (pendingEvent) {
                    updateInteraction(pendingEvent);
                }
            });
        }

        preview.addEventListener("pointerdown", (ev) => {
            if (ev.button !== 0) {
                return;
            }
            const resizeHandle = ev.target.closest(RESIZE_HANDLE_SELECTOR);
            if (resizeHandle) {
                interactionMode = "resize";
                resizeStartX = ev.clientX;
                resizeStartWidth = currentWidth;
                resizeDirection = resizeHandle.dataset.abResizeSide === "left" ? -1 : 1;
                grabOffsetX = 0;
                grabOffsetY = 0;
            } else if (ev.target.closest(CTA_SELECTOR)) {
                interactionMode = "move";
                const ctaRect = cta.getBoundingClientRect();
                grabOffsetX = ev.clientX - (ctaRect.left + ctaRect.width / 2);
                grabOffsetY = ev.clientY - (ctaRect.top + ctaRect.height / 2);
            } else {
                interactionMode = "move";
                grabOffsetX = 0;
                grabOffsetY = 0;
            }
            dragging = true;
            pointerId = ev.pointerId;
            cta.classList.add(interactionMode === "resize" ? "is-resizing" : "is-dragging");
            if (interactionMode === "move") {
                updateFromPointer(ev);
            }
            try {
                preview.setPointerCapture?.(ev.pointerId);
            } catch {
                // Document-level listeners keep the drag alive if capture is unavailable.
            }
            ev.preventDefault();
        });

        function onPointerMove(ev) {
            if (!dragging || ev.pointerId !== pointerId) {
                return;
            }
            requestUpdate(ev);
            ev.preventDefault();
        }

        function stopDrag(ev, updateFinalPosition = true) {
            if (!dragging || ev.pointerId !== pointerId) {
                return;
            }
            if (updateFinalPosition) {
                updateInteraction(ev);
            }
            if (rafId) {
                window.cancelAnimationFrame(rafId);
                rafId = null;
            }
            savePosition();
            pendingEvent = null;
            dragging = false;
            pointerId = null;
            grabOffsetX = 0;
            grabOffsetY = 0;
            cta.classList.remove("is-dragging", "is-resizing");
            try {
                preview.releasePointerCapture?.(ev.pointerId);
            } catch {
                // Dragging still saved through the updated fields.
            }
            ev.preventDefault();
        }

        preview.addEventListener("pointermove", onPointerMove);
        preview.addEventListener("pointerup", stopDrag);
        preview.addEventListener("pointercancel", (ev) => stopDrag(ev, false));
        document.addEventListener("pointermove", onPointerMove);
        document.addEventListener("pointerup", stopDrag);
        document.addEventListener("pointercancel", (ev) => stopDrag(ev, false));

        image.addEventListener("load", renderPosition);
        if (image.complete) {
            renderPosition();
        }
        if (window.ResizeObserver) {
            new ResizeObserver(renderPosition).observe(preview);
        } else {
            window.addEventListener("resize", renderPosition);
        }
    }

    function start() {
        document.querySelectorAll(PREVIEW_SELECTOR).forEach(attachPreview);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", start, { once: true });
    } else {
        start();
    }
    new MutationObserver(start).observe(document.documentElement, { childList: true, subtree: true });
}());
