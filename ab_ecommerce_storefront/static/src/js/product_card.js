/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { registry } from "@web/core/registry";
import { Interaction } from "@web/public/interaction";
import wishlistUtils from "@website_sale_wishlist/js/website_sale_wishlist_utils";

const CARD_FLY_DURATION = 760;

export class AbStorefrontProductCard extends Interaction {
    static selector = ".ab-storefront-product-card";
    dynamicContent = {
        ".ab-storefront-card-add": { "t-on-click.prevent": this.onAddToCart },
        "[data-ab-card-quantity]": { "t-on-click.prevent": this.onChangeQuantity },
        ".ab-storefront-unit-option": { "t-on-click.prevent": this.onSelectUnit },
    };

    setup() {
        this.onWishlistClick = this.onWishlistClick.bind(this);
    }

    start() {
        this.el.addEventListener("click", this.onWishlistClick, true);
        const addButton = this.el.querySelector(".ab-storefront-card-add");
        const label = addButton?.querySelector("[data-ab-card-add-label]");
        if (label && addButton.getAttribute("aria-label")) {
            label.title = addButton.getAttribute("aria-label");
        }
    }

    destroy() {
        this.el.removeEventListener("click", this.onWishlistClick, true);
    }

    async onWishlistClick(ev) {
        const button = ev.target.closest?.(".ab-storefront-wishlist");
        if (!button || !this.el.contains(button) || button.classList.contains("is-loading")) {
            return;
        }
        const productId = parseInt(button.dataset.productProductId, 10);
        if (!productId) {
            return;
        }

        ev.preventDefault();
        ev.stopImmediatePropagation();
        const isWishlisted = button.classList.contains("o_in_wishlist")
            || wishlistUtils.getWishlistProductIds().includes(productId);
        button.classList.add("is-loading");
        button.disabled = true;
        try {
            if (isWishlisted) {
                const wishId = await this.waitFor(this.getWishlistId(productId));
                if (!wishId) {
                    throw new Error("Wishlist entry not found");
                }
                await this.waitFor(rpc(`/shop/wishlist/remove/${wishId}`));
                wishlistUtils.removeWishlistProduct(productId);
                this.updateWishlistButtons(productId, false);
            } else {
                this.showActionFeedback(button, "wishlist");
                await this.waitFor(rpc("/shop/wishlist/add", { product_id: productId }));
                wishlistUtils.addWishlistProduct(productId);
                this.updateWishlistButtons(productId, true);
            }
            wishlistUtils.updateWishlistNavBar();
        } catch {
            button.classList.add("is-error");
            const errorLabel = _t("Could not update wishlist. Please try again.");
            button.setAttribute("aria-label", errorLabel);
            button.title = errorLabel;
            window.setTimeout(() => {
                if (!button.isConnected) {
                    return;
                }
                button.classList.remove("is-error");
                const isActive = button.classList.contains("o_in_wishlist");
                const label = isActive ? _t("Remove from wishlist") : _t("Add to wishlist");
                button.setAttribute("aria-label", label);
                button.title = label;
            }, 1800);
        } finally {
            button.classList.remove("is-loading");
            button.disabled = false;
        }
    }

    async getWishlistId(productId) {
        const response = await fetch("/shop/wishlist", {
            credentials: "same-origin",
            headers: { "X-Requested-With": "XMLHttpRequest" },
        });
        if (!response.ok) {
            return 0;
        }
        const html = await response.text();
        const doc = new DOMParser().parseFromString(html, "text/html");
        return parseInt(
            doc.querySelector(`article[data-product-id="${productId}"][data-wish-id]`)
                ?.dataset.wishId,
            10,
        ) || 0;
    }

    updateWishlistButtons(productId, isWishlisted) {
        document.querySelectorAll(
            `.ab-storefront-wishlist[data-product-product-id="${productId}"]`,
        ).forEach((button) => {
            button.classList.toggle("o_in_wishlist", isWishlisted);
            button.disabled = false;
            button.setAttribute("aria-pressed", isWishlisted ? "true" : "false");
            const label = isWishlisted ? _t("Remove from wishlist") : _t("Add to wishlist");
            button.setAttribute("aria-label", label);
            button.title = label;
        });
    }

