/** @odoo-module **/

import { localization } from "@web/core/l10n/localization";
import { insertThousandsSep } from "@web/core/utils/numbers";
import { registry } from "@web/core/registry";
import { Interaction } from "@web/public/interaction";

const DIGITS = "0123456789";
const ROLLER_DURATION = 340;
const ROLLER_DOWN_EXTRA_DURATION = 80;

function normalizeDigits(value) {
    const arabicZero = "٠".charCodeAt(0);
    const easternArabicZero = "۰".charCodeAt(0);
    return String(value || "").replace(/[٠-٩۰-۹]/g, (digit) => {
        const code = digit.charCodeAt(0);
        if (code >= arabicZero && code <= arabicZero + 9) {
            return String(code - arabicZero);
        }
        return String(code - easternArabicZero);
    });
}

function getDecimalPrecision(text) {
    const normalized = normalizeDigits(text);
    const decimalPoint = localization.decimalPoint || ".";
    const index = normalized.lastIndexOf(decimalPoint);
    if (index >= 0) {
        return normalized.length - index - 1;
    }
    const dotIndex = normalized.lastIndexOf(".");
    return dotIndex >= 0 ? normalized.length - dotIndex - 1 : 0;
}

function parseFormattedNumber(text) {
    const normalized = normalizeDigits(text).trim();
    const decimalPoint = localization.decimalPoint || ".";
    let decimalSeen = false;
    let parsed = "";
    for (let index = normalized.length - 1; index >= 0; index--) {
        const char = normalized[index];
        if (/\d/.test(char)) {
            parsed = char + parsed;
        } else if (!decimalSeen && (char === decimalPoint || char === "." || char === ",")) {
            parsed = "." + parsed;
            decimalSeen = true;
        } else if (char === "-" && index === 0) {
            parsed = "-" + parsed;
        }
    }
    const amount = Number.parseFloat(parsed);
    return Number.isFinite(amount) ? amount : null;
}

function formatPrice(amount, precision) {
    const fixed = amount.toFixed(Math.max(0, precision));
    const [whole, decimal] = fixed.split(".");
    const groupedWhole = insertThousandsSep(
        whole,
        localization.thousandsSep,
        localization.grouping,
    );
    return decimal === undefined ? groupedWhole : `${groupedWhole}${localization.decimalPoint}${decimal}`;
}

function isolateLtr(element) {
    element.style.setProperty("direction", "ltr", "important");
    element.style.setProperty("unicode-bidi", "isolate", "important");
}

function getRollingAnimation(fromDigit, toDigit, direction) {
    if (fromDigit === toDigit) {
        return {
            sequence: [toDigit],
            fromOffset: 0,
            toOffset: 0,
        };
    }
    const path = [fromDigit];
    let current = Number.parseInt(fromDigit, 10);
    const target = Number.parseInt(toDigit, 10);
    const step = direction >= 0 ? 1 : -1;
    for (let guard = 0; guard < 10 && current !== target; guard++) {
        current = (current + step + 10) % 10;
        path.push(String(current));
    }
    if (direction >= 0) {
        return {
            sequence: path,
            fromOffset: 0,
            toOffset: path.length - 1,
        };
    }
    return {
        sequence: path.slice().reverse(),
        fromOffset: path.length - 1,
        toOffset: 0,
    };
}

export class AbStorefrontAnimatedPrice extends Interaction {
    static selector = "#product_detail";

    setup() {
        this.total = null;
        this.value = null;
        this.unitPrice = null;
        this.quantity = null;
        this.observer = null;
        this.raf = null;
        this.currentText = "";
        this.currentAmount = null;
        this.reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
        this.onInputChange = this.onInputChange.bind(this);
        this.scheduleRender = this.scheduleRender.bind(this);
    }

    start() {
        this.total = this.el.querySelector("[data-ab-animated-total-price]");
        this.value = this.el.querySelector("[data-ab-animated-total-price-value]");
        this.unitPrice = this.el.querySelector(".oe_price");
        this.quantity = this.el.querySelector("input[name='add_qty']");
        if (!this.total || !this.value || !this.unitPrice || !this.quantity) {
            return;
        }
        this.total.style.setProperty("unicode-bidi", "isolate", "important");
        isolateLtr(this.value);
        this.observer = new MutationObserver(this.scheduleRender);
        this.observer.observe(this.unitPrice, {
            childList: true,
            characterData: true,
            subtree: true,
        });
        this.quantity.addEventListener("input", this.onInputChange);
        this.quantity.addEventListener("change", this.onInputChange);
        this.render({ animate: false });
    }

    destroy() {
        this.observer?.disconnect();
        this.quantity?.removeEventListener("input", this.onInputChange);
        this.quantity?.removeEventListener("change", this.onInputChange);
        if (this.raf) {
            cancelAnimationFrame(this.raf);
            this.raf = null;
        }
    }

