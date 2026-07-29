/** @odoo-module **/

const form = document.querySelector("[data-ab-external-request-form]");
const copyButtons = document.querySelectorAll("[data-ab-copy-value]");

async function copyTextToClipboard(value) {
    if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(value);
        return true;
    }

    const textarea = document.createElement("textarea");
    textarea.value = value;
    textarea.setAttribute("readonly", "");
    textarea.style.position = "fixed";
    textarea.style.insetInlineStart = "-9999px";
    textarea.style.top = "0";
    document.body.append(textarea);
    textarea.select();
    textarea.setSelectionRange(0, textarea.value.length);

    try {
        return document.execCommand("copy");
    } finally {
        textarea.remove();
    }
}

for (const copyButton of copyButtons) {
    copyButton.addEventListener("click", async () => {
        const value = copyButton.dataset.abCopyValue || "";
        if (!value) {
            return;
        }
        try {
            const copied = await copyTextToClipboard(value);
            copyButton.textContent = copied
                ? copyButton.dataset.abCopiedLabel || "تم النسخ"
                : copyButton.dataset.abCopyFallbackLabel || "حدد الرابط وانسخه";
        } catch {
            copyButton.textContent = copyButton.dataset.abCopyFallbackLabel || "حدد الرابط وانسخه";
        }
    });
}

if (form) {
    const categorySelect = form.querySelector("#request_category_id");
    const typeSelect = form.querySelector("#request_type_id");
    const employeeCodeInput = form.querySelector("#employee_code");
    const commercialRegisterInput = form.querySelector("#commercial_register_number");
    const typeOptions = Array.from(typeSelect.querySelectorAll("option[data-category-id]"));
    let selectedTypeId = typeSelect.dataset.selectedValue || "";

    function refreshRequestTypes() {
        const categoryId = categorySelect.value;
        const currentTypeId = typeSelect.value || selectedTypeId;
        const placeholder = document.createElement("option");
        placeholder.value = "";
        placeholder.textContent = categoryId
            ? typeSelect.dataset.placeholderReady
            : typeSelect.dataset.placeholderEmpty;

        typeSelect.replaceChildren(placeholder);
        for (const option of typeOptions) {
            if (option.dataset.categoryId === categoryId) {
                typeSelect.append(option.cloneNode(true));
            }
        }

        if (currentTypeId && Array.from(typeSelect.options).some((option) => option.value === currentTypeId)) {
            typeSelect.value = currentTypeId;
        }
        typeSelect.disabled = !categoryId || typeSelect.options.length <= 1;
    }

    categorySelect.addEventListener("change", () => {
        typeSelect.dataset.selectedValue = "";
        selectedTypeId = "";
        refreshRequestTypes();
    });

    function refreshAlternativeRequiredFields() {
        const hasRequesterReference = Boolean(
            employeeCodeInput.value.trim() || commercialRegisterInput.value.trim()
        );
        const message = hasRequesterReference
            ? ""
            : form.dataset.abRequesterReferenceError || "أدخل كود الموظف أو رقم السجل التجاري.";
        employeeCodeInput.setCustomValidity(message);
        commercialRegisterInput.setCustomValidity(message);
    }

    employeeCodeInput.addEventListener("input", refreshAlternativeRequiredFields);
    commercialRegisterInput.addEventListener("input", refreshAlternativeRequiredFields);

    const captchaImage = form.querySelector("#captcha_image");
    const refreshCaptchaBtn = form.querySelector("#refresh_captcha_btn");
    if (captchaImage && refreshCaptchaBtn) {
        refreshCaptchaBtn.addEventListener("click", (ev) => {
            ev.preventDefault();
            captchaImage.src = `/requests/captcha/image?ts=${Date.now()}`;
        });
    }

    refreshRequestTypes();
    refreshAlternativeRequiredFields();
}
