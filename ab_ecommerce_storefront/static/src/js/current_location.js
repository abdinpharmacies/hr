/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Interaction } from "@web/public/interaction";

const STORAGE_KEY = "ab_storefront_current_location";
const DEFAULT_LABEL = "منطقتك الحالية";
const FALLBACK_SET_LABEL = "تم تحديد المنطقة";
const GEOLOCATION_UNAVAILABLE_LABEL = "خدمة الموقع غير متاحة";
const LOADING_LABEL = "جاري تحديد المنطقة...";
const PERMISSION_NEEDED_LABEL = "السماح بالموقع مطلوب";
const REVERSE_GEOCODE_URL = "https://nominatim.openstreetmap.org/reverse";
const RECENT_LOCATIONS_KEY = "ab_storefront_recent_locations";

export class AbStorefrontCurrentLocation extends Interaction {
    static selector = "[data-ab-current-location]";

    setup() {
        this.onClick = this.onClick.bind(this);
        this.onLocationSet = this.onLocationSet.bind(this);
    }

    start() {
        this.button = this.el.querySelector(".ab-storefront-location-trigger");
        this.label = this.el.querySelector("[data-ab-location-label]");
        this.status = this.el.querySelector("[data-ab-location-status]");
        this.applyStoredLocation();
        this.button?.addEventListener("click", this.onClick);
        document.addEventListener("ab-storefront-location:set", this.onLocationSet);
    }

    destroy() {
        this.button?.removeEventListener("click", this.onClick);
        document.removeEventListener("ab-storefront-location:set", this.onLocationSet);
    }

    applyStoredLocation() {
        const location = this.getStoredLocation();
        if (location) {
            this.setState("is-set", location.governorate || FALLBACK_SET_LABEL);
            return;
        }
        const defaultLocation = (this.el.dataset.abLocationDefault || "").trim();
        if (defaultLocation) {
            this.setState("is-set", defaultLocation);
        }
    }

    getStoredLocation() {
        try {
            return JSON.parse(window.localStorage.getItem(STORAGE_KEY) || "null");
        } catch {
            return null;
        }
    }

    onLocationSet(event) {
        this.setState("is-set", event.detail?.governorate || FALLBACK_SET_LABEL);
    }

    async onClick() {
        document.dispatchEvent(new CustomEvent("ab-storefront-location:open"));
    }

    getCurrentPosition() {
        return new Promise((resolve, reject) => {
            navigator.geolocation.getCurrentPosition(resolve, reject, {
                enableHighAccuracy: true,
                maximumAge: 300000,
                timeout: 12000,
            });
        });
    }

    async getGovernorateName(latitude, longitude) {
        const url = new URL(REVERSE_GEOCODE_URL);
        url.searchParams.set("format", "jsonv2");
        url.searchParams.set("addressdetails", "1");
        url.searchParams.set("lat", latitude);
        url.searchParams.set("lon", longitude);
        url.searchParams.set("accept-language", "ar");

        try {
            const response = await fetch(url.toString(), { method: "GET" });
            if (!response.ok) {
                return "";
            }
            const data = await response.json();
            return this.extractGovernorate(data.address || {});
        } catch {
            return "";
        }
    }

    extractGovernorate(address) {
        return [
            address.state,
            address.province,
            address.governorate,
            address.county,
            address.city,
        ].find(Boolean) || "";
    }

    setState(stateClass, text) {
        this.button?.classList.remove("is-loading", "is-set", "is-error");
        this.button?.classList.add(stateClass);
        const displayText = stateClass === "is-set" && text
            ? `توصيل إلى ${text}`
            : text || DEFAULT_LABEL;
        this.button?.setAttribute("aria-label", displayText);
        this.button?.setAttribute("title", displayText);
        if (this.label) {
            this.label.textContent = displayText;
        }
        if (this.status) {
            this.status.textContent = displayText;
        }
    }
}

registry
    .category("public.interactions")
    .add("ab_ecommerce_storefront.current_location", AbStorefrontCurrentLocation);

export class AbStorefrontLocationPicker extends Interaction {
    static selector = "body.ab-storefront";

    setup() {
        this.selectedRegion = "مصر";
        this.geoPayload = {};
        this.lastFocus = null;
        this.onOpen = this.onOpen.bind(this);
        this.onCloseClick = this.onCloseClick.bind(this);
        this.onKeydown = this.onKeydown.bind(this);
        this.onRegionClick = this.onRegionClick.bind(this);
        this.onSearchInput = this.onSearchInput.bind(this);
        this.onAutoLocation = this.onAutoLocation.bind(this);
        this.onAddAddress = this.onAddAddress.bind(this);
        this.onSubmit = this.onSubmit.bind(this);
    }

