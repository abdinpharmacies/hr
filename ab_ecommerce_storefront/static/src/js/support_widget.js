/** @odoo-module ignore **/
(function () {
    "use strict";

    const WIDGET_SELECTOR = "[data-ab-support-widget]";
    const TOGGLE_SELECTOR = "[data-ab-support-toggle]";
    const CLOSE_SELECTOR = "[data-ab-support-close]";
    const OPEN_CLASS = "is-open";
    const CLOSING_CLASS = "is-closing";
    const CLOSE_ANIMATION_DELAY = 760;

    function setupWidget(widget) {
        const toggle = widget.querySelector(TOGGLE_SELECTOR);
        const closeButton = widget.querySelector(CLOSE_SELECTOR);
        if (!toggle) {
            return;
        }

        let closeTimer = null;

        function clearCloseTimer() {
            if (!closeTimer) {
                return;
            }
            clearTimeout(closeTimer);
            closeTimer = null;
        }

        function setOpen(nextOpen, focusToggle) {
            clearCloseTimer();
            if (nextOpen) {
                widget.classList.remove(CLOSING_CLASS);
                widget.classList.add(OPEN_CLASS);
            } else if (widget.classList.contains(OPEN_CLASS)) {
                widget.classList.remove(OPEN_CLASS);
                widget.classList.add(CLOSING_CLASS);
                closeTimer = setTimeout(() => {
                    widget.classList.remove(CLOSING_CLASS);
                    closeTimer = null;
                }, CLOSE_ANIMATION_DELAY);
            } else {
                widget.classList.remove(CLOSING_CLASS);
            }
            toggle.setAttribute("aria-expanded", nextOpen ? "true" : "false");
            if (focusToggle) {
                toggle.focus();
            }
        }

        toggle.addEventListener("click", (ev) => {
            ev.preventDefault();
            setOpen(!widget.classList.contains(OPEN_CLASS));
        });

        closeButton?.addEventListener("click", (ev) => {
            ev.preventDefault();
            setOpen(false, true);
        });

        document.addEventListener("click", (ev) => {
            if (!widget.classList.contains(OPEN_CLASS) || widget.contains(ev.target)) {
                return;
            }
            setOpen(false);
        });

        document.addEventListener("keydown", (ev) => {
            if (ev.key !== "Escape" || !widget.classList.contains(OPEN_CLASS)) {
                return;
            }
            setOpen(false, true);
        });

        setOpen(false);
        widget.dataset.abSupportReady = "true";
    }

    function start() {
        document.querySelectorAll(WIDGET_SELECTOR).forEach(setupWidget);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", start, { once: true });
    } else {
        start();
    }
}());
