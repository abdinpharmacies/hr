/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";

const ALLOWED_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);

export class AbPrescriptionOrderForm extends Interaction {
    static selector = "[data-ab-prescription-form]";

    setup() {
        this.previewUrl = null;
        this.cameraStream = null;
        this.cameraRequestId = 0;
        this.cameraPending = false;
        this.onChange = this.onChange.bind(this);
        this.onClick = this.onClick.bind(this);
        this.onSubmit = this.onSubmit.bind(this);
        this.onCameraReady = this.onCameraReady.bind(this);
        this.onPageHide = this.onPageHide.bind(this);
    }

    start() {
        this.inputs = [...this.el.querySelectorAll("[data-ab-prescription-input]")];
        this.error = this.el.querySelector("[data-ab-prescription-error]");
        this.emptyState = this.el.querySelector("[data-ab-prescription-empty]");
        this.preview = this.el.querySelector("[data-ab-prescription-preview]");
        this.previewImage = this.el.querySelector("[data-ab-prescription-preview-image]");
        this.submit = this.el.querySelector("[data-ab-prescription-submit]");
        this.uploading = this.el.querySelector("[data-ab-prescription-uploading]");
        this.success = this.el.querySelector("[data-ab-prescription-success]");
        this.cameraInput = this.el.querySelector('[data-ab-prescription-input="camera"]');
        this.cameraPanel = this.el.querySelector("[data-ab-prescription-camera]");
        this.cameraVideo = this.el.querySelector("[data-ab-prescription-camera-video]");
        this.cameraCapture = this.el.querySelector("[data-ab-prescription-camera-capture]");
        this.cameraHelp = this.el.querySelector("[data-ab-prescription-camera-help]");
        this.cameraMessage = this.el.querySelector("[data-ab-prescription-camera-message]");
        this.cameraRetry = this.el.querySelector("[data-ab-prescription-camera-retry]");
        this.maxSize = Number(this.el.dataset.abPrescriptionMaxSize || 8 * 1024 * 1024);
        this.inputs.forEach((input) => input.addEventListener("change", this.onChange));
        this.cameraVideo?.addEventListener("loadedmetadata", this.onCameraReady);
        window.addEventListener("pagehide", this.onPageHide);
        this.el.addEventListener("click", this.onClick);
        this.el.addEventListener("submit", this.onSubmit);
    }

    destroy() {
        this.inputs?.forEach((input) => input.removeEventListener("change", this.onChange));
        this.el.removeEventListener("click", this.onClick);
        this.el.removeEventListener("submit", this.onSubmit);
        this.cameraVideo?.removeEventListener("loadedmetadata", this.onCameraReady);
        window.removeEventListener("pagehide", this.onPageHide);
        this.stopCamera();
        this.revokePreviewUrl();
    }

    onChange(ev) {
        const input = ev.target.closest("[data-ab-prescription-input]");
        if (!input) {
            return;
        }
        this.stopCamera();
        this.showCameraMessage("");
        const file = input.files?.[0];
        if (!file) {
            this.syncSubmit();
            return;
        }
        const error = this.validateFile(file);
        if (error) {
            this.showError(error);
            this.clearInputs();
            this.showEmptyState();
            return;
        }
        this.inputs.forEach((otherInput) => {
            if (otherInput !== input) {
                otherInput.value = "";
            }
        });
        this.showPreview(file);
        this.showError("");
        this.syncSubmit();
    }

