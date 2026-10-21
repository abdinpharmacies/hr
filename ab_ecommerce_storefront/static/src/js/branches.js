import { registry } from "@web/core/registry";
import { Interaction } from "@web/public/interaction";
import { loadCSS, loadJS } from "@web/core/assets";
import { _t } from "@web/core/l10n/translation";

const LIB = "/ab_ecommerce_storefront/static/lib/";
const normalize = (value) => value.toLowerCase().normalize("NFKD")
    .replace(/[\u064B-\u065F\u0670\u0640]/g, "")
    .replace(/[\u0622\u0623\u0625]/g, "\u0627")
    .replace(/\u0649/g, "\u064A").replace(/\u0629/g, "\u0647");

export class AbBranchLocator extends Interaction {
    static selector = "[data-ab-branches]";

    start() {
        this.stopped = false;
        this.listeners = new AbortController();
        this.mobile = window.matchMedia("(max-width: 767px)");
        this.search = this.el.querySelector("#ab-branch-search");
        this.region = this.el.querySelector("#ab-branch-region");
        this.workspace = this.el.querySelector("[data-branch-workspace]");
        this.list = this.el.querySelector("[data-branch-list]");
        this.profile = this.el.querySelector("[data-branch-profile]");
        this.status = this.el.querySelector("[data-branch-status]");
        this.logo = this.el.querySelector(".ab-branches-map-hint img").src;
        this.branches = [...this.list.querySelectorAll("[data-branch-id]")].map((card) => ({
            card,
            id: card.dataset.branchId,
            region: card.dataset.region,
            regionName: card.querySelector("[data-branch-region]").textContent,
            name: card.querySelector("[data-branch-name]").textContent,
            address: card.querySelector("[data-branch-address]").textContent,
            coords: [Number(card.dataset.lat), Number(card.dataset.lng)],
            search: normalize(`${card.textContent} ${card.dataset.search}`),
        }));
        const listen = (target, event, handler) => target.addEventListener(event, handler, { signal: this.listeners.signal });
        listen(this.search, "input", () => this.filter());
        listen(this.region, "change", () => this.filter());
        listen(this.el, "click", (event) => this.onClick(event));
        listen(this.profile, "cancel", (event) => { event.preventDefault(); this.closeProfile(); });
        listen(this.profile, "click", (event) => { if (event.target === this.profile) this.closeProfile(); });
        listen(document, "keydown", (event) => {
            if (event.key === "Escape" && this.profile.open) this.closeProfile();
        });
        listen(this.mobile, "change", () => {
            if (this.profile.open) {
                this.profile.close();
                this.showProfile();
            }
            this.map?.invalidateSize();
        });
        listen(window, "hashchange", () => this.openHash());
        listen(document, "ab-storefront-location:position", (event) => this.usePosition(event.detail));
        this.el.classList.add("is-enhanced");
        this.filter(false);
        this.openHash();
        this.initializeMap();
    }

