/** @odoo-module **/

import { registry } from "@web/core/registry";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { _t } from "@web/core/l10n/translation";
import { Component, useState } from "@odoo/owl";

const imageExtensions = new Set(["jpg", "jpeg", "png", "webp", "gif", "bmp"]);

class StorefrontImageUpload extends Component {
    static template = "ab_ecommerce_storefront.ImageSyncUpload";
    static props = { ...standardWidgetProps };

    setup() {
        this.state = useState({ uploading: false, progress: 0, error: "" });
    }

    get mode() {
        return this.props.record.data.source_mode;
    }

    get hasSelection() {
        const data = this.props.record.data;
        return data.upload_ready && data.upload_source_mode === this.mode;
    }

    pickImages() {
        const picker = document.createElement("input");
        picker.type = "file";
        if (this.mode === "folder") {
            if (!("webkitdirectory" in picker)) {
                this.state.error = _t("Folder selection is unavailable in this browser. Choose a ZIP file instead.");
                return;
            }
            picker.webkitdirectory = true;
            picker.multiple = true;
        } else {
            picker.accept = ".zip,application/zip";
        }
        picker.addEventListener("change", () => this.uploadSelection([...picker.files]));
        picker.click();
    }

    async uploadSelection(files) {
        if (!files.length) {
            return;
        }
        const images = this.mode === "folder"
            ? files.filter((file) => imageExtensions.has(file.name.split(".").pop().toLowerCase()))
            : files;
        if (!images.length) {
            this.state.error = _t("No supported image files were selected.");
            return;
        }
        this.state.uploading = true;
        this.state.progress = 0;
        this.state.error = "";
        try {
            if (!(await this.props.record.save())) {
                throw new Error(_t("Save the image source before uploading."));
            }
            const name = this.mode === "folder"
                ? images[0].webkitRelativePath.split("/")[0]
                : images[0].name;
            await this.send("start", { source_mode: this.mode, upload_name: name });
            await this.props.record.load();
            if (this.mode === "zip") {
                await this.send("zip", {}, [images[0]], images[0].size, 0, images[0].size);
            } else {
                const total = images.reduce((sum, file) => sum + file.size, 0);
                let sent = 0;
                let batch = [];
                let batchBytes = 0;
                for (const file of images) {
                    if (batch.length && (batch.length >= 10 || batchBytes + file.size > 20 * 1024 * 1024)) {
                        await this.send("folder", {}, batch, total, sent, batchBytes);
                        sent += batchBytes;
                        batch = [];
                        batchBytes = 0;
                    }
                    batch.push(file);
                    batchBytes += file.size;
                }
                if (batch.length) {
                    await this.send("folder", {}, batch, total, sent, batchBytes);
                }
            }
            await this.send("finish");
            this.state.progress = 100;
            await this.props.record.load();
        } catch (error) {
            this.state.error = error.message || _t("Image upload failed.");
            await this.props.record.load();
        } finally {
            this.state.uploading = false;
        }
    }

    send(operation, values = {}, files = [], total = 0, sent = 0, batchBytes = 0) {
        const data = new FormData();
        data.append("csrf_token", odoo.csrf_token);
        data.append("wizard_id", this.props.record.resId);
        data.append("operation", operation);
        for (const [key, value] of Object.entries(values)) {
            data.append(key, value);
        }
        for (const file of files) {
            data.append(operation === "zip" ? "file" : "files", file);
            if (operation === "folder") {
                data.append("paths", file.webkitRelativePath || file.name);
            }
        }
        return new Promise((resolve, reject) => {
            const xhr = new XMLHttpRequest();
            xhr.open("POST", "/ab_storefront/image_sync/upload");
            xhr.responseType = "json";
            xhr.upload.onprogress = (event) => {
                if (event.lengthComputable && total) {
                    this.state.progress = Math.min(99, Math.round(100 * (sent + batchBytes * event.loaded / event.total) / total));
                }
            };
            xhr.onload = () => {
                if (xhr.status >= 200 && xhr.status < 300 && !xhr.response?.error) {
                    resolve(xhr.response);
                } else {
                    reject(new Error(xhr.response?.error || _t("Image upload failed.")));
                }
            };
            xhr.onerror = () => reject(new Error(_t("Image upload failed. Check your connection and try again.")));
            xhr.send(data);
        });
    }
}

registry.category("view_widgets").add("ab_storefront_image_upload", { component: StorefrontImageUpload });
