/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import wishlistUtils from "@website_sale_wishlist/js/website_sale_wishlist_utils";

const CART_ROOT_SELECTOR = "#shop_cart";
const LINE_SELECTOR = "#cart_products .o_cart_product";
const CHECKBOX_SELECTOR = ".ab-storefront-cart-line-checkbox";
const WISHLIST_BUTTON_SELECTOR = ".ab-storefront-cart-move-wishlist";

let wishlistSyncPromise = null;
let wishlistStateLoaded = false;
let cartViewportFrame = null;
let cartViewportBottom = -1;

function getProductId(button) {
    const value = Number.parseInt(button?.dataset?.productProductId || "0", 10);
    return Number.isFinite(value) ? value : 0;
}

function setLineLoading(element, isLoading) {
    const line = element?.closest?.(LINE_SELECTOR);
    line?.classList.toggle("ab-storefront-cart-line-loading", !!isLoading);
}

function syncCartActionsViewportBottom() {
    const viewport = window.visualViewport;
    const bottomOffset = viewport
        ? Math.max(0, window.innerHeight - viewport.height - viewport.offsetTop)
        : 0;
    const roundedOffset = Math.round(bottomOffset);
    if (Math.abs(roundedOffset - cartViewportBottom) < 4) return;
    cartViewportBottom = roundedOffset;
    document.documentElement.style.setProperty(
        "--ab-cart-actions-bottom",
        `${roundedOffset}px`
    );
}

function scheduleCartActionsViewportSync() {
    if (cartViewportFrame) return;
    cartViewportFrame = window.requestAnimationFrame(() => {
        cartViewportFrame = null;
        syncCartActionsViewportBottom();
    });
}

function applyWishlistState(root = document, productIds = wishlistUtils.getWishlistProductIds()) {
    const wishlistIds = new Set((productIds || []).map((id) => Number.parseInt(id, 10)));
    root.querySelectorAll(WISHLIST_BUTTON_SELECTOR).forEach((button) => {
        const productId = getProductId(button);
        const isActive = productId > 0 && wishlistIds.has(productId);
        if (button.disabled) {
            button.disabled = false;
        }
        if (button.classList.contains("disabled")) {
            button.classList.remove("disabled");
        }
        button.classList.toggle("o_in_wishlist", isActive);
        const pressed = isActive ? "true" : "false";
        const labelText = isActive ? _t("Added to Favorite") : _t("Add to Favorite");
        const accessibleText = isActive ? _t("In Favorites") : _t("Add to Favorites");
        if (button.getAttribute("aria-pressed") !== pressed) {
            button.setAttribute("aria-pressed", pressed);
        }
        if (button.getAttribute("aria-label") !== accessibleText) {
            button.setAttribute("aria-label", accessibleText);
        }
        if (button.getAttribute("title") !== accessibleText) {
            button.setAttribute("title", accessibleText);
        }
        const label = button.querySelector(".ab-storefront-cart-wishlist-label");
        if (label && label.textContent.trim() !== labelText) {
            label.textContent = labelText;
        }
    });
}

async function removeCartLineFromWishlist(button) {
    const productId = getProductId(button);
    if (!productId) return;
    setLineLoading(button, true);
    button.classList.add("is-loading");
    button.disabled = true;
    try {
        const response = await rpc("/ab/storefront/wishlist/remove_product", { product_id: productId });
        wishlistUtils.setWishlistProductIds(response?.product_ids || []);
        wishlistUtils.updateWishlistNavBar();
        applyWishlistState(document);
    } catch {
        button.classList.add("is-error");
        window.setTimeout(() => button.classList.remove("is-error"), 1800);
        await refreshWishlistState(document, { force: true });
    } finally {
        button.classList.remove("is-loading");
        button.disabled = false;
        setLineLoading(button, false);
    }
}