    async onAddToCart(ev) {
        const button = ev.currentTarget;
        if (button.disabled || button.classList.contains("is-loading")) {
            return;
        }

        const form = button.closest("form.oe_product_cart");
        const product = this.getProductData(form);
        if (!product) {
            this.showMessage(button, _t("Could not add this product. Please try again."));
            return;
        }

        button.dataset.abReadyLabel = this.getButtonLabel(button) || _t("Buy now");
        this.setButtonState(button, "loading", _t("Adding..."));
        try {
            window.abStorefrontSuppressNextCartMotion = true;
            const quantity = await this.waitFor(this.services["cart"].add(product, {
                isBuyNow: false,
                isConfigured: false,
                redirectToCart: false,
                showQuantity: false,
            }));
            window.abStorefrontSuppressNextCartMotion = false;
            if (!quantity) {
                this.setButtonState(button, "ready", this.getReadyLabel(button));
                return;
            }
            this.clearMessage(button);
            this.setButtonState(button, "success", _t("Added"));
            this.showActionFeedback(button, "cart");
            window.setTimeout(() => {
                if (button.isConnected && button.classList.contains("is-success")) {
                    this.setButtonState(button, "ready", this.getReadyLabel(button));
                }
            }, 1400);
        } catch {
            window.abStorefrontSuppressNextCartMotion = false;
            this.setButtonState(button, "error", this.getReadyLabel(button));
            this.showMessage(button, _t("Could not add this product. Please try again."));
        }
    }

    onChangeQuantity(ev) {
        const input = this.el.querySelector("input[name='add_qty']");
        if (!input) {
            return;
        }
        const direction = ev.currentTarget.dataset.abCardQuantity;
        const current = Math.max(parseInt(input.value, 10) || 1, 1);
        input.value = String(direction === "increase" ? current + 1 : Math.max(current - 1, 1));
        input.dispatchEvent(new Event("change", { bubbles: true }));
    }

    onSelectUnit(ev) {
        const selected = ev.currentTarget;
        const unitKey = selected.dataset.unitKey;
        const uomInput = this.el.querySelector("input[name='uom_id']");
        if (!unitKey || !uomInput) {
            return;
        }
        uomInput.value = selected.dataset.uomId;
        this.el.querySelectorAll(".ab-storefront-unit-option").forEach((option) => {
            const isSelected = option === selected;
            option.classList.toggle("is-selected", isSelected);
            option.setAttribute("aria-pressed", isSelected ? "true" : "false");
        });
        this.el.querySelectorAll(".ab-storefront-unit-price").forEach((price) => {
            price.classList.toggle("is-selected", price.dataset.unitPrice === unitKey);
        });
    }

    getProductData(form) {
        const productTemplateId = this.getIntegerField(form, "product_template_id");
        const productId = this.getIntegerField(form, "product_id");
        if (!form || !productTemplateId || !productId) {
            return null;
        }
        return {
            productTemplateId,
            productId,
            quantity: Math.max(parseInt(form.querySelector("input[name='add_qty']")?.value, 10) || 1, 1),
            uomId: this.getIntegerField(form, "uom_id") || undefined,
            isCombo: form.querySelector("input[name='product_type']")?.value === "combo",
        };
    }

    getIntegerField(form, name) {
        const value = form?.querySelector(`input[name='${name}']`)?.value;
        const parsed = parseInt(value, 10);
        return Number.isFinite(parsed) ? parsed : 0;
    }

    setButtonState(button, state, label) {
        button.disabled = state === "loading";
        button.setAttribute("aria-busy", state === "loading" ? "true" : "false");
        button.classList.toggle("is-loading", state === "loading");
        button.classList.toggle("is-success", state === "success");
        button.classList.toggle("is-error", state === "error");
        button.setAttribute("aria-label", label);
        const labelEl = button.querySelector("[data-ab-card-add-label]");
        if (labelEl) {
            labelEl.title = label;
            labelEl.replaceChildren();
        }
    }

