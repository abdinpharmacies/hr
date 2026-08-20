/** @odoo-module **/

const STOCK_REPORT_SELECTOR = ".o_ab_stock_report";
const DIALOG_CLASS = "o_ab_stock_report_dialog";
const FOOTER_LOAD_MORE_CLASS = "o_ab_stock_report_footer_load_more";
const STORE_BALANCE_TABLE_SELECTOR = ".o_ab_stock_report_store_balance_table";
const STORE_BALANCE_FILTER_SELECTOR = ".o_ab_store_balance_filter";

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
