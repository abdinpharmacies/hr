/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { registry } from "@web/core/registry";
import { Interaction } from "@web/public/interaction";

function element(tag, className, textValue) {
    const node = document.createElement(tag);
    node.className = className;
    if (textValue !== undefined) {
        node.textContent = textValue;
    }
    return node;
}

export class StorefrontSecondItemOffer extends Interaction {
    static selector = ".ab-storefront-second-offer-trigger";

    setup() {
        this.onOpen = this.onOpen.bind(this);
    }

    start() {
        this.el.addEventListener("click", this.onOpen);
    }

    destroy() {
        this.el.removeEventListener("click", this.onOpen);
        this.dialog?.close();
        this.dialog?.remove();
    }

    async onOpen(event) {
        event.preventDefault();
        if (this.el.disabled || this.dialog) {
            return;
        }
        if (this.el.dataset.offerMode === "same") {
            await this.addOffer();
            return;
        }
        const container = this.el.closest(".ab-storefront-product-card, #product_detail");
        const selectedId = Number(container?.querySelector(".ab-storefront-benefit-options")?.dataset.selectedBenefitId);
        if (selectedId && this.el.dataset.pickerOnly !== "true") {
            await this.addOffer(selectedId);
            return;
        }
        this.openPicker();
        await this.loadItems();
    }

    openPicker() {
        this.dialog?.remove();
        this.dialog = element("dialog", "ab-storefront-second-picker");
        this.dialog.setAttribute("aria-labelledby", "ab-second-picker-title");
        const panel = element("div", "ab-storefront-second-picker-panel");
        const header = element("div", "ab-storefront-second-picker-header");
        const title = element("h2", "", _t("Choose your benefit product"));
        title.id = "ab-second-picker-title";
        const close = element("button", "ab-storefront-second-picker-close", "×");
        close.type = "button";
        close.setAttribute("aria-label", _t("Close"));
        close.addEventListener("click", () => this.dialog.close());
        header.append(title, close);
        const description = element("p", "ab-storefront-second-picker-description", this.el.dataset.offerDescription);
        this.search = element("input", "ab-storefront-second-picker-search");
        this.search.type = "search";
        this.search.placeholder = _t("Search eligible items");
        this.search.setAttribute("aria-label", _t("Search eligible items"));
        this.search.addEventListener("input", () => {
            window.clearTimeout(this.searchTimer);
            this.searchTimer = window.setTimeout(() => this.loadItems(), 250);
        });
        this.message = element("p", "ab-storefront-second-picker-message");
        this.message.setAttribute("role", "status");
        this.list = element("div", "ab-storefront-second-picker-list");
        this.more = element("button", "ab-storefront-second-picker-more btn btn-outline-primary", _t("Show more"));
        this.more.type = "button";
        this.more.hidden = true;
        this.more.addEventListener("click", () => this.loadItems(true));
        panel.append(header, description, this.search, this.message, this.list, this.more);
        this.dialog.append(panel);
        this.dialog.addEventListener("close", () => {
            window.clearTimeout(this.searchTimer);
            this.dialog.remove();
            this.dialog = null;
        });
        document.body.append(this.dialog);
        this.dialog.showModal();
    }

    async loadItems(append = false) {
        const offerId = Number(this.el.dataset.offerId);
        const search = this.search.value.trim();
        const offset = append ? this.list.children.length : 0;
        const requestNumber = this.requestNumber = (this.requestNumber || 0) + 1;
        this.message.textContent = _t("Loading eligible items...");
        this.more.hidden = true;
        try {
            const response = await this.waitFor(rpc("/shop/offer/second-items", {
                offer_id: offerId, search, offset,
            }));
            if (!this.dialog || requestNumber !== this.requestNumber) {
                return;
            }
            if (!append) {
                this.list.replaceChildren();
            }
            for (const item of response.items) {
                const row = element("button", "ab-storefront-second-picker-item");
                row.type = "button";
                const image = element("img", "");
                image.src = item.image;
                image.alt = "";
                image.loading = "lazy";
                const copy = element("span", "ab-storefront-second-picker-item-copy");
                copy.append(
                    element("strong", "", item.name),
                    element("span", "", `${item.price} → ${item.discounted_price}`),
                );
                row.append(image, copy);
                row.addEventListener("click", () => this.addOffer(item.id));
                this.list.append(row);
            }
            this.message.textContent = this.list.children.length ? "" : _t("No eligible items found. Try another search.");
            this.more.hidden = !response.has_more;
        } catch {
            if (this.dialog) {
                this.message.textContent = _t("Could not load eligible items. Please try again.");
            }
        }
    }