    getButtonLabel(button) {
        return button.querySelector("[data-ab-card-add-label]")?.title || button.getAttribute("aria-label");
    }

    getReadyLabel(button) {
        return button.dataset.abReadyLabel || _t("Buy now");
    }

    showMessage(button, message) {
        const actions = button.closest(".ab-storefront-product-actions");
        if (!actions) {
            return;
        }
        let messageEl = actions.querySelector(".ab-storefront-card-message");
        if (!messageEl) {
            messageEl = document.createElement("div");
            messageEl.className = "ab-storefront-card-message";
            messageEl.setAttribute("role", "status");
            actions.appendChild(messageEl);
        }
        messageEl.textContent = message;
    }

    clearMessage(button) {
        button.closest(".ab-storefront-product-actions")
            ?.querySelector(".ab-storefront-card-message")
            ?.remove();
    }

    getProductImage(button) {
        const productCard = button.closest(".ab-storefront-product-card");
        const image = productCard?.querySelector(".ab-storefront-product-media img");
        return image && this.hasVisibleRect(image) && (image.currentSrc || image.src) ? image : null;
    }

    getWishlistTarget() {
        const targets = [
            ...document.querySelectorAll(
                ".ab-storefront-actions .o_wsale_my_wish .ab-storefront-action,"
                + " .ab-storefront-actions .o_wsale_my_wish a,"
                + " .ab-storefront-actions a[href*='/shop/wishlist'],"
                + " .o_wsale_my_wish .ab-storefront-action,"
                + " .o_wsale_my_wish a,"
                + " a[href*='/shop/wishlist']"
            ),
        ];
        return targets.find((target) => this.hasVisibleRect(target)) || null;
    }

    getProductName(button) {
        const productCard = button.closest(".ab-storefront-product-card");
        return productCard?.querySelector(".ab-storefront-product-name")?.textContent?.trim() || "";
    }

    hasVisibleRect(element) {
        const rect = element.getBoundingClientRect();
        const style = window.getComputedStyle(element);
        return rect.width > 0 && rect.height > 0 && style.visibility !== "hidden" && style.display !== "none";
    }

    showActionFeedback(button, action) {
        const image = this.getProductImage(button);
        const target = action === "wishlist" ? this.getWishlistTarget() : this.getCartTarget();
        this.showButtonPulse(button);
        this.showToast({
            image,
            title: this.getProductName(button),
            action,
        });
        if (image && target) {
            this.flyImageToTarget(image, target);
        } else if (target) {
            this.bounceTarget(target);
        }
    }

    getCartTarget() {
        const targets = [
            ...document.querySelectorAll(
                ".ab-storefront-actions .o_wsale_my_cart .ab-storefront-action,"
                + " .ab-storefront-actions .o_wsale_my_cart a,"
                + " .ab-storefront-actions a[href*='/shop/cart'],"
                + " .o_wsale_my_cart .ab-storefront-action,"
                + " .o_wsale_my_cart a,"
                + " a[href*='/shop/cart']"
            ),
        ];
        return targets.find((target) => this.hasVisibleRect(target)) || null;
    }