async function addCartLineToWishlist(button) {
    const productId = getProductId(button);
    if (!productId) return;
    setLineLoading(button, true);
    button.classList.add("is-loading");
    button.disabled = true;
    try {
        await rpc("/shop/wishlist/add", { product_id: productId });
        wishlistUtils.addWishlistProduct(productId);
        wishlistUtils.updateWishlistNavBar();
        applyWishlistState(document);
    } catch {
        button.classList.add("is-error");
        window.setTimeout(() => button.classList.remove("is-error"), 1800);
        await refreshWishlistState(document, { force: true });
    } finally {
        button.classList.remove("is-loading");
        button.disabled = false;
        setLineLoading(button, false);
    }
}

async function refreshWishlistState(root = document, { force = false } = {}) {
    applyWishlistState(root);
    if (!document.querySelector(WISHLIST_BUTTON_SELECTOR)) return;
    if (wishlistStateLoaded && !force) return;
    if (!wishlistSyncPromise) {
        wishlistSyncPromise = rpc("/shop/wishlist/get_product_ids")
            .then((productIds) => {
                wishlistUtils.setWishlistProductIds(productIds || []);
                wishlistStateLoaded = true;
                return productIds || [];
            })
            .catch(() => wishlistUtils.getWishlistProductIds())
            .finally(() => {
                wishlistSyncPromise = null;
            });
    }
    applyWishlistState(root, await wishlistSyncPromise);
}

function getQuantityInput(line) {
    return line.querySelector(".css_quantity > input.js_quantity");
}

function ensureTrashIcon(button) {
    if (!button) return null;
    const existingIcon = button.querySelector(".ab-storefront-cart-trash-icon");
    if (existingIcon) return existingIcon;
    const icon = document.createElement("i");
    icon.className = "fa fa-trash-o ab-storefront-cart-trash-icon";
    icon.setAttribute("aria-hidden", "true");
    button.appendChild(icon);
    return icon;
}

function setQuantityMinusState(minus, value) {
    if (!minus) return;
    const removesLine = value <= 1;
    minus.classList.toggle("ab-storefront-cart-removes-line", removesLine);
    if (removesLine) {
        ensureTrashIcon(minus);
    } else {
        minus.querySelector(".ab-storefront-cart-trash-icon")?.remove();
    }
    minus.setAttribute("aria-label", removesLine ? _t("Remove from cart") : _t("Remove one"));
    minus.setAttribute("title", removesLine ? _t("Remove from cart") : _t("Remove one"));
}

function updateQuantityIcons(root = document) {
    root.querySelectorAll(`${LINE_SELECTOR} .css_quantity`).forEach((quantity) => {
        const input = quantity.querySelector("input.js_quantity");
        const minus = [...quantity.querySelectorAll("a")].find((button) =>
            button.querySelector(".oi-minus")
        );
        if (!input || !minus) return;
        const value = Number.parseFloat(input.value || "0");
        setQuantityMinusState(minus, value);
    });
}

function syncLineSelectionStyles(root = document) {
    root.querySelectorAll(LINE_SELECTOR).forEach((line) => {
        const checkbox = line.querySelector(CHECKBOX_SELECTOR);
        line.classList.toggle(
            "ab-storefront-cart-item-unselected",
            !!checkbox && !checkbox.checked
        );
    });
}

function normalizeDigits(value) {
    return String(value || "")
        .replace(/[٠-٩]/g, (digit) => "٠١٢٣٤٥٦٧٨٩".indexOf(digit))
        .replace(/[۰-۹]/g, (digit) => "۰۱۲۳۴۵۶۷۸۹".indexOf(digit))
        .replace(/\u066B/g, ".")
        .replace(/\u066C/g, ",");
}

function getNumberToken(text) {
    const normalized = normalizeDigits(text).replace(/\s+/g, " ");
    const matches = normalized.match(/[-+]?\d[\d\s,.]*/g);
    return matches?.findLast((match) => /\d/.test(match))?.trim() || "";
}

