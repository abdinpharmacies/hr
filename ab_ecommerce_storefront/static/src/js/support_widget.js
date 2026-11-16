/** @odoo-module ignore **/
(function () {
    "use strict";

    const WIDGET_SELECTOR = "[data-ab-support-widget]";
    const TOGGLE_SELECTOR = "[data-ab-support-toggle]";
    const CLOSE_SELECTOR = "[data-ab-support-close]";
    const LIVECHAT_SELECTOR = "[data-ab-support-livechat]";
    const CHOICE_SELECTOR = "[data-ab-support-choice]";
    const CHOICE_STORAGE_KEY = "ab-storefront-support-choice";
    const OPEN_CLASS = "is-open";
    const CLOSING_CLASS = "is-closing";
    const CLOSE_ANIMATION_DELAY = 760;

    function setupWidget(widget) {
        const toggle = widget.querySelector(TOGGLE_SELECTOR);
        const closeButton = widget.querySelector(CLOSE_SELECTOR);
        const livechatButton = widget.querySelector(LIVECHAT_SELECTOR);
        const toggleIcon = toggle?.querySelector(".ab-storefront-support-toggle-icon--chat");
        if (!toggleIcon?.firstElementChild) {
            return;
        }

        const choiceItems = [...widget.querySelectorAll(CHOICE_SELECTOR)];
        const defaultIcon = toggleIcon.firstElementChild.cloneNode(true);
        let selectedChoice = null;
        try {
            selectedChoice = window.localStorage.getItem(CHOICE_STORAGE_KEY);
        } catch {
            selectedChoice = null;
        }
        let closeTimer = null;

        function renderSelectedChoice() {
            const item = choiceItems.find((choiceItem) => choiceItem.dataset.abSupportChoice === selectedChoice);
            const icon = !item?.hidden && item?.querySelector(".ab-storefront-support-item-icon > *");
            toggleIcon.replaceChildren((icon || defaultIcon).cloneNode(true));
        }

        function rememberChoice(choice) {
            try {
                window.localStorage.setItem(CHOICE_STORAGE_KEY, choice);
            } catch {
                return;
            }
        }

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
            if (nextOpen) {
                widget.querySelector(".ab-storefront-support-item:not([hidden])")?.focus();
            }
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

        if (livechatButton) {
            const syncLivechat = () => {
                livechatButton.hidden = !document.body.classList.contains("ab-livechat-integrated");
                renderSelectedChoice();
            };
            window.addEventListener("ab-storefront:livechat-ready", syncLivechat);
            syncLivechat();
        } else {
            renderSelectedChoice();
        }

        choiceItems.forEach((item) => {
            item.addEventListener("click", () => {
                selectedChoice = item.dataset.abSupportChoice;
                rememberChoice(selectedChoice);
                renderSelectedChoice();
                setOpen(false, item === livechatButton);
                if (item !== livechatButton) {
                    return;
                }
                window.dispatchEvent(new Event("ab-storefront:open-livechat"));
            });
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
