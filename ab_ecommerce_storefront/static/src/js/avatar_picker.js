/** @odoo-module **/

import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";

const AVATAR_PATH = "/ab_ecommerce_storefront/static/src/img/avatars/";
const DEFAULT_AVATAR = "avatar_none";
const CLOSE_ANIMATION_MS = 380;

export class AbStorefrontAvatarPicker extends Interaction {
    static selector = ".ab-auth-page, .ab-account-hero-scope, .ab-account-avatar-card";

    setup() {
        this.onClick = this.onClick.bind(this);
        this.onChange = this.onChange.bind(this);
        this.onKeydown = this.onKeydown.bind(this);
        this.activeScope = null;
        this.pickerPlaceholders = new WeakMap();
        this.previewUrls = new WeakMap();
    }

    start() {
        document.addEventListener("click", this.onClick);
        document.addEventListener("change", this.onChange);
        document.addEventListener("keydown", this.onKeydown);
    }

    destroy() {
        document.removeEventListener("click", this.onClick);
        document.removeEventListener("change", this.onChange);
        document.removeEventListener("keydown", this.onKeydown);
    }

    onClick(ev) {
        const openButton = ev.target.closest("[data-ab-avatar-open]");
        if (openButton) {
            const scope = openButton.closest("[data-ab-avatar-scope]");
            if (scope) {
                ev.preventDefault();
                this.openPicker(scope);
            }
            return;
        }

        const closeButton = ev.target.closest("[data-ab-avatar-close]");
        if (closeButton) {
            ev.preventDefault();
            this.closePicker(closeButton.closest("[data-ab-avatar-picker]"), {animate: true});
            return;
        }

        const option = ev.target.closest("[data-ab-avatar-option]");
        if (option) {
            ev.preventDefault();
            this.selectAvatar(this.getScopeFromElement(option), option.dataset.abAvatarOption);
            return;
        }

        const confirmButton = ev.target.closest("[data-ab-avatar-confirm]");
        if (confirmButton) {
            ev.preventDefault();
            this.confirmSelection(this.getScopeFromElement(confirmButton));
        }
    }

    onChange(ev) {
        const uploadInput = ev.target.closest("[data-ab-avatar-upload]");
        if (!uploadInput) {
            return;
        }
        const scope = this.getScopeFromElement(uploadInput);
        const file = uploadInput.files?.[0];
        if (!scope || !file) {
            return;
        }
        this.selectUploadedAvatar(scope, file);
    }

    onKeydown(ev) {
        if (ev.key === "Escape") {
            document.querySelectorAll(".ab-avatar-picker.is-open").forEach((picker) => this.closePicker(picker, {animate: true}));
            return;
        }
        const option = ev.target.closest("[data-ab-avatar-option]");
        if (!option || !["Enter", " "].includes(ev.key)) {
            return;
        }
        ev.preventDefault();
        this.selectAvatar(this.getScopeFromElement(option), option.dataset.abAvatarOption);
    }

    getScopeFromElement(element) {
        const picker = element.closest("[data-ab-avatar-picker]");
        return element.closest("[data-ab-avatar-scope]") || picker?.abAvatarScope || this.activeScope;
    }

    getPickerForScope(scope) {
        return scope?.querySelector("[data-ab-avatar-picker]") || [...document.querySelectorAll("[data-ab-avatar-picker]")].find((picker) => picker.abAvatarScope === scope);
    }

    openPicker(scope) {
        const picker = this.getPickerForScope(scope);
        if (!picker) {
            return;
        }
        this.activeScope = scope;
        picker.abAvatarScope = scope;
        picker.classList.remove("is-closing");
        if (!this.pickerPlaceholders.has(picker)) {
            const placeholder = document.createComment("ab-avatar-picker");
            picker.parentNode.insertBefore(placeholder, picker);
            this.pickerPlaceholders.set(picker, placeholder);
        }
        document.body.appendChild(picker);
        this.syncOptions(scope, scope.dataset.abAvatarCurrent || DEFAULT_AVATAR);
        picker.setAttribute("aria-hidden", "false");
        document.documentElement.classList.add("ab-avatar-picker-open");
        window.requestAnimationFrame(() => {
            window.requestAnimationFrame(() => {
                picker.classList.add("is-open");
            });
        });
        window.setTimeout(() => {
            picker.querySelector(".ab-avatar-option.is-selected")?.focus();
        }, 80);
    }

    closePicker(picker, {animate = false} = {}) {
        if (!picker) {
            return;
        }
        picker.classList.remove("is-open");
        picker.setAttribute("aria-hidden", "true");
        if (animate) {
            picker.classList.add("is-closing");
            window.setTimeout(() => this.restorePicker(picker), CLOSE_ANIMATION_MS);
            return;
        }
        this.restorePicker(picker);
    }

    restorePicker(picker) {
        picker.classList.remove("is-closing");
        const placeholder = this.pickerPlaceholders.get(picker);
        if (placeholder?.parentNode) {
            placeholder.parentNode.insertBefore(picker, placeholder);
            placeholder.remove();
            this.pickerPlaceholders.delete(picker);
        }
        if (this.activeScope?.querySelector("[data-ab-avatar-picker]") === picker) {
            this.activeScope = null;
        }
        picker.abAvatarScope = null;
        if (!document.querySelector(".ab-avatar-picker.is-open")) {
            document.documentElement.classList.remove("ab-avatar-picker-open");
        }
    }

    selectAvatar(scope, avatar) {
        if (!scope || !avatar) {
            return;
        }
        scope.dataset.abAvatarCurrent = avatar;
        const input = scope.querySelector("[data-ab-avatar-input]");
        if (input) {
            input.value = avatar;
        }
        if (avatar !== "custom") {
            this.clearUpload(scope);
        }
        this.syncOptions(scope, avatar);
        this.updatePreview(scope, avatar);
    }

