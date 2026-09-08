/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Interaction } from "@web/public/interaction";

const SEARCH_INPUT_SELECTOR = [
    ".ab-storefront-search input.search-query[name='search'][data-search-type='products']",
    "[data-ab-mobile-search-input]",
].join(", ");

const PHRASE_SELECTOR = "[data-ab-search-typewriter-phrase]";
const LABEL_SELECTOR = "[data-ab-search-typewriter-label]";
const PREFIX_SELECTOR = "[data-ab-search-typewriter-prefix]";
const TYPE_DELAY = 68;
const DELETE_DELAY = 38;
const HOLD_DELAY = 2100;
const NEXT_PHRASE_DELAY = 260;
const VISIBILITY_RETRY_DELAY = 750;

const FALLBACK_PLACEHOLDER = "What are you looking for?";

export class AbStorefrontSearchTypewriter extends Interaction {
    static selector = "body";

    setup() {
        this.states = new Map();
        this.searchPrefix = "";
        this.searchLabel = "";
        this.searchPhrases = [];
        this.motionQuery = window.matchMedia?.("(prefers-reduced-motion: reduce)") || null;
        this.onMotionPreferenceChange = this.onMotionPreferenceChange.bind(this);
    }

    start() {
        this.inputs = Array.from(this.el.querySelectorAll(SEARCH_INPUT_SELECTOR));
        if (!this.inputs.length) {
            return;
        }
        for (const input of this.inputs) {
            this.bindInput(input);
        }
        this.motionQuery?.addEventListener?.("change", this.onMotionPreferenceChange);
    }

    destroy() {
        this.motionQuery?.removeEventListener?.("change", this.onMotionPreferenceChange);
        for (const state of this.states.values()) {
            this.unbindInput(state);
        }
        this.states.clear();
    }

    bindInput(input) {
        if (input.dataset.abSearchTypewriterBound === "1") {
            return;
        }

        const state = {
            input,
            phraseIndex: 0,
            charIndex: 0,
            deleting: false,
            timer: null,
            handlers: {},
        };
        state.handlers.stop = () => this.stopForUser(state);
        state.handlers.blur = () => this.resumeAfterBlur(state);

        input.dataset.abSearchTypewriterBound = "1";
        input.dataset.abSearchFallbackPlaceholder = input.getAttribute("placeholder") || this.getFallbackPlaceholder();
        const searchLabel = this.getSearchLabel();
        if (!input.getAttribute("aria-label") && searchLabel) {
            input.setAttribute("aria-label", searchLabel);
        }
        input.addEventListener("focus", state.handlers.stop);
        input.addEventListener("pointerdown", state.handlers.stop);
        input.addEventListener("keydown", state.handlers.stop);
        input.addEventListener("input", state.handlers.stop);
        input.addEventListener("blur", state.handlers.blur);

        this.states.set(input, state);
        this.startTyping(state);
    }

    unbindInput(state) {
        const { input, handlers } = state;
        this.clearTimer(state);
        input.removeEventListener("focus", handlers.stop);
        input.removeEventListener("pointerdown", handlers.stop);
        input.removeEventListener("keydown", handlers.stop);
        input.removeEventListener("input", handlers.stop);
        input.removeEventListener("blur", handlers.blur);
        input.placeholder = input.dataset.abSearchFallbackPlaceholder || this.getFallbackPlaceholder();
        delete input.dataset.abSearchTypewriterBound;
        delete input.dataset.abSearchFallbackPlaceholder;
    }

    onMotionPreferenceChange() {
        for (const state of this.states.values()) {
            this.clearTimer(state);
            state.input.placeholder = state.input.dataset.abSearchFallbackPlaceholder || this.getFallbackPlaceholder();
            if (!this.prefersReducedMotion()) {
                this.startTyping(state);
            }
        }
    }

    stopForUser(state) {
        this.clearTimer(state);
        state.input.placeholder = state.input.dataset.abSearchFallbackPlaceholder || this.getFallbackPlaceholder();
        if (!state.input.value.trim()) {
            this.setTimer(state, () => {
                if (document.activeElement !== state.input && !state.input.value.trim()) {
                    this.startTyping(state);
                }
            }, VISIBILITY_RETRY_DELAY);
        }
    }

    resumeAfterBlur(state) {
        if (!state.input.value.trim()) {
            const phrases = this.getSearchPhrases();
            state.phraseIndex = phrases.length ? state.phraseIndex % phrases.length : 0;
            state.charIndex = 0;
            state.deleting = false;
            this.setTimer(state, () => this.startTyping(state), NEXT_PHRASE_DELAY);
        }
    }