    onInputChange() {
        this.scheduleRender();
    }

    scheduleRender() {
        if (this.raf) {
            cancelAnimationFrame(this.raf);
        }
        this.raf = requestAnimationFrame(() => {
            this.raf = null;
            this.render({ animate: true });
        });
    }

    render({ animate }) {
        const state = this.getTotalState();
        if (!state) {
            this.value.textContent = this.unitPrice.textContent.trim();
            this.currentText = "";
            this.currentAmount = null;
            return;
        }

        const shouldAnimate = animate
            && !this.reduceMotion.matches
            && this.currentText
            && this.currentText !== state.formatted;
        const direction = this.currentAmount === null || state.amount >= this.currentAmount ? 1 : -1;
        this.total.setAttribute("aria-label", state.accessibleText);
        this.value.dataset.abAnimatedTotalText = state.formatted;
        this.value.setAttribute("aria-hidden", "true");
        this.value.replaceChildren(...this.buildPriceNodes(state, shouldAnimate, direction));
        this.currentText = state.formatted;
        this.currentAmount = state.amount;
    }

    getTotalState() {
        const currencyValue = this.unitPrice.querySelector(".oe_currency_value");
        const unitText = currencyValue?.textContent?.trim();
        const quantity = Number.parseFloat(normalizeDigits(this.quantity.value));
        if (!currencyValue || !unitText || !Number.isFinite(quantity)) {
            return null;
        }
        const unitAmount = parseFormattedNumber(unitText);
        if (unitAmount === null) {
            return null;
        }
        const precision = this.getPrecision(unitText);
        const amount = unitAmount * Math.max(quantity, 0);
        const formatted = formatPrice(amount, precision);
        const accessibleText = this.unitPrice.textContent.replace(unitText, formatted).trim();
        return { amount, formatted, unitText, accessibleText };
    }

    getPrecision(unitText) {
        const configured = Number.parseInt(
            this.el.querySelector(".product_price.decimal_precision")?.dataset.precision,
            10,
        );
        return Number.isFinite(configured) ? configured : getDecimalPrecision(unitText);
    }

    buildPriceNodes(state, animate, direction) {
        const nodes = [];
        const source = this.unitPrice.cloneNode(true);
        isolateLtr(source);
        const currencyValue = source.querySelector(".oe_currency_value");
        if (!currencyValue) {
            return this.buildCharacterNodes(state.formatted, animate, direction);
        }

        isolateLtr(currencyValue);
        currencyValue.replaceChildren(
            ...this.buildCharacterNodes(state.formatted, animate, direction),
        );
        source.childNodes.forEach((node) => nodes.push(node.cloneNode(true)));
        return nodes;
    }

    buildCharacterNodes(text, animate, direction) {
        return Array.from(text).map((char, index) => {
            if (!DIGITS.includes(char)) {
                const separator = document.createElement("span");
                separator.className = "ab-storefront-total-price-static";
                isolateLtr(separator);
                separator.textContent = char;
                return separator;
            }
            const previousChar = this.currentText[index];
            return this.buildDigitRoller(char, previousChar, animate, direction);
        });
    }

    buildDigitRoller(char, previousChar, animate, direction) {
        const roller = document.createElement("span");
        roller.className = "ab-storefront-total-price-digit";
        isolateLtr(roller);
        const track = document.createElement("span");
        track.className = "ab-storefront-total-price-digit-track";
        isolateLtr(track);
        roller.appendChild(track);

        const canRoll = animate && DIGITS.includes(previousChar) && previousChar !== char;
        const animation = canRoll
            ? getRollingAnimation(previousChar, char, direction)
            : { sequence: [char], fromOffset: 0, toOffset: 0 };
        for (const digit of animation.sequence) {
            const item = document.createElement("span");
            item.className = "ab-storefront-total-price-digit-item";
            item.textContent = digit;
            track.appendChild(item);
        }

        if (canRoll) {
            const duration = Math.min(
                ROLLER_DURATION
                    + (animation.sequence.length - 2) * 16
                    + (direction < 0 ? ROLLER_DOWN_EXTRA_DURATION : 0),
                direction < 0 ? 430 : 360,
            );
            track.style.transitionDuration = "0ms";
            track.style.transform = `translate3d(0, -${animation.fromOffset}em, 0)`;
            track.getBoundingClientRect();
            requestAnimationFrame(() => {
                track.style.transitionDuration = `${duration}ms`;
                track.style.transform = `translate3d(0, -${animation.toOffset}em, 0)`;
            });
        } else if (animate && previousChar !== char) {
            roller.classList.add("ab-storefront-total-price-digit-new");
        }
        return roller;
    }
}

registry
    .category("public.interactions")
    .add("ab_ecommerce_storefront.animated_price", AbStorefrontAnimatedPrice);
