/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";

const STOCK_REPORT_SELECTOR = ".o_ab_stock_report";
const DIALOG_CLASS = "o_ab_stock_report_dialog";
const FOOTER_LOAD_MORE_CLASS = "o_ab_stock_report_footer_load_more";
const STORE_BALANCE_TABLE_SELECTOR = ".o_ab_stock_report_store_balance_table";
const STORE_BALANCE_FILTER_SELECTOR = ".o_ab_store_balance_filter";
const LOADING_TRIGGER_SELECTOR = [
    ".o_ab_stock_report_tab",
    ".o_ab_stock_report_load_more_btn",
    ".o_ab_stock_report_clear_date",
    ".o_ab_store_balance_filter_clear",
    ".o_ab_stock_report_footer_load_more_btn",
    "button[name^='action_']",
].join(",");

const TABLE_COLUMNS = [
    _t("MOVEMENT DATE"),
    _t("MOVEMENT TYPE"),
    _t("SALE PRICE"),
    _t("QUANTITY IN LARGE..."),
    _t("STORE"),
    _t("CUSTOMER"),
    _t("EMPLOYEE"),
];

function isOdooHidden(element) {
    return (
        !element
        || element.hidden
        || element.classList.contains("d-none")
        || element.classList.contains("o_invisible_modifier")
        || element.getAttribute("aria-hidden") === "true"
    );
}

function syncFooterLoadMore(report) {
    const modalContent = report.closest(".modal-content");
    const footer = modalContent?.querySelector(".modal-footer");
    const source = report.querySelector(".o_ab_stock_report_load_more");
    if (!footer || !source) {
        return;
    }

    let footerControl = footer.querySelector(`.${FOOTER_LOAD_MORE_CLASS}`);
    if (!footerControl) {
        footerControl = document.createElement("div");
        footerControl.className = FOOTER_LOAD_MORE_CLASS;
        footer.insertBefore(footerControl, footer.firstChild);
    }

    const sourceMeta = source.querySelector(".o_ab_stock_report_load_more_meta");
    const sourceButton = source.querySelector(".o_ab_stock_report_load_more_btn");
    const sourceIsHidden = isOdooHidden(source);
    const sourceButtonIsHidden = isOdooHidden(sourceButton);
    const metaText = (sourceMeta?.textContent || "").trim();
    const buttonText = (sourceButton?.textContent || "").trim();
    const stateKey = JSON.stringify({
        sourceIsHidden,
        sourceButtonIsHidden,
        metaText,
        buttonText,
    });

    if (footerControl.dataset.stateKey === stateKey && footerControl.sourceButton === sourceButton) {
        return;
    }
    footerControl.dataset.stateKey = stateKey;
    footerControl.sourceButton = sourceButton;

    footerControl.hidden = sourceIsHidden;
    footerControl.innerHTML = "";
    if (sourceIsHidden) {
        return;
    }

    const meta = document.createElement("div");
    meta.className = "o_ab_stock_report_footer_load_more_meta";
    meta.textContent = metaText;
    footerControl.appendChild(meta);

    if (sourceButton && !sourceButtonIsHidden) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "btn o_ab_stock_report_footer_load_more_btn";
        button.textContent = buttonText;
        button.addEventListener("click", (event) => {
            event.preventDefault();
            sourceButton.click();
        });
        footerControl.appendChild(button);
    }
}

function syncStoreBalanceFilter(report) {
    const table = report.querySelector(STORE_BALANCE_TABLE_SELECTOR);
    const filter = table?.querySelector(STORE_BALANCE_FILTER_SELECTOR);
    const controlPanel = table?.querySelector(".o_x2m_control_panel");
    if (!table || !filter || !controlPanel) {
        return;
    }

    let leftSlot = controlPanel.querySelector(".o_ab_store_balance_filter_slot");
    if (!leftSlot) {
        leftSlot = document.createElement("div");
        leftSlot.className = "o_ab_store_balance_filter_slot";
        controlPanel.insertBefore(leftSlot, controlPanel.firstChild);
    }
    if (filter.parentElement !== leftSlot) {
        leftSlot.appendChild(filter);
    }
}

function skeletonLine(className = "") {
    const line = document.createElement("span");
    line.className = `o_ab_stock_report_skeleton_line ${className}`.trim();
    return line;
}

function getReportDataTable(report) {
    const visibleTable = [...report.querySelectorAll(".o_ab_stock_report_table")]
        .find((table) => !isOdooHidden(table));
    if (visibleTable) {
        return visibleTable;
    }
    return report.querySelector(".o_ab_stock_report_table");
}