function parseMoney(text) {
    const token = getNumberToken(text);
    if (!token) return 0;

    const compact = token.replace(/\s/g, "");
    const lastDot = compact.lastIndexOf(".");
    const lastComma = compact.lastIndexOf(",");
    const decimalIndex = Math.max(lastDot, lastComma);
    let normalized;

    if (decimalIndex >= 0 && compact.length - decimalIndex - 1 <= 2) {
        const integerPart = compact.slice(0, decimalIndex).replace(/[,.]/g, "");
        const decimalPart = compact.slice(decimalIndex + 1).replace(/[,.]/g, "");
        normalized = `${integerPart}.${decimalPart}`;
    } else {
        normalized = compact.replace(/[,.]/g, "");
    }
    const parsed = Number.parseFloat(normalized);
    return Number.isFinite(parsed) ? parsed : 0;
}

function getFractionDigits(text) {
    const token = getNumberToken(text);
    const separatorIndex = Math.max(token.lastIndexOf("."), token.lastIndexOf(","));
    if (separatorIndex < 0) return 2;
    return Math.min(Math.max(token.length - separatorIndex - 1, 0), 2);
}

function formatLikeOriginal(value, originalText) {
    const token = getNumberToken(originalText);
    const fractionDigits = getFractionDigits(originalText);
    const formatted = value.toLocaleString(document.documentElement.lang || undefined, {
        minimumFractionDigits: fractionDigits,
        maximumFractionDigits: fractionDigits,
    });
    return token ? String(originalText).replace(token, formatted) : formatted;
}

function getVisibleLinePrice(line) {
    const prices = [
        ...line.querySelectorAll(
            "[name='website_sale_cart_line_price'] .monetary_field, "
            + "[name='website_sale_cart_line_price'] span, "
            + ".ab-storefront-cart-line-price .monetary_field, "
            + ".ab-storefront-cart-line-price span"
        ),
    ].filter((element) => !element.closest("del"));
    return prices.find((element) => element.offsetParent !== null) || prices[0] || null;
}

function getMoneyElement(selector) {
    return document.querySelector(`${selector} .monetary_field`);
}

function rememberOriginalMoney(element) {
    if (!element) return "";
    if (!element.dataset.abOriginalMoneyText) {
        element.dataset.abOriginalMoneyText = element.textContent.trim();
    }
    return element.dataset.abOriginalMoneyText;
}

function setMoney(element, value) {
    const originalText = rememberOriginalMoney(element);
    if (!element || !originalText) return;
    const nextText = formatLikeOriginal(Math.max(value, 0), originalText);
    if (element.textContent.trim() !== nextText) {
        element.textContent = nextText;
    }
}

function updateSelectedSummary() {
    const lines = [...document.querySelectorAll(LINE_SELECTOR)];
    if (!lines.length) return;

    const totals = lines.reduce((result, line) => {
        const price = parseMoney(getVisibleLinePrice(line)?.textContent || "");
        const checkbox = line.querySelector(CHECKBOX_SELECTOR);
        result.all += price;
        if (!checkbox || checkbox.checked) {
            result.selected += price;
        }
        return result;
    }, { all: 0, selected: 0 });

    const ratio = totals.all > 0 ? totals.selected / totals.all : 1;
    const hasExcludedLines = totals.selected < totals.all;
    const selectedHasValue = totals.selected > 0;
    const deliveryElement = getMoneyElement("[name='o_order_delivery']");
    const untaxedElement = getMoneyElement("[name='o_order_total_untaxed']");
    const taxElement = getMoneyElement("[name='o_order_total_taxes']");
    const totalElement = getMoneyElement("[name='o_order_total']");
    const originalDelivery = parseMoney(rememberOriginalMoney(deliveryElement));
    const originalUntaxed = parseMoney(rememberOriginalMoney(untaxedElement));
    const originalTax = parseMoney(rememberOriginalMoney(taxElement));
    const selectedDelivery = hasExcludedLines && !selectedHasValue ? 0 : originalDelivery;

    document.querySelector(CART_ROOT_SELECTOR)?.classList.toggle(
        "ab-storefront-cart-has-excluded-lines",
        hasExcludedLines
    );

    if (hasExcludedLines) {
        setMoney(untaxedElement, originalUntaxed * ratio);
        setMoney(taxElement, originalTax * ratio);
        setMoney(deliveryElement, selectedDelivery);
        setMoney(totalElement, (originalUntaxed * ratio) + (originalTax * ratio) + selectedDelivery);
    } else {
        [deliveryElement, untaxedElement, taxElement, totalElement].forEach((element) => {
            const originalText = rememberOriginalMoney(element);
            if (element && originalText && element.textContent.trim() !== originalText) {
                element.textContent = originalText;
            }
        });
    }
}

