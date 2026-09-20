/** @odoo-module **/

import wSaleUtils from "@website_sale/js/website_sale_utils";

const originalShowWarning = wSaleUtils.showWarning;

function isArabicPage() {
    const lang = document.documentElement.lang || "";
    return lang.startsWith("ar");
}

function stockWarningCopy() {
    if (isArabicPage()) {
        return {
            title: "تم تعديل الكمية",
            close: "إغلاق تنبيه الكمية",
        };
    }
    return {
        title: "Quantity adjusted",
        close: "Close quantity warning",
    };
}

wSaleUtils.showWarning = function showStockWarning(message) {
    if (!message) {
        return;
    }

    const page = document.querySelector(".oe_website_sale");
    if (!page) {
        return originalShowWarning.call(this, message);
    }

    const copy = stockWarningCopy();
    let alert = page.querySelector(":scope > #data_warning");
    if (!alert) {
        alert = document.createElement("div");
        alert.id = "data_warning";
        alert.setAttribute("role", "alert");
        page.prepend(alert);
    }

    alert.className = "alert alert-warning alert-dismissible ab-storefront-stock-warning";
    alert.innerHTML = `
        <span class="ab-storefront-stock-warning-icon" aria-hidden="true">
            <i class="fa fa-exclamation-triangle"></i>
        </span>
        <span class="ab-storefront-stock-warning-copy">
            <strong>${copy.title}</strong>
            <span></span>
        </span>
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="${copy.close}"></button>
    `;
    alert.querySelector(".ab-storefront-stock-warning-copy span").textContent = message;
};