function ensureReportSkeleton(report) {
    const dataTable = getReportDataTable(report);
    if (!dataTable) {
        return null;
    }

    dataTable.classList.add("o_ab_stock_report_loading_target");
    let skeleton = dataTable.querySelector(":scope > .o_ab_stock_report_skeleton");
    if (skeleton) {
        return skeleton;
    }

    skeleton = document.createElement("div");
    skeleton.className = "o_ab_stock_report_skeleton";
    skeleton.setAttribute("aria-hidden", "true");

    const tableHeader = document.createElement("div");
    tableHeader.className = "o_ab_stock_report_skeleton_table_header";
    for (const column of TABLE_COLUMNS) {
        const cell = document.createElement("div");
        cell.className = "o_ab_stock_report_skeleton_th";
        cell.textContent = column;
        tableHeader.appendChild(cell);
    }
    const settings = document.createElement("div");
    settings.className = "o_ab_stock_report_skeleton_th o_ab_stock_report_skeleton_settings";
    settings.innerHTML = '<i class="fa fa-sliders" aria-hidden="true"></i>';
    tableHeader.appendChild(settings);

    const tableBody = document.createElement("div");
    tableBody.className = "o_ab_stock_report_skeleton_table_body";
    for (let rowIndex = 0; rowIndex < 8; rowIndex++) {
        const row = document.createElement("div");
        row.className = "o_ab_stock_report_skeleton_row";
        row.innerHTML = `
            <div class="o_ab_stock_report_skeleton_td date">
                <span class="o_ab_stock_report_skeleton_line w-date"></span>
                <span class="o_ab_stock_report_skeleton_line w-time"></span>
            </div>
            <div class="o_ab_stock_report_skeleton_td type">
                <span class="o_ab_stock_report_skeleton_capsule ${rowIndex % 3 === 1 ? "wide" : ""}"></span>
            </div>
            <div class="o_ab_stock_report_skeleton_td number">
                <span class="o_ab_stock_report_skeleton_line w-price"></span>
            </div>
            <div class="o_ab_stock_report_skeleton_td number">
                <span class="o_ab_stock_report_skeleton_line w-qty"></span>
            </div>
            <div class="o_ab_stock_report_skeleton_td arabic">
                <span class="o_ab_stock_report_skeleton_line ${rowIndex % 2 ? "w-ar-store-short" : "w-ar-store"}"></span>
            </div>
            <div class="o_ab_stock_report_skeleton_td arabic">
                <span class="o_ab_stock_report_skeleton_line ${rowIndex % 2 ? "w-ar-customer" : "w-ar-customer-short"}"></span>
            </div>
            <div class="o_ab_stock_report_skeleton_td employee">
                <span class="o_ab_stock_report_skeleton_line w-employee"></span>
                <span class="o_ab_stock_report_skeleton_line w-employee-short"></span>
            </div>
            <div class="o_ab_stock_report_skeleton_td settings"></div>
        `;
        tableBody.appendChild(row);
    }
    skeleton.append(tableHeader, tableBody);
    dataTable.appendChild(skeleton);
    return skeleton;
}

function setReportLoading(report) {
    if (!report || report.classList.contains("is-loading")) {
        return;
    }
    report.classList.add("is-loading");
    report.setAttribute("aria-busy", "true");
    const modalContent = report.closest(".modal-content");
    modalContent?.classList.add("o_ab_stock_report_is_loading");
    ensureReportSkeleton(report);

    window.setTimeout(() => {
        if (report.isConnected) {
            report.classList.remove("is-loading");
            report.removeAttribute("aria-busy");
            modalContent?.classList.remove("o_ab_stock_report_is_loading");
        }
    }, 300000);
}

function handleStockReportActionClick(event) {
    const button = event.target.closest?.("button");
    if (!button || !button.matches(LOADING_TRIGGER_SELECTOR) || button.disabled) {
        return;
    }

    const report = (
        button.closest(STOCK_REPORT_SELECTOR)
        || button.closest(".modal-content")?.querySelector(STOCK_REPORT_SELECTOR)
    );
    if (!report || isOdooHidden(button)) {
        return;
    }

    setReportLoading(report);
}

function decorateStockReportDialogs(root = document) {
    const reports = [
        ...(root.matches?.(STOCK_REPORT_SELECTOR) ? [root] : []),
        ...(root.querySelectorAll?.(STOCK_REPORT_SELECTOR) || []),
    ];
    for (const report of reports) {
        const dialog = report.closest(".o_dialog");
        if (dialog) {
            dialog.classList.add(DIALOG_CLASS);
        }
        const modalDialog = report.closest(".modal-dialog");
        if (modalDialog) {
            modalDialog.classList.add("o_ab_stock_report_modal_dialog");
        }
        const modalContent = report.closest(".modal-content");
        if (modalContent) {
            modalContent.classList.add("o_ab_stock_report_modal_content");
        }
        syncFooterLoadMore(report);
        syncStoreBalanceFilter(report);
    }
}

let decorateScheduled = false;

function scheduleDecorateStockReportDialogs() {
    if (decorateScheduled) {
        return;
    }
    decorateScheduled = true;
    requestAnimationFrame(() => {
        decorateScheduled = false;
        decorateStockReportDialogs();
    });
}

const observer = new MutationObserver(scheduleDecorateStockReportDialogs);
document.addEventListener("click", handleStockReportActionClick, true);

function observeStockReportDialogs() {
    decorateStockReportDialogs();

    if (document.body instanceof Node) {
        observer.observe(document.body, {
            attributes: true,
            childList: true,
            subtree: true,
        });
        return;
    }

    window.addEventListener("DOMContentLoaded", observeStockReportDialogs, { once: true });
}

observeStockReportDialogs();
