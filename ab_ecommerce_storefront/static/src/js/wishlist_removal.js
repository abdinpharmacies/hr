/** @odoo-module **/

import { rpc } from "@web/core/network/rpc";

const REMOVE_FAVORITE_ROUTE = "/ab/storefront/wishlist/remove_product";
const WISHLIST_BUTTON_SELECTOR = [
    ".ab-storefront-wishlist",
    ".o_add_wishlist",
    ".o_add_wishlist_dyn",
    "[data-action='o_wishlist']",
].join(", ");
const pendingProductIds = new Set();

/**
 * Public JSON-RPC route accepting a product.product ID. It removes the current
 * guest/session or signed-in user's wish and returns {removed, product_ids}.
 */
export function requestFavoriteRemoval(productId) {
    return rpc(REMOVE_FAVORITE_ROUTE, { product_id: productId });
}

export function claimFavoriteRemoval(productId) {
    if (pendingProductIds.has(productId)) {
        return false;
    }
    pendingProductIds.add(productId);
    return true;
}

export function releaseFavoriteRemoval(productId) {
    pendingProductIds.delete(productId);
}

export function setFavoriteButtonsPending(productId, isPending) {
    document.querySelectorAll(`[data-product-product-id="${productId}"]`).forEach((button) => {
        if (!button.matches(WISHLIST_BUTTON_SELECTOR)) {
            return;
        }
        button.classList.toggle("is-favorite-removing", isPending);
        button.disabled = isPending;
        button.setAttribute("aria-busy", isPending ? "true" : "false");
        if (!isPending) {
            button.querySelectorAll(".ab-storefront-favorite-source-icon").forEach((icon) => {
                icon.classList.remove("ab-storefront-favorite-source-icon");
            });
        }
    });
}

export function wishlistProductIdsFromResponse(response) {
    if (!Array.isArray(response?.product_ids)) {
        throw new Error("Invalid wishlist removal response");
    }
    return response.product_ids.map((id) => Number.parseInt(id, 10)).filter(Boolean);
}

function cloneHeartIcon(source) {
    if (!source) {
        const fallback = document.createElement("i");
        fallback.className = "fa fa-heart";
        fallback.setAttribute("aria-hidden", "true");
        return fallback;
    }
    const icon = source.cloneNode(true);
    icon.classList.remove("ab-storefront-favorite-source-icon");
    icon.removeAttribute("id");
    icon.removeAttribute("aria-label");
    icon.setAttribute("aria-hidden", "true");
    if (icon.classList.contains("fa-heart-o")) {
        icon.classList.remove("fa-heart-o");
        icon.classList.add("fa-heart");
    }
    return icon;
}

function createBreakPiece(source, side) {
    const piece = document.createElement("span");
    piece.className = `ab-storefront-favorite-break-piece is-${side}`;
    piece.appendChild(cloneHeartIcon(source));
    return piece;
}

function animationLifecycle(effect) {
    let active = true;
    let resolveFinished;
    const finished = new Promise((resolve) => {
        resolveFinished = resolve;
    });
    const finish = () => {
        if (!active) {
            return;
        }
        active = false;
        effect.remove();
        resolveFinished();
    };

    window.requestAnimationFrame(() => {
        if (!active) {
            return;
        }
        effect.classList.add("is-active");
        window.requestAnimationFrame(() => {
            if (!active) {
                return;
            }
            const animations = effect.getAnimations({ subtree: true });
            if (!animations.length) {
                finish();
                return;
            }
            Promise.allSettled(animations.map((animation) => animation.finished)).then(finish);
        });
    });

    return {
        finished,
        cancel() {
            effect.getAnimations({ subtree: true }).forEach((animation) => animation.cancel());
            finish();
        },
    };
}

export function startFavoriteBreak(button) {
    const source = button.querySelector("svg, .fa-heart, .fa-heart-o");
    const rect = (source || button).getBoundingClientRect();
    const buttonRect = button.getBoundingClientRect();
    const iconSize = Math.max(rect.width, rect.height, 18);
    const card = button.closest(".ab-storefront-product-card, #product_detail");
    const configuredAccent = card?.dataset.abProductAccent
        || window.getComputedStyle(card || button).getPropertyValue("--ab-product-accent").trim();
    const effect = document.createElement("span");
    effect.className = "ab-storefront-favorite-break";
    effect.setAttribute("aria-hidden", "true");
    effect.style.left = `${rect.left - buttonRect.left + rect.width / 2}px`;
    effect.style.top = `${rect.top - buttonRect.top + rect.height / 2}px`;
    effect.style.transform = "translate(-50%, -50%)";
    effect.style.setProperty("--ab-favorite-break-icon-size", `${iconSize}px`);
    effect.style.setProperty("--ab-favorite-break-box-size", `${Math.max(iconSize + 40, 60)}px`);
    effect.style.setProperty("--ab-favorite-break-accent", configuredAccent || "#007f4f");
    effect.style.setProperty(
        "--ab-favorite-break-heart-color",
        window.getComputedStyle(source || button).color || "#ffffff",
    );

    const halo = document.createElement("span");
    halo.className = "ab-storefront-favorite-break-halo";
    const crack = document.createElement("span");
    crack.className = "ab-storefront-favorite-break-crack";
    effect.append(halo, createBreakPiece(source, "start"), createBreakPiece(source, "end"), crack);

    const fragmentVectors = [
        [-20, -17], [-4, -25], [18, -18], [23, 4], [9, 23], [-18, 18],
    ];
    fragmentVectors.forEach(([x, y], index) => {
        const fragment = document.createElement("span");
        fragment.className = `ab-storefront-favorite-break-fragment is-${index % 3}`;
        fragment.style.setProperty("--ab-favorite-fragment-x", `${x}px`);
        fragment.style.setProperty("--ab-favorite-fragment-y", `${y}px`);
        fragment.style.setProperty("--ab-favorite-fragment-delay", `${index * 18}ms`);
        effect.appendChild(fragment);
    });

    button.appendChild(effect);
    const effectRect = effect.getBoundingClientRect();
    const correctionX = rect.left + rect.width / 2 - effectRect.left - effectRect.width / 2;
    const correctionY = rect.top + rect.height / 2 - effectRect.top - effectRect.height / 2;
    effect.style.left = `${parseFloat(effect.style.left) + correctionX}px`;
    effect.style.top = `${parseFloat(effect.style.top) + correctionY}px`;
    source?.classList.add("ab-storefront-favorite-source-icon");
    return animationLifecycle(effect);
}

export async function collapseWishlistCard(article) {
    if (!article?.isConnected) {
        return;
    }
    article.style.setProperty("--ab-favorite-card-height", `${article.getBoundingClientRect().height}px`);
    article.classList.add("is-favorite-leaving");
    await new Promise((resolve) => window.requestAnimationFrame(resolve));
    const animations = article.getAnimations({ subtree: true });
    if (animations.length) {
        await Promise.allSettled(animations.map((animation) => animation.finished));
    }
    article.remove();
}