    selectUploadedAvatar(scope, file) {
        scope.dataset.abAvatarCurrent = "custom";
        const input = scope.querySelector("[data-ab-avatar-input]");
        if (input) {
            input.value = "custom";
        }
        const formUpload = scope.querySelector("[data-ab-avatar-form-upload]");
        if (formUpload && window.DataTransfer) {
            const transfer = new DataTransfer();
            transfer.items.add(file);
            formUpload.files = transfer.files;
        }
        const currentPreviewUrl = this.previewUrls.get(scope);
        if (currentPreviewUrl) {
            URL.revokeObjectURL(currentPreviewUrl);
        }
        const previewUrl = URL.createObjectURL(file);
        this.previewUrls.set(scope, previewUrl);
        this.syncOptions(scope, "custom");
        this.updatePreview(scope, "custom", previewUrl);
    }

    clearUpload(scope) {
        const pickerUpload = this.getPickerForScope(scope)?.querySelector("[data-ab-avatar-upload]");
        const formUpload = scope.querySelector("[data-ab-avatar-form-upload]");
        if (pickerUpload) {
            pickerUpload.value = "";
        }
        if (formUpload) {
            formUpload.value = "";
        }
        const currentPreviewUrl = this.previewUrls.get(scope);
        if (currentPreviewUrl) {
            URL.revokeObjectURL(currentPreviewUrl);
            this.previewUrls.delete(scope);
        }
    }

    syncOptions(scope, avatar) {
        const picker = this.getPickerForScope(scope) || document.querySelector(".ab-avatar-picker.is-open");
        picker?.querySelector(".ab-avatar-upload-option")?.classList.toggle("is-selected", avatar === "custom");
        picker?.querySelectorAll("[data-ab-avatar-option]").forEach((option) => {
            const selected = option.dataset.abAvatarOption === avatar;
            option.classList.toggle("is-selected", selected);
            option.setAttribute("aria-checked", selected ? "true" : "false");
        });
    }

    updatePreview(scope, avatar, customSrc = null) {
        scope.querySelectorAll(".ab-auth-avatar-preview .ab-storefront-avatar, .ab-account-avatar-visual .ab-storefront-avatar, .ab-account-hero-avatar .ab-storefront-avatar").forEach((avatarNode) => {
            const img = avatarNode.querySelector("img");
            avatarNode.dataset.abAvatarValue = avatar;
            avatarNode.classList.remove("is-changing");
            void avatarNode.offsetWidth;
            avatarNode.classList.add("is-changing");
            if (img) {
                img.src = customSrc || this.getAvatarSrc(avatar);
            }
        });
    }

    getAvatarSrc(avatar) {
        if (avatar === "custom") {
            const partnerId = window.odoo?.session_info?.partner_id;
            return partnerId ? `/web/image/res.partner/${partnerId}/image_128?unique=${Date.now()}` : `${AVATAR_PATH}${DEFAULT_AVATAR}.svg`;
        }
        return `${AVATAR_PATH}${avatar || DEFAULT_AVATAR}.svg`;
    }

    async confirmSelection(scope) {
        if (!scope) {
            return;
        }
        const picker = this.getPickerForScope(scope);
        const avatar = scope.dataset.abAvatarCurrent || DEFAULT_AVATAR;
        const updateUrl = scope.dataset.abAvatarUpdateUrl;
        if (!updateUrl) {
            this.closePicker(picker, {animate: true});
            return;
        }
        const status = scope.querySelector("[data-ab-avatar-status]");
        const formData = new FormData();
        formData.append("avatar", avatar);
        const upload = this.getPickerForScope(scope)?.querySelector("[data-ab-avatar-upload]")?.files?.[0];
        if (upload) {
            formData.append("avatar_upload", upload);
        }
        formData.append("csrf_token", scope.querySelector("[data-ab-avatar-csrf]")?.value || "");
        try {
            const response = await fetch(updateUrl, {
                method: "POST",
                body: formData,
                credentials: "same-origin",
                headers: {"X-Requested-With": "XMLHttpRequest"},
            });
            if (!response.ok) {
                throw new Error("avatar_update_failed");
            }
            this.updateGlobalAvatars(avatar, this.previewUrls.get(scope));
            scope.classList.add("is-avatar-saved");
            if (status) {
                status.textContent = "تم حفظ الأفاتار";
            }
            this.closePicker(picker, {animate: true});
            window.setTimeout(() => {
                scope.classList.remove("is-avatar-saved");
                if (status) {
                    status.textContent = "";
                }
            }, 3000);
        } catch {
            if (status) {
                status.textContent = "تعذر حفظ الأفاتار. حاول مرة أخرى.";
            }
        }
    }

    updateGlobalAvatars(avatar, customSrc = null) {
        document.querySelectorAll(".ab-storefront-header .ab-storefront-avatar, .o_portal_wrap .ab-storefront-avatar, .ab-account-avatar-visual .ab-storefront-avatar").forEach((avatarNode) => {
            if (avatarNode.closest(".ab-avatar-picker")) {
                return;
            }
            const img = avatarNode.querySelector("img");
            avatarNode.dataset.abAvatarValue = avatar;
            avatarNode.classList.add("is-changing");
            if (img) {
                img.src = customSrc || this.getAvatarSrc(avatar);
            }
        });
    }
}

registry.category("public.interactions").add("ab_ecommerce_storefront.avatar_picker", AbStorefrontAvatarPicker);