    start() {
        this.panel = this.el.querySelector("[data-ab-location-picker]");
        if (!this.panel) {
            return;
        }
        this.searchInput = this.panel.querySelector("[data-ab-location-search]");
        this.detailInput = this.panel.querySelector("[data-ab-location-detail]");
        this.selectedLabel = this.panel.querySelector("[data-ab-location-selected]");
        this.submitButton = this.panel.querySelector("[data-ab-location-submit]");
        this.autoButton = this.panel.querySelector("[data-ab-location-auto]");
        this.addButton = this.panel.querySelector("[data-ab-location-add]");
        this.recentSection = this.panel.querySelector("[data-ab-location-recent-section]");
        this.recentList = this.panel.querySelector("[data-ab-location-recent-list]");

        document.addEventListener("ab-storefront-location:open", this.onOpen);
        document.addEventListener("keydown", this.onKeydown);
        this.panel.addEventListener("click", this.onRegionClick);
        this.searchInput?.addEventListener("input", this.onSearchInput);
        this.autoButton?.addEventListener("click", this.onAutoLocation);
        this.addButton?.addEventListener("click", this.onAddAddress);
        this.submitButton?.addEventListener("click", this.onSubmit);
        this.panel.querySelectorAll("[data-ab-location-picker-close]").forEach((button) => {
            button.addEventListener("click", this.onCloseClick);
        });
        this.applyStoredLocation();
        this.renderRecentLocations();
    }

    destroy() {
        document.removeEventListener("ab-storefront-location:open", this.onOpen);
        document.removeEventListener("keydown", this.onKeydown);
        this.panel?.removeEventListener("click", this.onRegionClick);
        this.searchInput?.removeEventListener("input", this.onSearchInput);
        this.autoButton?.removeEventListener("click", this.onAutoLocation);
        this.addButton?.removeEventListener("click", this.onAddAddress);
        this.submitButton?.removeEventListener("click", this.onSubmit);
        this.panel?.querySelectorAll("[data-ab-location-picker-close]").forEach((button) => {
            button.removeEventListener("click", this.onCloseClick);
        });
        document.body.classList.remove("ab-storefront-location-picker-open");
    }

    applyStoredLocation() {
        const stored = this.getStoredLocation();
        if (!stored) {
            return;
        }
        this.selectedRegion = stored.governorate || stored.region || "مصر";
        this.geoPayload = {
            latitude: stored.latitude,
            longitude: stored.longitude,
            accuracy: stored.accuracy,
            timestamp: stored.timestamp,
        };
        if (this.detailInput) {
            this.detailInput.value = stored.detailedAddress || "";
        }
        this.updateSelection();
    }

    getStoredLocation() {
        try {
            return JSON.parse(window.localStorage.getItem(STORAGE_KEY) || "null");
        } catch {
            return null;
        }
    }

    onOpen() {
        this.lastFocus = document.activeElement;
        this.renderRecentLocations();
        this.panel.classList.add("is-open");
        this.panel.setAttribute("aria-hidden", "false");
        document.body.classList.add("ab-storefront-location-picker-open");
        setTimeout(() => this.searchInput?.focus({ preventScroll: true }), 80);
    }

    onCloseClick() {
        this.close();
    }

    close() {
        this.panel?.classList.remove("is-open");
        this.panel?.setAttribute("aria-hidden", "true");
        document.body.classList.remove("ab-storefront-location-picker-open");
        if (this.lastFocus && document.contains(this.lastFocus)) {
            this.lastFocus.focus({ preventScroll: true });
        }
    }

    onKeydown(ev) {
        if (ev.key === "Escape" && this.panel?.classList.contains("is-open")) {
            ev.preventDefault();
            this.close();
        }
    }

    onRegionClick(ev) {
        const regionButton = ev.target.closest("[data-ab-location-region]");
        if (!regionButton || !this.panel.contains(regionButton)) {
            return;
        }
        this.selectRegion(regionButton.dataset.abLocationRegion);
    }

    onSearchInput() {
        const query = (this.searchInput?.value || "").trim().toLowerCase();
        this.panel.querySelectorAll(".ab-storefront-location-regions [data-ab-location-region]").forEach((button) => {
            const label = button.dataset.abLocationRegion || "";
            button.classList.toggle("d-none", Boolean(query) && !label.toLowerCase().includes(query));
        });
    }