function bindCartSelection(root = document) {
    updateQuantityIcons(root);
    refreshWishlistState(root);
    syncLineSelectionStyles(root);
    updateSelectedSummary();
}

function scheduleCartBind(root = document) {
    window.requestAnimationFrame(() => bindCartSelection(root));
}

function scheduleCartRebindAfterOdooUpdate() {
    // Odoo replaces `.js_cart_lines` and the cart summary after quantity/delete RPCs.
    // Rebind around that async replacement without keeping a broad MutationObserver alive.
    [350, 900, 1600].forEach((delay) => {
        window.setTimeout(() => scheduleCartBind(document), delay);
    });
}

function startCartSelection() {
    bindCartSelection();
    syncCartActionsViewportBottom();
}

document.addEventListener("change", (event) => {
    if (!event.target.matches(CHECKBOX_SELECTOR)) return;
    syncLineSelectionStyles();
    updateSelectedSummary();
});

document.addEventListener("input", (event) => {
    if (!event.target.matches(".css_quantity > input.js_quantity")) return;
    setLineLoading(event.target, true);
    window.setTimeout(() => setLineLoading(event.target, false), 900);
    updateQuantityIcons();
    updateSelectedSummary();
    scheduleCartRebindAfterOdooUpdate();
});

document.addEventListener("click", (event) => {
    const quantityButton = event.target.closest(`${LINE_SELECTOR} .css_quantity .btn`);
    if (!quantityButton) return;
    const quantity = quantityButton.closest(".css_quantity");
    const input = quantity?.querySelector("input.js_quantity");
    const minus = [...(quantity?.querySelectorAll("a") || [])].find((button) =>
        button.querySelector(".oi-minus")
    );
    const currentValue = Number.parseFloat(input?.value || "0");
    if (Number.isFinite(currentValue)) {
        const nextValue = quantityButton.querySelector(".oi-plus")
            ? currentValue + 1
            : Math.max(currentValue - 1, 0);
        window.requestAnimationFrame(() => setQuantityMinusState(minus, nextValue));
    }
    setLineLoading(quantityButton, true);
    window.setTimeout(() => setLineLoading(quantityButton, false), 1100);
    window.setTimeout(() => updateQuantityIcons(), 80);
    window.setTimeout(() => updateQuantityIcons(), 220);
    scheduleCartRebindAfterOdooUpdate();
});

document.addEventListener("click", (event) => {
    const button = event.target.closest(WISHLIST_BUTTON_SELECTOR);
    if (!button) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    const productId = getProductId(button);
    const isActive = button.classList.contains("o_in_wishlist")
        || wishlistUtils.getWishlistProductIds().includes(productId);
    if (!isActive) {
        addCartLineToWishlist(button);
        return;
    }
    removeCartLineFromWishlist(button);
}, true);

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", startCartSelection, { once: true });
} else {
    startCartSelection();
}

window.addEventListener("resize", scheduleCartActionsViewportSync, { passive: true });
window.addEventListener("scroll", scheduleCartActionsViewportSync, { passive: true });
window.visualViewport?.addEventListener("resize", scheduleCartActionsViewportSync, {
    passive: true,
});
window.visualViewport?.addEventListener("scroll", scheduleCartActionsViewportSync, {
    passive: true,
});
