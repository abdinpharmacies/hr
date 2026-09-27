/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { registry } from "@web/core/registry";
import { Interaction } from "@web/public/interaction";

const STORAGE_KEY = "ab_ecommerce_storefront.recently_viewed.v1";
const MAX_HISTORY_SIZE = 30;
const PAGE_BATCH_SIZE = 12;
const REMOVE_ANIMATION_DURATION = 1180;
const REMOVE_SUCCESS_DURATION = 860;
const REMOVE_EXIT_DURATION = 280;
const MAX_REMOVE_PARTICLES = 1100;

function sleep(ms) {
    return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function normalizeProductId(value) {
    const productId = parseInt(value, 10);
    return Number.isFinite(productId) && productId > 0 ? productId : 0;
}

function readLocalHistory() {
    try {
        const raw = window.localStorage.getItem(STORAGE_KEY);
        const items = JSON.parse(raw || "[]");
        if (!Array.isArray(items)) {
            return [];
        }
        const seen = new Set();
        const history = [];
        for (const item of items) {
            const productId = normalizeProductId(item?.product_id ?? item);
            if (!productId || seen.has(productId)) {
                continue;
            }
            seen.add(productId);
            history.push({ product_id: productId });
            if (history.length >= MAX_HISTORY_SIZE) {
                break;
            }
        }
        return history;
    } catch {
        return [];
    }
}

function writeLocalHistory(history) {
    try {
        window.localStorage.setItem(
            STORAGE_KEY,
            JSON.stringify(history.slice(0, MAX_HISTORY_SIZE).map((item) => ({
                product_id: normalizeProductId(item.product_id),
            })).filter((item) => item.product_id)),
        );
        return true;
    } catch {
        return false;
    }
}

function clearLocalHistory() {
    try {
        window.localStorage.removeItem(STORAGE_KEY);
        return true;
    } catch {
        return false;
    }
}

function localProductIds() {
    return readLocalHistory().map((item) => item.product_id);
}

function rememberLocalProduct(productId) {
    productId = normalizeProductId(productId);
    if (!productId) {
        return [];
    }
    const nextHistory = [
        { product_id: productId },
        ...readLocalHistory().filter((item) => item.product_id !== productId),
    ].slice(0, MAX_HISTORY_SIZE);
    writeLocalHistory(nextHistory);
    return nextHistory;
}

function removeLocalProduct(productId) {
    productId = normalizeProductId(productId);
    if (!productId) {
        return false;
    }
    const nextHistory = readLocalHistory().filter((item) => item.product_id !== productId);
    return writeLocalHistory(nextHistory);
}

function easeOutCubic(value) {
    return 1 - Math.pow(1 - value, 3);
}

function easeInOutCubic(value) {
    return value < .5 ? 4 * value * value * value : 1 - Math.pow(-2 * value + 2, 3) / 2;
}

function clamp(value, minimum = 0, maximum = 1) {
    return Math.min(maximum, Math.max(minimum, value));
}

function prefersReducedMotion() {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function imageElementForCard(card) {
    return card.querySelector(".ab-storefront-product-media img");
}

function productMediaForCard(card) {
    return card.querySelector(".ab-storefront-product-media");
}

function buildImageParticles(image, width, height) {
    const sampleCanvas = document.createElement("canvas");
    const sampleWidth = Math.min(156, Math.max(56, Math.round(width)));
    const sampleHeight = Math.max(48, Math.round(sampleWidth * height / Math.max(width, 1)));
    sampleCanvas.width = sampleWidth;
    sampleCanvas.height = sampleHeight;
    const sampleContext = sampleCanvas.getContext("2d", { willReadFrequently: true });
    if (!sampleContext) {
        return [];
    }
    sampleContext.drawImage(image, 0, 0, sampleWidth, sampleHeight);
    const pixels = sampleContext.getImageData(0, 0, sampleWidth, sampleHeight).data;
    const particles = [];
    const step = Math.max(4, Math.round(Math.sqrt((sampleWidth * sampleHeight) / MAX_REMOVE_PARTICLES)));
    const centerX = width / 2;
    const centerY = height / 2;

    for (let y = 0; y < sampleHeight; y += step) {
        for (let x = 0; x < sampleWidth; x += step) {
            const index = (y * sampleWidth + x) * 4;
            const alpha = pixels[index + 3];
            if (alpha < 24) {
                continue;
            }
            const red = pixels[index];
            const green = pixels[index + 1];
            const blue = pixels[index + 2];
            const luminance = red * .299 + green * .587 + blue * .114;
            const saturation = Math.max(red, green, blue) - Math.min(red, green, blue);
            if (luminance > 240 && saturation < 20) {
                continue;
            }
            const px = (x / sampleWidth) * width;
            const py = (y / sampleHeight) * height;
            const dx = px - centerX;
            const dy = py - centerY;
            particles.push({
                x: px,
                y: py,
                radius: Math.hypot(dx, dy),
                angle: Math.atan2(dy, dx),
                color: `rgb(${red}, ${green}, ${blue})`,
                luminance,
                saturation,
                size: Math.max(1.5, step * width / sampleWidth),
                spin: 4.6 + Math.random() * 3.8,
                drift: (Math.random() - .5) * 14,
                burstAngle: Math.atan2(dy, dx) + (Math.random() - .5) * .9,
                burstDistance: Math.min(width, height) * (.36 + Math.random() * .62),
                burstSize: .65 + Math.random() * 1.4,
                bursts: Math.random() > .72,
            });
        }
    }
    return particles.slice(0, MAX_REMOVE_PARTICLES);
}

function particlePalette(particles) {
    const palette = [];
    const buckets = new Set();
    const colorCandidates = [...particles].sort((first, second) => (
        second.saturation * 1.6 + Math.abs(160 - second.luminance) * .24
        - first.saturation * 1.6 - Math.abs(160 - first.luminance) * .24
    ));
    for (const particle of colorCandidates) {
        const channels = particle.color.match(/\d+/g)?.map(Number) || [];
        const bucket = channels.map((channel) => Math.round(channel / 40)).join("-");
        if (bucket && !buckets.has(bucket)) {
            buckets.add(bucket);
            palette.push(particle.color);
        }
        if (palette.length >= 7) {
            break;
        }
    }
    return palette.length ? palette : ["rgb(0, 127, 79)", "rgb(220, 35, 55)", "rgb(21, 91, 177)"];
}

function animateVortexDissolve(card) {
    const media = productMediaForCard(card);
    const image = imageElementForCard(card);
    if (!media || !image || !image.complete || !image.naturalWidth) {
        return sleep(REMOVE_ANIMATION_DURATION * .55);
    }

    const rect = media.getBoundingClientRect();
    if (!rect.width || !rect.height) {
        return sleep(REMOVE_ANIMATION_DURATION * .55);
    }

    if (prefersReducedMotion()) {
        image.classList.add("ab-storefront-history-image-fading");
        return sleep(260);
    }

    const pixelRatio = Math.min(window.devicePixelRatio || 1, 2);
    const canvas = document.createElement("canvas");
    canvas.className = "ab-storefront-history-particle-canvas";
    canvas.width = Math.round(rect.width * pixelRatio);
    canvas.height = Math.round(rect.height * pixelRatio);
    media.appendChild(canvas);

    const context = canvas.getContext("2d");
    if (!context) {
        canvas.remove();
        return sleep(REMOVE_ANIMATION_DURATION * .55);
    }
    context.scale(pixelRatio, pixelRatio);

    let particles = [];
    try {
        particles = buildImageParticles(image, rect.width, rect.height);
    } catch {
        particles = [];
    }
    image.classList.add("ab-storefront-history-image-fading");
    if (!particles.length) {
        return sleep(REMOVE_ANIMATION_DURATION * .55).finally(() => canvas.remove());
    }

    const centerX = rect.width / 2;
    const centerY = rect.height / 2;
    const startedAt = performance.now();
    const palette = particlePalette(particles);
    const maximumRadius = Math.min(rect.width, rect.height) * .48;

    return new Promise((resolve) => {
        const frame = (now) => {
            const progress = Math.min(1, (now - startedAt) / REMOVE_ANIMATION_DURATION);
            const collapse = easeInOutCubic(clamp(progress / .7));
            const burst = easeOutCubic(clamp((progress - .5) / .5));
            const vortexLife = Math.sin(Math.PI * clamp((progress - .02) / .88));
            context.clearRect(0, 0, rect.width, rect.height);
            context.globalCompositeOperation = "source-over";

            // Wide, product-colored ribbons make the inward pull readable before
            // the finer pixels collapse into the center.
            context.save();
            context.translate(centerX, centerY);
            context.rotate(collapse * 4.8);
            context.globalCompositeOperation = "lighter";
            for (let index = 0; index < palette.length; index += 1) {
                const start = (index / palette.length) * Math.PI * 2 + collapse * 1.7;
                context.strokeStyle = palette[index];
                context.globalAlpha = vortexLife * (.48 + (index % 3) * .12);
                context.lineWidth = Math.max(2, (11 - index * .7) * (1 - burst * .76));
                context.lineCap = "round";
                context.beginPath();
                for (let point = 0; point <= 34; point += 1) {
                    const ratio = point / 34;
                    const angle = start + ratio * Math.PI * (2.1 + collapse * 1.5);
                    const radius = (8 + ratio * maximumRadius) * (1 - collapse * .72);
                    const x = Math.cos(angle) * radius;
                    const y = Math.sin(angle) * radius * .76;
                    if (!point) {
                        context.moveTo(x, y);
                    } else {
                        context.lineTo(x, y);
                    }
                }
                context.stroke();
            }
            context.restore();

            for (const particle of particles) {
                const inward = Math.pow(1 - collapse, 1.72);
                const angle = particle.angle + particle.spin * collapse;
                const radius = particle.radius * inward;
                let x = centerX + Math.cos(angle) * radius;
                let y = centerY + Math.sin(angle) * radius + particle.drift * collapse;
                let alpha = Math.pow(1 - clamp(progress / .82), .72);
                let size = particle.size * (.42 + inward);

                if (particle.bursts && burst > 0) {
                    const burstLife = Math.sin(Math.PI * burst);
                    x = centerX + Math.cos(particle.burstAngle) * particle.burstDistance * burst;
                    y = centerY + Math.sin(particle.burstAngle) * particle.burstDistance * burst;
                    alpha = burstLife * .96;
                    size = particle.size * particle.burstSize * (1 - burst * .38);
                }

                context.globalAlpha = alpha;
                context.fillStyle = particle.color;
                context.shadowColor = particle.color;
                context.shadowBlur = particle.bursts ? 5 * (1 - burst) : 0;
                context.beginPath();
                context.ellipse(x, y, size, size * (particle.bursts ? 2.7 : 1), particle.burstAngle, 0, Math.PI * 2);
                context.fill();
            }
            context.shadowBlur = 0;

            if (progress > .43 && progress < .88) {
                const flashLife = Math.sin(Math.PI * clamp((progress - .43) / .45));
                const flash = context.createRadialGradient(centerX, centerY, 0, centerX, centerY, maximumRadius * .42);
                flash.addColorStop(0, `rgba(255, 255, 255, ${flashLife * .95})`);
                flash.addColorStop(.24, `rgba(137, 231, 187, ${flashLife * .72})`);
                flash.addColorStop(1, "rgba(0, 127, 79, 0)");
                context.globalCompositeOperation = "lighter";
                context.globalAlpha = 1;
                context.fillStyle = flash;
                context.beginPath();
                context.arc(centerX, centerY, maximumRadius * .42, 0, Math.PI * 2);
                context.fill();
            }

            if (progress < 1) {
                window.requestAnimationFrame(frame);
                return;
            }
            context.globalAlpha = 1;
            canvas.remove();
            resolve();
        };
        window.requestAnimationFrame(frame);
    });
}

function showRemovalSuccess(card) {
    const form = card.querySelector(".ab-storefront-product-card");
    if (!form) {
        return sleep(REMOVE_SUCCESS_DURATION);
    }
    const success = document.createElement("div");
    success.className = "ab-storefront-history-success";
    success.setAttribute("role", "status");
    success.setAttribute("aria-live", "polite");
    const icon = document.createElement("span");
    icon.className = "ab-storefront-history-success-icon";
    icon.setAttribute("aria-hidden", "true");
    const bagIcon = document.createElement("i");
    bagIcon.className = "fa fa-shopping-bag";
    const checkIcon = document.createElement("i");
    checkIcon.className = "fa fa-check ab-storefront-history-success-check";
    icon.append(bagIcon, checkIcon);
    const title = document.createElement("strong");
    title.textContent = _t("Successfully removed");
    const text = document.createElement("span");
    text.textContent = _t("Product removed from your list");
    success.append(icon, title, text);
    form.appendChild(success);
    card.classList.add("is-success");
    window.requestAnimationFrame(() => success.classList.add("is-visible"));
    return sleep(REMOVE_SUCCESS_DURATION);
}

async function exitRemovedCard(card) {
    if (prefersReducedMotion()) {
        card.remove();
        return;
    }
    card.classList.add("is-leaving");
    await sleep(REMOVE_EXIT_DURATION);
    card.remove();
}

export class AbStorefrontBrowsingHistoryTracker extends Interaction {
    static selector = "[data-ab-history-product-id]";

    start() {
        const productId = normalizeProductId(this.el.dataset.abHistoryProductId);
        if (!productId || this.el.dataset.abHistoryRecorded === "1") {
            return;
        }
        this.el.dataset.abHistoryRecorded = "1";
        rememberLocalProduct(productId);
        this.recordServerView(productId);
    }

    async recordServerView(productId) {
        try {
            await this.waitFor(rpc("/ab/storefront/browsing-history/record", {
                product_id: productId,
            }));
        } catch {
            // Guest history is already kept locally; server errors should not
            // interrupt product browsing.
        }
    }
}

export class AbStorefrontBrowsingHistorySurface extends Interaction {
    static selector = "[data-ab-history-rail], [data-ab-history-page]";
    dynamicContent = {
        "[data-ab-history-clear]": { "t-on-click.prevent": this.onClearHistory },
        "[data-ab-history-remove]": { "t-on-click.prevent": this.onRemoveProduct },
        "[data-ab-history-search]": { "t-on-input": this.onSearch },
        "[data-ab-history-load-more]": { "t-on-click.prevent": this.onLoadMore },
    };

    setup() {
        this.visibleCount = PAGE_BATCH_SIZE;
        this.clearPrimed = false;
    }

    async start() {
        this.productsNode = this.el.querySelector("[data-ab-history-products]");
        this.skeletonNode = this.el.querySelector("[data-ab-history-skeleton]");
        this.statusNode = this.el.querySelector("[data-ab-history-status]");
        this.emptyNode = this.el.querySelector("[data-ab-history-empty]");
        this.noResultsNode = this.el.querySelector("[data-ab-history-no-results]");
        this.clearButton = this.el.querySelector("[data-ab-history-clear]");
        this.loadMoreButton = this.el.querySelector("[data-ab-history-load-more]");
        this.countNode = this.el.querySelector("[data-ab-history-count]");
        this.searchInput = this.el.querySelector("[data-ab-history-search]");
        this.isPage = this.el.matches("[data-ab-history-page]");
        await this.loadHistory();
    }

    async loadHistory() {
        this.setLoading(true);
        await this.syncLocalHistory();
        const productIds = localProductIds();
        const excludeIds = this.getExcludeIds();
        try {
            const response = await this.waitFor(rpc("/ab/storefront/browsing-history/cards", {
                product_ids: productIds,
                limit: this.getLimit(),
                exclude_ids: excludeIds,
            }));
            this.renderHistory(response || {});
        } catch {
            this.renderError();
        } finally {
            this.setLoading(false);
        }
    }

    async syncLocalHistory() {
        const productIds = localProductIds();
        if (!productIds.length) {
            return;
        }
        try {
            const response = await this.waitFor(rpc("/ab/storefront/browsing-history/sync", {
                product_ids: productIds,
            }));
            if (response?.synced) {
                clearLocalHistory();
            }
        } catch {
            // Keep local history intact so it can be retried later.
        }
    }

    renderHistory(response) {
        const html = response.html || "";
        const hasProducts = Boolean(html && response.count);
        if (!hasProducts) {
            this.productsNode.innerHTML = "";
            this.updateCount(0);
            this.clearButton?.setAttribute("disabled", "disabled");
            if (this.isPage) {
                this.showEmpty();
            } else {
                this.hideSurface();
            }
            return;
        }
        this.el.classList.remove("d-none");
        this.emptyNode?.classList.add("d-none");
        this.noResultsNode?.classList.add("d-none");
        this.productsNode.innerHTML = html;
        this.clearButton?.removeAttribute("disabled");
        this.updateCount(response.count || 0);
        this.services["public.interactions"]?.startInteractions(this.productsNode);
        if (this.isPage) {
            this.visibleCount = PAGE_BATCH_SIZE;
            this.applyPaging();
            this.applySearch();
        }
    }

    renderError() {
        if (!this.isPage) {
            this.hideSurface();
            return;
        }
        this.productsNode.innerHTML = "";
        this.updateCount(0);
        this.clearButton?.setAttribute("disabled", "disabled");
        this.setStatus(_t("We could not load your browsing history. Please try again later."));
        this.emptyNode?.classList.add("d-none");
        this.noResultsNode?.classList.add("d-none");
    }

    showEmpty() {
        this.el.classList.remove("d-none");
        this.emptyNode?.classList.remove("d-none");
        this.noResultsNode?.classList.add("d-none");
        this.loadMoreButton?.classList.add("d-none");
    }

    hideSurface() {
        this.el.classList.add("d-none");
    }

    setLoading(isLoading) {
        this.el.classList.toggle("is-loading", isLoading);
        this.skeletonNode?.classList.toggle("d-none", !isLoading);
        if (isLoading) {
            this.setStatus(_t("Loading recently viewed products..."));
        } else {
            this.setStatus("");
        }
    }

    setStatus(message) {
        if (this.statusNode) {
            this.statusNode.textContent = message;
        }
    }

    updateCount(count) {
        if (this.countNode) {
            this.countNode.textContent = count ? _t("%s products", count) : "";
        }
    }

    currentCardCount() {
        return this.productsNode.querySelectorAll(".ab-storefront-history-card").length;
    }

    getLimit() {
        return Math.min(
            Math.max(parseInt(this.el.dataset.abHistoryLimit, 10) || MAX_HISTORY_SIZE, 1),
            MAX_HISTORY_SIZE,
        );
    }

    getExcludeIds() {
        return [normalizeProductId(this.el.dataset.abHistoryExcludeCurrent)].filter(Boolean);
    }

    onSearch() {
        this.visibleCount = PAGE_BATCH_SIZE;
        this.applySearch();
    }

    applySearch() {
        const query = (this.searchInput?.value || "").trim().toLocaleLowerCase();
        const cards = [...this.productsNode.querySelectorAll(".ab-storefront-history-card")];
        let matchedCount = 0;
        for (const card of cards) {
            const name = (
                card.dataset.abHistoryProductName
                || card.querySelector(".ab-storefront-product-name")?.textContent
                || ""
            ).toLocaleLowerCase();
            const matches = !query || name.includes(query);
            card.dataset.abHistorySearchMatch = matches ? "1" : "0";
            if (matches) {
                matchedCount += 1;
            }
        }
        this.applyPaging();
        this.noResultsNode?.classList.toggle("d-none", !query || matchedCount > 0);
    }

    applyPaging() {
        if (!this.isPage) {
            return;
        }
        const cards = [...this.productsNode.querySelectorAll(".ab-storefront-history-card")];
        let visibleMatches = 0;
        let totalMatches = 0;
        for (const card of cards) {
            const matches = card.dataset.abHistorySearchMatch !== "0";
            if (matches) {
                totalMatches += 1;
            }
            const visible = matches && visibleMatches < this.visibleCount;
            card.classList.toggle("d-none", !visible);
            if (visible) {
                visibleMatches += 1;
            }
        }
        this.loadMoreButton?.classList.toggle("d-none", totalMatches <= this.visibleCount);
    }

    onLoadMore() {
        this.visibleCount += PAGE_BATCH_SIZE;
        this.applyPaging();
    }

    async onClearHistory(ev) {
        const button = ev.currentTarget;
        if (!this.clearPrimed) {
            this.clearPrimed = true;
            button.dataset.abOriginalLabel = button.textContent.trim();
            button.textContent = _t("Click again to clear");
            window.setTimeout(() => {
                if (!button.isConnected || !this.clearPrimed) {
                    return;
                }
                this.clearPrimed = false;
                button.textContent = button.dataset.abOriginalLabel || _t("Clear history");
            }, 3200);
            return;
        }
        button.disabled = true;
        button.classList.add("is-loading");
        try {
            const response = await this.waitFor(rpc("/ab/storefront/browsing-history/clear", {}));
            if (response?.cleared) {
                clearLocalHistory();
                this.productsNode.innerHTML = "";
                this.updateCount(0);
                this.showEmpty();
            }
        } catch {
            this.setStatus(_t("Could not clear your browsing history. Please try again."));
        } finally {
            this.clearPrimed = false;
            button.classList.remove("is-loading");
            button.textContent = button.dataset.abOriginalLabel || _t("Clear history");
            button.disabled = false;
        }
    }

    async onRemoveProduct(ev) {
        const button = ev.currentTarget;
        const productId = normalizeProductId(button.dataset.abHistoryRemove);
        const card = button.closest(".ab-storefront-history-card");
        if (!productId || !card || card.classList.contains("is-removing")) {
            return;
        }
        const removeButtons = [...card.querySelectorAll("[data-ab-history-remove]")];
        button.disabled = true;
        removeButtons.forEach((removeButton) => {
            removeButton.disabled = true;
            removeButton.classList.add("is-loading");
        });
        card.classList.add("is-removing");
        try {
            const removeRequest = this.waitFor(rpc("/ab/storefront/browsing-history/remove", {
                product_id: productId,
            }));
            const animation = animateVortexDissolve(card);
            await Promise.all([removeRequest, animation]);
            removeLocalProduct(productId);
            await showRemovalSuccess(card);
            await exitRemovedCard(card);
            const count = this.currentCardCount();
            this.updateCount(count);
            if (!count) {
                this.clearButton?.setAttribute("disabled", "disabled");
                if (this.isPage) {
                    this.showEmpty();
                } else {
                    this.hideSurface();
                }
            } else if (this.isPage) {
                this.applySearch();
            }
            this.setStatus(_t("Removed from history."));
        } catch {
            removeButtons.forEach((removeButton) => {
                removeButton.disabled = false;
                removeButton.classList.remove("is-loading");
            });
            card.classList.remove("is-removing");
            imageElementForCard(card)?.classList.remove("ab-storefront-history-image-fading");
            card.querySelector(".ab-storefront-history-particle-canvas")?.remove();
            this.setStatus(_t("Could not remove this product. Please try again."));
        }
    }
}

registry
    .category("public.interactions")
    .add("ab_ecommerce_storefront.browsing_history_tracker", AbStorefrontBrowsingHistoryTracker);

registry
    .category("public.interactions")
    .add("ab_ecommerce_storefront.browsing_history_surface", AbStorefrontBrowsingHistorySurface);