    async onAutoLocation() {
        if (!navigator.geolocation) {
            this.setAutoState("is-error", GEOLOCATION_UNAVAILABLE_LABEL);
            return;
        }

        this.setAutoState("is-loading", LOADING_LABEL);
        try {
            const position = await this.getCurrentPosition();
            const data = await this.getReverseGeocode(position.coords.latitude, position.coords.longitude);
            const governorate = this.extractGovernorate(data.address || {}) || FALLBACK_SET_LABEL;
            this.geoPayload = {
                latitude: position.coords.latitude,
                longitude: position.coords.longitude,
                accuracy: position.coords.accuracy,
                timestamp: position.timestamp,
            };
            this.selectRegion(governorate);
            if (this.detailInput && data.display_name) {
                this.detailInput.value = data.display_name;
            }
            this.setAutoState("", "استخدم موقعي الحالي");
        } catch {
            this.setAutoState("is-error", PERMISSION_NEEDED_LABEL);
        }
    }

    onAddAddress() {
        this.detailInput?.scrollIntoView({ block: "center", behavior: "smooth" });
        setTimeout(() => this.detailInput?.focus({ preventScroll: true }), 180);
    }

    onSubmit() {
        const payload = {
            governorate: this.selectedRegion,
            region: this.selectedRegion,
            detailedAddress: (this.detailInput?.value || "").trim(),
            ...this.geoPayload,
            timestamp: this.geoPayload.timestamp || Date.now(),
        };
        window.localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
        this.storeRecentLocation(payload);
        document.dispatchEvent(new CustomEvent("ab-storefront-location:set", {
            detail: payload,
        }));
        this.close();
    }

    selectRegion(region) {
        this.selectedRegion = region || "مصر";
        this.updateSelection();
    }

    updateSelection() {
        this.panel?.querySelectorAll("[data-ab-location-region]").forEach((button) => {
            button.classList.toggle("is-selected", button.dataset.abLocationRegion === this.selectedRegion);
        });
        if (this.selectedLabel) {
            this.selectedLabel.textContent = this.selectedRegion;
        }
        if (this.submitButton) {
            this.submitButton.textContent = `تحديد ${this.selectedRegion}`;
        }
    }

    setAutoState(stateClass, text) {
        this.autoButton?.classList.remove("is-loading", "is-error");
        if (stateClass) {
            this.autoButton?.classList.add(stateClass);
        }
        const label = this.autoButton?.querySelector("span");
        if (label) {
            label.textContent = text || "استخدم موقعي الحالي";
        }
    }

    getCurrentPosition() {
        return new Promise((resolve, reject) => {
            navigator.geolocation.getCurrentPosition(resolve, reject, {
                enableHighAccuracy: true,
                maximumAge: 300000,
                timeout: 12000,
            });
        });
    }

    async getReverseGeocode(latitude, longitude) {
        const url = new URL(REVERSE_GEOCODE_URL);
        url.searchParams.set("format", "jsonv2");
        url.searchParams.set("addressdetails", "1");
        url.searchParams.set("lat", latitude);
        url.searchParams.set("lon", longitude);
        url.searchParams.set("accept-language", "ar");

        const response = await fetch(url.toString(), { method: "GET" });
        if (!response.ok) {
            return {};
        }
        return response.json();
    }

    extractGovernorate(address) {
        return [
            address.state,
            address.province,
            address.governorate,
            address.county,
            address.city,
        ].find(Boolean) || "";
    }

    getRecentLocations() {
        try {
            const recent = JSON.parse(window.localStorage.getItem(RECENT_LOCATIONS_KEY) || "[]");
            return Array.isArray(recent) ? recent.slice(0, 4) : [];
        } catch {
            return [];
        }
    }

    storeRecentLocation(location) {
        const recent = this.getRecentLocations();
        const next = [
            location,
            ...recent.filter((item) => (item.governorate || item.region) !== location.governorate),
        ].slice(0, 4);
        window.localStorage.setItem(RECENT_LOCATIONS_KEY, JSON.stringify(next));
    }

    renderRecentLocations() {
        if (!this.recentSection || !this.recentList) {
            return;
        }
        const recent = this.getRecentLocations();
        this.recentSection.classList.toggle("d-none", !recent.length);
        this.recentList.replaceChildren(...recent.map((location) => {
            const button = document.createElement("button");
            const region = location.governorate || location.region || "مصر";
            button.type = "button";
            button.className = "ab-storefront-location-recent-chip";
            button.dataset.abLocationRegion = region;
            button.textContent = region;
            return button;
        }));
    }
}

registry
    .category("public.interactions")
    .add("ab_ecommerce_storefront.location_picker", AbStorefrontLocationPicker);
