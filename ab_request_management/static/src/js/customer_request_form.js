/** @odoo-module **/

const form = document.querySelector("[data-ab-external-request-form]");

if (form) {
    const categorySelect = form.querySelector("#request_category_id");
    const typeSelect = form.querySelector("#request_type_id");
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
    refreshRequestTypes();
}