    startTyping(state) {
        this.clearTimer(state);
        if (!this.canAnimate(state)) {
            state.input.placeholder = state.input.dataset.abSearchFallbackPlaceholder || this.getFallbackPlaceholder();
            if (!this.prefersReducedMotion() && !state.input.value.trim() && document.activeElement !== state.input) {
                this.setTimer(state, () => this.startTyping(state), VISIBILITY_RETRY_DELAY);
            }
            return;
        }
        if (!this.getSearchPhrases().length) {
            this.setTimer(state, () => this.startTyping(state), VISIBILITY_RETRY_DELAY);
            return;
        }
        this.tick(state);
    }

    tick(state) {
        if (!this.canAnimate(state)) {
            this.startTyping(state);
            return;
        }

        const phrases = this.getSearchPhrases();
        if (!phrases.length) {
            this.startTyping(state);
            return;
        }
        const phrase = phrases[state.phraseIndex % phrases.length] || "";
        let delay = TYPE_DELAY;

        if (state.deleting) {
            state.charIndex -= 1;
            if (state.charIndex <= 0) {
                state.charIndex = 0;
                state.deleting = false;
                state.phraseIndex = (state.phraseIndex + 1) % phrases.length;
                delay = NEXT_PHRASE_DELAY;
            } else {
                delay = DELETE_DELAY;
            }
        } else {
            state.charIndex += 1;
            if (state.charIndex >= phrase.length) {
                state.charIndex = phrase.length;
                state.deleting = true;
                delay = HOLD_DELAY;
            }
        }

        state.input.placeholder = this.formatPlaceholder(phrase.slice(0, state.charIndex));
        this.setTimer(state, () => this.tick(state), delay);
    }

    canAnimate(state) {
        return Boolean(
            state.input.isConnected
            && !this.prefersReducedMotion()
            && document.activeElement !== state.input
            && !state.input.value.trim()
            && this.isVisible(state.input)
        );
    }

    getFallbackPlaceholder() {
        return FALLBACK_PLACEHOLDER;
    }

    getSearchLabel() {
        if (this.searchLabel) {
            return this.searchLabel;
        }
        this.searchLabel = document.querySelector(LABEL_SELECTOR)?.textContent?.trim() || "";
        return this.searchLabel;
    }

    getSearchPrefix() {
        if (this.searchPrefix) {
            return this.searchPrefix;
        }
        this.searchPrefix = document.querySelector(PREFIX_SELECTOR)?.textContent?.trim() || "";
        return this.searchPrefix;
    }

    getSearchPhrases() {
        if (this.searchPhrases.length) {
            return this.searchPhrases;
        }
        this.searchPhrases = Array.from(document.querySelectorAll(PHRASE_SELECTOR))
            .map((phrase) => phrase.textContent.trim())
            .filter(Boolean);
        return this.searchPhrases;
    }

    formatPlaceholder(animatedPart) {
        const prefix = this.getSearchPrefix();
        if (!prefix) {
            return animatedPart ? `${animatedPart}...` : "";
        }
        return animatedPart ? `${prefix} ${animatedPart}...` : `${prefix} `;
    }

    prefersReducedMotion() {
        return Boolean(this.motionQuery?.matches);
    }

    isVisible(input) {
        return Boolean(input.offsetWidth || input.offsetHeight || input.getClientRects().length);
    }

    setTimer(state, callback, delay) {
        this.clearTimer(state);
        state.timer = window.setTimeout(callback, delay);
    }

    clearTimer(state) {
        if (state.timer) {
            window.clearTimeout(state.timer);
            state.timer = null;
        }
    }
}

registry
    .category("public.interactions")
    .add("ab_ecommerce_storefront.search_typewriter", AbStorefrontSearchTypewriter);

let standaloneTypewriter = null;

function startSearchTypewriterInteraction(attempt = 0) {
    if (!document.querySelector(SEARCH_INPUT_SELECTOR)) {
        return;
    }
    const publicInteractions = globalThis.odoo?.__WOWL_DEBUG__?.root?.env?.services?.["public.interactions"];
    if (publicInteractions) {
        publicInteractions.startInteractions(document.body);
        return;
    }
    if (!standaloneTypewriter) {
        standaloneTypewriter = Object.create(AbStorefrontSearchTypewriter.prototype);
        standaloneTypewriter.el = document.body;
        standaloneTypewriter.setup();
        standaloneTypewriter.start();
        window.addEventListener("pagehide", () => {
            standaloneTypewriter?.destroy();
            standaloneTypewriter = null;
        }, { once: true });
        return;
    }
    if (attempt < 20) {
        window.setTimeout(() => startSearchTypewriterInteraction(attempt + 1), 250);
    }
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => startSearchTypewriterInteraction(), { once: true });
} else {
    startSearchTypewriterInteraction();
}