    flyImageToTarget(image, targetElement) {
        const start = image.getBoundingClientRect();
        const target = targetElement.getBoundingClientRect();
        const flyer = image.cloneNode(false);
        const endSize = Math.max(26, Math.min(46, Math.min(start.width, start.height) * 0.24));
        const startCenterX = start.left + start.width / 2;
        const startCenterY = start.top + start.height / 2;
        const endX = target.left + target.width / 2 - startCenterX;
        const endY = target.top + target.height / 2 - startCenterY;
        const liftY = Math.min(-90, endY * 0.28 - 70);

        flyer.className = "ab-storefront-cart-flyer";
        flyer.alt = "";
        Object.assign(flyer.style, {
            left: `${start.left}px`,
            top: `${start.top}px`,
            width: `${start.width}px`,
            height: `${start.height}px`,
        });
        document.body.appendChild(flyer);

        const animation = flyer.animate([
            { opacity: 1, transform: "translate3d(0, 0, 0) scale(1)", offset: 0 },
            {
                opacity: .96,
                transform: `translate3d(${endX * .34}px, ${liftY}px, 0) scale(.72) rotate(-2deg)`,
                offset: .38,
            },
            {
                opacity: .92,
                transform: `translate3d(${endX * .78}px, ${endY * .74}px, 0) scale(.34) rotate(3deg)`,
                offset: .78,
            },
            {
                opacity: 0,
                transform: `translate3d(${endX}px, ${endY}px, 0) scale(${endSize / Math.max(start.width, start.height)}) rotate(0deg)`,
                offset: 1,
            },
        ], {
            duration: CARD_FLY_DURATION,
            easing: "cubic-bezier(.16, 1, .3, 1)",
            fill: "forwards",
        });

        animation.addEventListener("finish", () => {
            flyer.remove();
            this.bounceTarget(targetElement);
        }, { once: true });
        animation.addEventListener("cancel", () => flyer.remove(), { once: true });
    }

    bounceTarget(target) {
        target.classList.remove("ab-storefront-cart-bounce");
        void target.offsetWidth;
        target.classList.add("ab-storefront-cart-bounce");
        window.setTimeout(() => target.classList.remove("ab-storefront-cart-bounce"), 620);
    }

    showButtonPulse(button) {
        button.classList.remove("ab-storefront-addcart-press", "ab-storefront-addcart-success");
        void button.offsetWidth;
        button.classList.add("ab-storefront-addcart-success");
        window.setTimeout(() => button.classList.remove("ab-storefront-addcart-success"), 820);
    }

    showToast({ image, title, action }) {
        const toast = document.createElement("div");
        toast.className = `ab-storefront-action-toast ab-storefront-action-toast-${action}`;

        const media = document.createElement("span");
        media.className = "ab-storefront-action-toast-media";
        const logoSrc = this.getWebsiteLogoSrc();
        const imageSrc = image?.currentSrc || image?.src || "";
        if (action === "cart") {
            media.classList.add("ab-storefront-cart-toast-motion");
            media.append(
                document.createElement("span"),
                document.createElement("span"),
                document.createElement("span")
            );
        } else {
            media.classList.add("ab-storefront-toast-logo-motion");
        }
        if (action !== "cart" && (logoSrc || imageSrc)) {
            const toastImage = document.createElement("img");
            toastImage.src = logoSrc || imageSrc;
            toastImage.alt = "";
            toastImage.loading = "lazy";
            media.appendChild(toastImage);
        } else if (action !== "cart") {
            const iconWrap = document.createElement("span");
            iconWrap.className = "ab-storefront-action-toast-icon";
            const icon = document.createElement("i");
            icon.className = `fa ${action === "wishlist" ? "fa-heart" : "fa-shopping-cart"}`;
            iconWrap.appendChild(icon);
            media.appendChild(iconWrap);
        }

        const copy = document.createElement("span");
        copy.className = "ab-storefront-action-toast-copy";
        const heading = document.createElement("strong");
        heading.textContent = action === "wishlist" ? _t("Added to wishlist") : _t("Added to cart");
        const detail = document.createElement("small");
        detail.textContent = title || _t("Product saved");
        copy.append(heading, detail);

        const check = document.createElement("span");
        check.className = "ab-storefront-action-toast-check";
        const checkIcon = document.createElement("i");
        checkIcon.className = "fa fa-check";
        check.appendChild(checkIcon);

        toast.append(media, copy, check);
        document.body.appendChild(toast);
        requestAnimationFrame(() => toast.classList.add("is-visible"));
        window.setTimeout(() => {
            toast.classList.remove("is-visible");
            window.setTimeout(() => toast.remove(), 260);
        }, 2400);
    }

    getWebsiteLogoSrc() {
        const logo = document.querySelector(".ab-storefront-brand-logo img, .ab-storefront-brand img");
        return logo?.currentSrc || logo?.src || "";
    }
}

registry
    .category("public.interactions")
    .add("ab_ecommerce_storefront.product_card", AbStorefrontProductCard);