    onClick(ev) {
        const cameraOpen = ev.target.closest("[data-ab-prescription-camera-open]");
        if (cameraOpen) {
            if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia || !window.DataTransfer) {
                this.showCameraMessage(_t("Live camera access needs HTTPS or a loopback address (127.0.0.x) in a supported browser. You can use the camera picker or upload an image."), false);
                return;
            }
            ev.preventDefault();
            this.openCamera();
            return;
        }
        if (ev.target.closest("[data-ab-prescription-camera-retry]")) {
            ev.preventDefault();
            this.openCamera();
            return;
        }
        if (ev.target.closest("[data-ab-prescription-camera-capture]")) {
            ev.preventDefault();
            this.capturePhoto();
            return;
        }
        if (ev.target.closest("[data-ab-prescription-camera-close]")) {
            ev.preventDefault();
            this.stopCamera();
            this.showCameraMessage("");
            return;
        }
        const remove = ev.target.closest("[data-ab-prescription-remove]");
        if (!remove) {
            return;
        }
        ev.preventDefault();
        this.stopCamera();
        this.clearInputs();
        this.showEmptyState();
        this.showError("");
    }

    onSubmit() {
        this.stopCamera();
        this.showUploadingState();
    }

    async openCamera() {
        if (this.cameraPending || this.cameraStream) {
            return;
        }
        this.cameraPending = true;
        const requestId = ++this.cameraRequestId;
        this.showCameraMessage(_t("Waiting for camera permission..."), false);
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: { ideal: "environment" } },
                audio: false,
            });
            if (requestId !== this.cameraRequestId) {
                stream.getTracks().forEach((track) => track.stop());
                return;
            }
            this.cameraStream = stream;
            this.cameraVideo.srcObject = stream;
            this.cameraCapture.disabled = true;
            this.emptyState.classList.add("d-none");
            this.cameraPanel.classList.remove("d-none");
            await this.cameraVideo.play();
            this.onCameraReady();
            this.showCameraMessage("");
        } catch (error) {
            if (requestId === this.cameraRequestId) {
                this.stopCamera();
                this.showCameraMessage(this.cameraErrorMessage(error));
            }
        } finally {
            if (requestId === this.cameraRequestId) {
                this.cameraPending = false;
            }
        }
    }

    onCameraReady() {
        if (this.cameraCapture && this.cameraVideo?.videoWidth) {
            this.cameraCapture.disabled = false;
        }
    }

    async capturePhoto() {
        if (!this.cameraStream || !this.cameraVideo.videoWidth || this.cameraCapture.disabled) {
            return;
        }
        this.cameraCapture.disabled = true;
        const captureRequestId = this.cameraRequestId;
        try {
            const canvas = document.createElement("canvas");
            const scale = Math.min(1, 2600 / Math.max(this.cameraVideo.videoWidth, this.cameraVideo.videoHeight));
            canvas.width = Math.round(this.cameraVideo.videoWidth * scale);
            canvas.height = Math.round(this.cameraVideo.videoHeight * scale);
            canvas.getContext("2d").drawImage(this.cameraVideo, 0, 0, canvas.width, canvas.height);
            const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.88));
            if (captureRequestId !== this.cameraRequestId) {
                return;
            }
            if (!blob) {
                throw new Error("Camera capture failed");
            }
            const file = new File([blob], `prescription-${Date.now()}.jpg`, { type: "image/jpeg" });
            const transfer = new DataTransfer();
            transfer.items.add(file);
            this.cameraInput.files = transfer.files;
            this.onChange({ target: this.cameraInput });
        } catch {
            this.stopCamera();
            this.showCameraMessage(_t("Unable to capture the photo. Please try again or upload an image."));
        }
    }

    stopCamera() {
        this.cameraRequestId += 1;
        this.cameraPending = false;
        this.cameraStream?.getTracks().forEach((track) => track.stop());
        this.cameraStream = null;
        if (this.cameraVideo) {
            this.cameraVideo.pause();
            this.cameraVideo.srcObject = null;
        }
        this.cameraPanel?.classList.add("d-none");
        if (this.preview?.classList.contains("d-none")) {
            this.emptyState?.classList.remove("d-none");
        }
    }

    onPageHide() {
        this.stopCamera();
    }

    showCameraMessage(message, canRetry = true) {
        if (this.cameraMessage) {
            this.cameraMessage.textContent = message;
        }
        this.cameraHelp?.classList.toggle("d-none", !message);
        this.cameraRetry?.classList.toggle("d-none", !message || !canRetry);
    }

    cameraErrorMessage(error) {
        if (error.name === "NotAllowedError" || error.name === "PermissionDeniedError" || error.name === "SecurityError") {
            return _t("Camera access is blocked. Allow Camera in the site settings beside the address bar, and allow your browser in device settings if needed. Then try again.");
        }
        if (error.name === "NotFoundError") {
            return _t("No camera was found. Connect a camera or upload an image.");
        }
        if (error.name === "NotReadableError") {
            return _t("The camera is unavailable or already in use. Close other apps using it and try again.");
        }
        return _t("Unable to open the camera. Please try again or upload an image.");
    }

    validateFile(file) {
        if (!file) {
            return _t("Please upload a prescription image.");
        }
        if (!ALLOWED_TYPES.has(file.type)) {
            return _t("Please upload a JPG, PNG, or WebP image.");
        }
        if (file.size > this.maxSize) {
            return _t("The prescription image is too large. Please upload an image up to 8 MB.");
        }
        return "";
    }

    showPreview(file) {
        this.revokePreviewUrl();
        this.previewUrl = URL.createObjectURL(file);
        this.previewImage.src = this.previewUrl;
        this.preview.classList.remove("d-none");
        this.emptyState.classList.add("d-none");
        this.success?.classList.remove("d-none");
        this.uploading?.classList.add("d-none");
    }

    showEmptyState() {
        this.revokePreviewUrl();
        if (this.previewImage) {
            this.previewImage.removeAttribute("src");
        }
        this.preview?.classList.add("d-none");
        this.emptyState?.classList.remove("d-none");
        this.success?.classList.add("d-none");
        this.uploading?.classList.add("d-none");
        this.syncSubmit();
    }

    showError(message) {
        if (!this.error) {
            return;
        }
        this.error.textContent = message;
        this.error.classList.toggle("d-none", !message);
    }

    clearInputs() {
        this.inputs.forEach((input) => {
            input.value = "";
        });
    }

    syncSubmit() {
        const hasImage = this.inputs.some((input) => Boolean(input.files?.[0]));
        if (this.submit) {
            this.submit.disabled = !hasImage;
        }
    }

    revokePreviewUrl() {
        if (this.previewUrl) {
            URL.revokeObjectURL(this.previewUrl);
            this.previewUrl = null;
        }
    }

    showUploadingState() {
        if (!this.inputs.some((input) => Boolean(input.files?.[0]))) {
            return;
        }
        this.submit.disabled = true;
        this.submit.setAttribute("aria-busy", "true");
        this.submit.querySelector("span").textContent = _t("Uploading...");
        this.uploading?.classList.remove("d-none");
        this.success?.classList.add("d-none");
    }
}

registry.category("public.interactions").add("ab_ecommerce_storefront.prescription_order_form", AbPrescriptionOrderForm);