    async addOffer(secondProductId = null) {
        if (this.adding) {
            return;
        }
        this.adding = true;
        const button = this.el;
        const previousLabel = button.textContent;
        const isIconButton = button.classList.contains("ab-storefront-card-add");
        button.disabled = true;
        button.setAttribute("aria-busy", "true");
        if (!isIconButton) {
            button.textContent = _t("Adding offer...");
        }
        if (this.message) {
            this.message.textContent = _t("Adding offer...");
        }
        this.list?.querySelectorAll("button").forEach((item) => item.disabled = true);
        try {
            const result = await this.waitFor(rpc("/shop/offer/add-second-item", {
                offer_id: Number(button.dataset.offerId),
                second_product_id: secondProductId,
            }));
            window.location.assign(result.url);
        } catch {
            if (this.message) {
                this.message.textContent = _t("Could not add the offer. Check availability and try again.");
            } else {
                let feedback = button.parentElement.querySelector(".ab-storefront-second-offer-feedback");
                if (!feedback) {
                    feedback = element("span", "ab-storefront-second-offer-feedback");
                    feedback.setAttribute("role", "status");
                    button.parentElement.after(feedback);
                }
                feedback.textContent = _t("Could not add the offer. Check availability and try again.");
            }
        } finally {
            this.adding = false;
            this.list?.querySelectorAll("button").forEach((item) => item.disabled = false);
            button.disabled = false;
            button.setAttribute("aria-busy", "false");
            if (!isIconButton) {
                button.textContent = previousLabel;
            }
        }
    }
}

registry.category("public.interactions").add("ab_ecommerce_storefront.second_item_offer", StorefrontSecondItemOffer);

export class StorefrontBenefitOptions extends Interaction {
    static selector = ".ab-storefront-benefit-options";

    setup() {
        this.onSelect = this.onSelect.bind(this);
    }

    start() {
        this.el.addEventListener("click", this.onSelect);
    }

    destroy() {
        this.el.removeEventListener("click", this.onSelect);
    }

    onSelect(event) {
        const option = event.target.closest(".ab-storefront-benefit-option");
        if (!option || !this.el.contains(option)) {
            return;
        }
        const selected = option.getAttribute("aria-pressed") !== "true";
        for (const item of this.el.querySelectorAll(".ab-storefront-benefit-option")) {
            item.setAttribute("aria-pressed", String(selected && item === option));
        }
        this.el.dataset.selectedBenefitId = selected ? option.dataset.benefitId : "";
    }
}

registry.category("public.interactions").add("ab_ecommerce_storefront.benefit_options", StorefrontBenefitOptions);

export class StorefrontProductOfferCart extends Interaction {
    static selector = ".ab-storefront-product-page #product_detail";

    setup() {
        this.onCartClick = this.onCartClick.bind(this);
    }

    start() {
        this.el.addEventListener("click", this.onCartClick, true);
    }

    destroy() {
        this.el.removeEventListener("click", this.onCartClick, true);
    }

    onCartClick(event) {
        const button = event.target.closest("#add_to_cart, .o_we_buy_now");
        if (!button || !this.el.contains(button)) {
            return;
        }
        const offer = this.el.querySelector(".ab-storefront-product-second-offer[data-primary-product-id]");
        const productId = this.el.querySelector("input[name='product_id']")?.value;
        if (!offer || offer.dataset.primaryProductId !== productId) {
            return;
        }
        const trigger = offer.querySelector(".ab-storefront-second-offer-trigger[data-offer-mode='choice']");
        if (trigger) {
            event.preventDefault();
            event.stopImmediatePropagation();
            trigger.click();
        }
    }
}

registry.category("public.interactions").add("ab_ecommerce_storefront.product_offer_cart", StorefrontProductOfferCart);