    async initializeMap() {
        try {
            await Promise.all([
                loadCSS(`${LIB}leaflet/leaflet.css`),
                loadCSS(`${LIB}leaflet_markercluster/MarkerCluster.css`),
                loadJS(`${LIB}leaflet/leaflet.js`),
            ]);
            await loadJS(`${LIB}leaflet_markercluster/leaflet.markercluster.js`);
            if (this.stopped) return;
            const L = window.L;
            this.map = L.map(this.el.querySelector("[data-branch-map]"), {
                scrollWheelZoom: false,
                zoomControl: false,
                maxBounds: [[20, 22], [34, 39]],
                maxBoundsViscosity: 0.8,
                minZoom: 5,
            });
            L.control.zoom({ position: "topleft", zoomInTitle: _t("Zoom in"), zoomOutTitle: _t("Zoom out") }).addTo(this.map);
            let tileErrors = 0;
            let tileLoaded = false;
            L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
                maxZoom: 19,
                attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a>',
            }).on("tileerror", () => {
                if (++tileErrors >= 4 && !tileLoaded) {
                    this.setStatus(_t("Map tiles could not load. You can still choose a branch from the list."));
                }
            }).on("tileload", () => { tileLoaded = true; }).addTo(this.map);
            this.clusters = L.markerClusterGroup({
                showCoverageOnHover: false,
                maxClusterRadius: 48,
                animate: !window.matchMedia("(prefers-reduced-motion: reduce)").matches,
                iconCreateFunction: (cluster) => L.divIcon({
                    html: this.markerContent(cluster.getChildCount()),
                    className: "ab-branch-cluster",
                    iconSize: [58, 58],
                }),
            }).addTo(this.map);
            for (const branch of this.branches) {
                branch.marker = L.marker(branch.coords, {
                    title: branch.name,
                    alt: branch.name,
                    keyboard: true,
                    icon: L.divIcon({ html: this.markerContent(), className: "ab-branch-pin", iconSize: [52, 58], iconAnchor: [26, 56] }),
                }).on("click", () => this.selectBranch(branch));
                const tooltip = document.createElement("span");
                tooltip.textContent = branch.name;
                branch.marker.bindTooltip(tooltip, { direction: "top", offset: [0, -48] });
                branch.marker.on("add", () => {
                    const marker = branch.marker.getElement();
                    marker?.setAttribute("aria-label", branch.name);
                    marker?.setAttribute("aria-haspopup", "dialog");
                    marker?.classList.toggle("is-selected", branch === this.selected);
                });
            }
            this.filter(false);
            this.fitBranches();
            if (this.selected) this.focusBranch(this.selected);
            this.resizeObserver = new ResizeObserver(() => this.map?.invalidateSize());
            this.resizeObserver.observe(this.workspace);
        } catch {
            if (!this.stopped) {
                this.setStatus(_t("The map is unavailable right now. Browse the branches below or open directions."));
                this.el.classList.add("is-map-unavailable");
                this.setView("list");
            }
        } finally {
            if (!this.stopped) this.el.querySelector("[data-branch-loading]").hidden = true;
        }
    }

    markerContent(count) {
        const content = document.createElement("span");
        content.className = "ab-branch-marker-brand";
        const img = document.createElement("img");
        img.src = this.logo;
        img.alt = "";
        content.append(img);
        if (count) {
            const badge = document.createElement("b");
            badge.textContent = count;
            content.append(badge);
        }
        return content;
    }

    onClick(event) {
        const branchButton = event.target.closest("[data-branch-select]");
        if (branchButton) {
            this.selectBranch(this.branches.find((branch) => branch.card.contains(branchButton)));
        } else if (event.target.closest("[data-branch-close]")) {
            this.closeProfile();
        } else if (event.target.closest("[data-branch-reset]")) {
            this.search.value = "";
            this.region.value = "";
            this.closeProfile();
            this.filter();
        } else if (event.target.closest("[data-branch-clear]")) {
            this.search.value = "";
            this.filter();
            this.search.focus();
        } else if (event.target.closest("[data-branch-near]")) {
            this.locate();
        } else if (event.target.closest("[data-branch-view]")) {
            this.setView(event.target.closest("[data-branch-view]").dataset.branchView);
        }
    }

    filter(fit = true) {
        const terms = normalize(this.search.value.trim()).split(/\s+/).filter(Boolean);
        this.visible = this.branches.filter((branch) => {
            const matches = (!this.region.value || branch.region === this.region.value) && terms.every((term) => branch.search.includes(term));
            branch.card.hidden = !matches;
            return matches;
        });
        this.el.querySelector("[data-branch-count]").textContent = _t("%s branches found", this.visible.length);
        this.el.querySelector("[data-branch-empty]").hidden = Boolean(this.visible.length);
        this.el.querySelector("[data-branch-clear]").hidden = !this.search.value;
        if (this.clusters) {
            this.clusters.clearLayers();
            this.clusters.addLayers(this.visible.map((branch) => branch.marker));
            if (fit) this.fitBranches();
        }
        if (this.selected && !this.visible.includes(this.selected)) this.closeProfile();
    }

    fitBranches() {
        if (this.map && this.visible.length) {
            this.map.fitBounds(this.visible.map((branch) => branch.coords), { padding: [48, 60], maxZoom: 14, animate: false });
        }
    }

    setView(view) {
        this.workspace.dataset.view = view;
        this.el.querySelectorAll("[data-branch-view]").forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.branchView === view)));
        this.map?.invalidateSize();
    }

    selectBranch(branch, updateHash = true) {
        if (!branch) return;
        if (!this.profile.open) this.returnFocus = document.activeElement;
        this.selected?.marker?.getElement()?.classList.remove("is-selected");
        this.selected?.card.classList.remove("is-selected");
        this.selected = branch;
        branch.card.classList.add("is-selected");
        branch.marker?.getElement()?.classList.add("is-selected");
        this.profile.querySelector("#ab-branch-profile-name").textContent = branch.name;
        this.profile.querySelector("[data-profile-region]").textContent = branch.regionName;
        this.profile.querySelector("[data-profile-address]").textContent = branch.address;
        const distance = this.profile.querySelector("[data-profile-distance]");
        distance.hidden = branch.distance === undefined;
        distance.textContent = branch.distance === undefined ? "" : this.distanceLabel(branch.distance);
        this.profile.querySelector("[data-profile-directions]").href = `https://www.google.com/maps/dir/?api=1&destination=${branch.coords.join(",")}`;
        this.profile.scrollTop = 0;
        if (!this.profile.open) this.showProfile();
        this.focusBranch(branch);
        if (updateHash) history.replaceState(null, "", `#branch=${encodeURIComponent(branch.id)}`);
    }

    showProfile() {
        this.el.querySelector(".ab-branches-results").inert = true;
        if (this.mobile.matches) {
            this.profile.showModal();
            document.body.classList.add("ab-branch-sheet-open");
        } else {
            this.profile.show();
            document.body.classList.remove("ab-branch-sheet-open");
        }
        this.profile.querySelector("#ab-branch-profile-name").focus({ preventScroll: true });
    }

    focusBranch(branch) {
        if (!this.map || !branch.marker) return;
        this.map.setView(branch.coords, 16, { animate: false });
    }

    closeProfile(updateHash = true) {
        const wasOpen = this.profile.open;
        this.profile.close();
        this.el.querySelector(".ab-branches-results").inert = false;
        document.body.classList.remove("ab-branch-sheet-open");
        this.selected?.marker?.getElement()?.classList.remove("is-selected");
        this.selected?.card.classList.remove("is-selected");
        this.selected = null;
        if (updateHash && location.hash.startsWith("#branch=")) history.replaceState(null, "", location.pathname + location.search);
        if (wasOpen) {
            const target = this.returnFocus?.isConnected && this.returnFocus.getClientRects().length ? this.returnFocus : this.search;
            target.focus({ preventScroll: true });
        }
    }

    openHash() {
        let id;
        try { id = decodeURIComponent(location.hash.replace(/^#branch=/, "")); } catch { return; }
        const branch = this.branches.find((item) => item.id === id);
        if (branch) {
            if (!this.visible.includes(branch)) {
                this.region.value = "";
                this.search.value = "";
                this.filter();
            }
            this.selectBranch(branch, false);
        } else if (this.profile.open) {
            this.closeProfile(false);
        }
    }

    setStatus(message) {
        this.status.hidden = !message;
        this.status.textContent = message;
    }

    distanceLabel(distance) {
        const value = new Intl.NumberFormat(document.documentElement.lang, { maximumFractionDigits: 1 }).format(distance);
        return _t("%s km away · straight-line distance", value);
    }

    locate() {
        if (!window.isSecureContext || !navigator.geolocation) {
            this.setStatus(_t("Your browser needs a secure HTTPS connection to use your location. Search by area or governorate instead."));
            return;
        }
        const button = this.el.querySelector("[data-branch-near]");
        button.disabled = true;
        button.setAttribute("aria-busy", "true");
        this.setStatus(_t("Finding the closest branches..."));
        const finish = () => { button.disabled = false; button.removeAttribute("aria-busy"); };
        navigator.geolocation.getCurrentPosition((position) => {
            if (this.stopped) return;
            finish();
            this.usePosition(position.coords);
        }, (error) => {
            if (this.stopped) return;
            finish();
            this.setStatus(error.code === 1 ? _t("Location access was declined. You can still search by area or governorate.") : _t("We couldn't find your location. Try again or search for your area."));
        }, { enableHighAccuracy: false, timeout: 12000, maximumAge: 300000 });
    }

    usePosition({ latitude, longitude } = {}) {
        if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) return;
        const radians = (degrees) => degrees * Math.PI / 180;
        for (const branch of this.branches) {
            const [lat, lng] = branch.coords;
            const a = Math.sin(radians(lat - latitude) / 2) ** 2 + Math.cos(radians(latitude)) * Math.cos(radians(lat)) * Math.sin(radians(lng - longitude) / 2) ** 2;
            branch.distance = 6371 * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(Math.max(0, 1 - a)));
            const distance = branch.card.querySelector("[data-branch-distance]");
            distance.hidden = false;
            distance.textContent = this.distanceLabel(branch.distance);
        }
        this.branches.sort((first, second) => first.distance - second.distance);
        this.branches.forEach((branch) => this.list.append(branch.card));
        this.search.value = "";
        this.region.value = "";
        this.filter(false);
        this.selectBranch(this.branches[0]);
        this.setStatus(_t("Branches are sorted by distance from your location. Distances are approximate."));
    }

    destroy() {
        this.stopped = true;
        this.listeners?.abort();
        this.resizeObserver?.disconnect();
        this.profile?.close();
        this.el.querySelector(".ab-branches-results").inert = false;
        document.body.classList.remove("ab-branch-sheet-open");
        this.map?.remove();
        this.map = null;
    }
}

registry.category("public.interactions").add("ab_ecommerce_storefront.branches", AbBranchLocator);
