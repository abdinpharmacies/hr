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
        if (this.dialog) {
            this.dialog.close();
            this.dialog.remove();
            document.documentElement.classList.remove("ab-storefront-second-picker-open");
        }
    }

    async onOpen(event) {
        event.preventDefault();
        if (this.el.disabled || this.dialog) {
            return;
        }
        const container = this.el.closest(".ab-storefront-product-card, #product_detail");
        const purchaseInput = container?.querySelector('input[name="add_qty"]');
        const desiredQuantity = Number(purchaseInput?.value);
        const minimumQuantity = Math.max(
            Number(this.el.dataset.buyQty) || Number(purchaseInput?.min) || 1,
            1,
        );
        this.purchaseQuantity = purchaseInput
            ? Math.max(Number.isInteger(desiredQuantity) ? desiredQuantity : minimumQuantity, minimumQuantity)
            : null;
        if (purchaseInput) {
            purchaseInput.value = String(this.purchaseQuantity);
        }
        if (["same", "auto_cheapest"].includes(this.el.dataset.offerMode)) {
            await this.addOffer();
            return;
        }
        const selectedId = Number(container?.querySelector(".ab-storefront-benefit-options")?.dataset.selectedBenefitId);
        if (selectedId && this.el.dataset.pickerOnly !== "true" && this.el.dataset.offerType !== "gift") {
            await this.addOffer(selectedId);
            return;
        }
        this.initialSelectedId = selectedId;
        this.openPicker();
        await this.loadItems();
    }

    openPicker() {
        this.dialog?.remove();
        this.giftAllocations = null;
        this.giftRows = new Map();
        this.isGift = false;
        this.dialog = element("dialog", "ab-storefront-second-picker");
        this.dialog.setAttribute("aria-labelledby", "ab-second-picker-title");
        const panel = element("div", "ab-storefront-second-picker-panel");
        const header = element("div", "ab-storefront-second-picker-header");
        const title = element("h2", "", _t("Choose your benefit product"));
        title.id = "ab-second-picker-title";
        this.dialogTitle = title;
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
        this.giftSummary = element("div", "ab-storefront-second-picker-summary");
        this.giftSummary.hidden = true;
        this.giftSummary.append(element("span", "", _t("Gifts selected")));
        this.giftCount = element("strong", "", "0 / 0");
        this.giftCount.setAttribute("aria-live", "polite");
        this.giftCount.style.direction = "ltr";
        this.giftSummary.append(this.giftCount);
        this.list = element("div", "ab-storefront-second-picker-list");
        this.more = element("button", "ab-storefront-second-picker-more btn btn-outline-primary", _t("Show more"));
        this.more.type = "button";
        this.more.hidden = true;
        this.more.addEventListener("click", () => this.loadItems(true));
        this.confirm = element("button", "ab-storefront-second-picker-confirm btn btn-primary", _t("Add selected gifts to cart"));
        this.confirm.type = "button";
        this.confirm.hidden = true;
        this.confirm.disabled = true;
        this.confirm.addEventListener("click", () => this.addOffer());
        panel.append(header, description, this.giftSummary, this.search, this.message, this.list, this.more, this.confirm);
        this.dialog.append(panel);
        this.dialog.addEventListener("close", () => {
            window.clearTimeout(this.searchTimer);
            this.dialog.remove();
            this.dialog = null;
            document.documentElement.classList.remove("ab-storefront-second-picker-open");
        });
        document.body.append(this.dialog);
        this.dialog.showModal();
        document.documentElement.classList.add("ab-storefront-second-picker-open");
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
                offer_id: offerId, search, offset, purchase_quantity: this.purchaseQuantity,
            }));
            if (!this.dialog || requestNumber !== this.requestNumber) {
                return;
            }
            if (!append) {
                this.list.replaceChildren();
                this.giftRows = new Map();
            }
            this.isGift = response.offer_type === "gift";
            this.dialogTitle.textContent = this.isGift ? _t("Choose your gifts") : _t("Choose your benefit product");
            if (this.isGift) {
                this.giftSlots = response.gift_slots;
                if (!this.giftAllocations) {
                    this.giftAllocations = new Map(
                        Object.entries(response.allocations).map(([id, quantity]) => [Number(id), quantity]),
                    );
                    if (!this.giftAllocations.size && this.initialSelectedId) {
                        this.giftAllocations.set(this.initialSelectedId, Math.min(1, this.giftSlots));
                    }
                }
            }
            this.giftSummary.hidden = !this.isGift;
            this.confirm.hidden = !this.isGift;
            for (const item of response.items) {
                if (this.isGift) {
                    this.renderGiftItem(item);
                    continue;
                }
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
            if (this.isGift) {
                this.updateGiftSelection();
            }
        } catch {
            if (this.dialog) {
                this.message.textContent = _t("Could not load eligible items. Please try again.");
            }
        }
    }

    renderGiftItem(item) {
        const row = element("div", "ab-storefront-second-picker-item ab-storefront-second-picker-gift");
        const image = element("img", "");
        image.src = item.image;
        image.alt = "";
        image.loading = "lazy";
        const copy = element("div", "ab-storefront-second-picker-item-copy");
        copy.append(element("strong", "", item.name), element("span", "", _t("Free gift")));
        const controls = element("div", "ab-storefront-second-picker-controls");
        const slider = element("input", "ab-storefront-second-picker-slider");
        slider.type = "range";
        slider.min = "0";
        slider.max = String(this.giftSlots);
        slider.step = "1";
        slider.setAttribute("aria-label", `${_t("Gift quantity")}: ${item.name}`);
        slider.addEventListener("input", () => this.setGiftQuantity(item.id, Number(slider.value)));
        const stepper = element("div", "ab-storefront-second-picker-stepper");
        const minus = element("button", "ab-storefront-second-picker-step", "−");
        minus.type = "button";
        minus.setAttribute("aria-label", `${_t("Remove one gift")}: ${item.name}`);
        minus.addEventListener("click", () => this.setGiftQuantity(item.id, (this.giftAllocations.get(item.id) || 0) - 1));
        const count = element("output", "ab-storefront-second-picker-quantity", "0");
        const plus = element("button", "ab-storefront-second-picker-step", "+");
        plus.type = "button";
        plus.setAttribute("aria-label", `${_t("Add one gift")}: ${item.name}`);
        plus.addEventListener("click", () => this.setGiftQuantity(item.id, (this.giftAllocations.get(item.id) || 0) + 1));
        stepper.append(minus, count, plus);
        controls.append(slider, stepper);
        row.append(image, copy, controls);
        this.giftRows.set(item.id, { row, slider, count, minus, plus });
        this.list.append(row);
    }

    setGiftQuantity(productId, quantity) {
        const current = this.giftAllocations.get(productId) || 0;
        const otherTotal = [...this.giftAllocations.values()].reduce((sum, value) => sum + value, 0) - current;
        const allowed = Math.max(0, Math.min(this.giftSlots - otherTotal, quantity));
        if (allowed) {
            this.giftAllocations.set(productId, allowed);
        } else {
            this.giftAllocations.delete(productId);
        }
        this.updateGiftSelection();
    }

    updateGiftSelection() {
        const selected = [...this.giftAllocations.values()].reduce((sum, value) => sum + value, 0);
        this.giftCount.textContent = `${selected} / ${this.giftSlots}`;
        this.confirm.disabled = selected !== this.giftSlots || !selected;
        for (const [productId, controls] of this.giftRows) {
            const quantity = this.giftAllocations.get(productId) || 0;
            controls.slider.value = String(quantity);
            controls.slider.style.setProperty("--ab-fill", `${this.giftSlots ? quantity * 100 / this.giftSlots : 0}%`);
            controls.count.value = String(quantity);
            controls.minus.disabled = !quantity;
            controls.plus.disabled = selected >= this.giftSlots;
            controls.row.classList.toggle("is-selected", Boolean(quantity));
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
        if (this.isGift) {
            this.confirm.disabled = true;
            this.confirm.textContent = _t("Adding offer...");
        }
        try {
            const payload = {
                offer_id: Number(button.dataset.offerId),
                second_product_id: secondProductId,
                purchase_quantity: this.purchaseQuantity,
                primary_product_id: Number(button.dataset.primaryProductId) || null,
            };
            if (this.isGift) {
                payload.gift_allocations = [...this.giftAllocations].map(([product_id, quantity]) => ({
                    product_id, quantity,
                }));
            }
            const result = await this.waitFor(rpc("/shop/offer/add-second-item", payload));
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
            if (this.isGift) {
                this.confirm.textContent = _t("Add selected gifts to cart");
                this.updateGiftSelection();
            }
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
        const trigger = offer.querySelector(
            ".ab-storefront-second-offer-trigger[data-offer-mode='choice'], " +
            ".ab-storefront-second-offer-trigger[data-offer-mode='auto_cheapest']",
        );
        if (trigger) {
            event.preventDefault();
            event.stopImmediatePropagation();
            trigger.click();
        }
    }
}

registry.category("public.interactions").add("ab_ecommerce_storefront.product_offer_cart", StorefrontProductOfferCart);
