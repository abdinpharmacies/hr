/** @odoo-module **/

const escapeHtml = (raw) =>
    String(raw || "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");

export const openBillWizardPrintWindow = (html, format = "a4", {focus = true} = {}) => {
    const specs = format === "pos_80mm" ? "width=360,height=900" : "width=900,height=720";
    const win = window.open("", "_blank", specs);
    if (!win) {
        return null;
    }
    win.document.open();
    win.document.write(html);
    win.document.close();
    if (focus) {
        win.focus();
    }
    return win;
};

export const buildBillWizardTextPreviewHtml = (receiptText, format = "a4", title = "Sales Receipt") => {
    const isPos = format === "pos_80mm";
    const widthStyle = isPos ? "width:74mm;" : "width:210mm;";
    const pageSize = isPos ? "80mm auto" : "A4 portrait";
    const printBodyWidth = isPos ? "80mm" : "210mm";
    const printReceiptWidth = isPos ? "74mm" : "210mm";
    const printReceiptPadding = isPos ? "0 1mm 2mm 1mm" : "0";
    const fontSize = isPos ? "15px" : "18px";
    const widthChars = isPos ? 44 : 80;
    const qtyCol = isPos ? 6 : 9;
    const priceCol = isPos ? 7 : 9;
    const totalCol = isPos ? 8 : 9;
    const itemCol = Math.max(12, widthChars - qtyCol - priceCol - totalCol - 3);
    const divider = ".".repeat(widthChars);
    const lines = String(receiptText || "").replaceAll("\r", "").split("\n");
    const itemHeaderRegex = /^\s*Item\s+Qty\s+Price\s+Total\s*$/;
    const codeRegex = /^[A-Za-z0-9._-]{2,30}$/;

    const renderPlainLine = (line) => `<div class="line">${escapeHtml(line || "")}</div>`;
    const renderFirstItemLine = (line) => {
        if (!line || line.length < itemCol + 2) {
            return `<div class="line line-item-name">${escapeHtml(line || "")}</div>`;
        }
        const item = (line || "").slice(0, itemCol);
        const qty = (line || "").slice(itemCol + 1, itemCol + 1 + qtyCol).trim();
        const price = (line || "").slice(itemCol + 2 + qtyCol, itemCol + 2 + qtyCol + priceCol).trim();
        const total = (line || "").slice(itemCol + 3 + qtyCol + priceCol, itemCol + 3 + qtyCol + priceCol + totalCol).trim();
        return `<div class="line"><span class="line-item-name">${escapeHtml(item)}</span> <span class="line-col qty">${escapeHtml(qty)}</span> <span class="line-col price">${escapeHtml(price)}</span> <span class="line-col total">${escapeHtml(total)}</span></div>`;
    };
    const renderItemEntry = (entryLines) => {
        if (!entryLines.length) {
            return "";
        }
        const out = [renderFirstItemLine(entryLines[0])];
        for (const extra of entryLines.slice(1)) {
            const trimmed = String(extra || "").trim();
            if (!trimmed) {
                out.push(renderPlainLine(""));
                continue;
            }
            if (/^Sold without balance$/i.test(trimmed) || codeRegex.test(trimmed)) {
                out.push(renderPlainLine(extra));
            } else {
                out.push(`<div class="line line-item-name">${escapeHtml(extra || "")}</div>`);
            }
        }
        return out.join("");
    };

    const rendered = [];
    let inItems = false;
    let itemHeaderSeen = false;
    let currentEntry = [];
    const flushEntry = () => {
        if (!currentEntry.length) {
            return;
        }
        rendered.push(renderItemEntry(currentEntry));
        currentEntry = [];
    };

    for (const rawLine of lines) {
        const line = String(rawLine || "");
        if (!itemHeaderSeen && itemHeaderRegex.test(line)) {
            itemHeaderSeen = true;
            rendered.push(renderPlainLine(line));
            continue;
        }
        if (itemHeaderSeen && !inItems && line === divider) {
            inItems = true;
            rendered.push(renderPlainLine(line));
            continue;
        }
        if (inItems) {
            if (line === divider) {
                flushEntry();
                inItems = false;
                rendered.push(renderPlainLine(line));
                continue;
            }
            if (!line.trim()) {
                flushEntry();
                rendered.push(renderPlainLine(line));
                continue;
            }
            currentEntry.push(line);
            continue;
        }
        rendered.push(renderPlainLine(line));
    }
    flushEntry();
    const renderedLinesHtml = rendered.join("");

    return `<!doctype html>
<html>
<head>
<meta charset="utf-8"/>
<title>${escapeHtml(title)}</title>
<style>
    @page {
        size: ${pageSize};
        margin: 0;
    }
    html, body {
        margin: 0;
        padding: 0;
    }
    body { margin: 0; padding: 8px; background: #f5f5f5; }
    .receipt-wrap {
        margin: 0 auto;
        ${widthStyle}
        background: #fff;
        border: 1px solid #ddd;
        box-sizing: border-box;
        padding: 0 2mm 3mm 2mm;
    }
    pre {
        margin: 0;
        display: none;
    }
    .text-lines {
        overflow-x: visible;
        font-family: "Courier New", monospace;
        font-size: ${fontSize};
        line-height: 1.35;
        font-weight: 700;
        color: #111;
    }
    .line {
        white-space: pre;
    }
    .line-item-name {
        font-weight: 800;
    }
    .line-col {
        display: inline-block;
        text-align: right;
    }
    .line-col.qty { width: ${qtyCol}ch; }
    .line-col.price { width: ${priceCol}ch; }
    .line-col.total { width: ${totalCol}ch; }
    .line > .line-item-name:first-child {
        display: inline-block;
        width: ${itemCol}ch;
    }
    @media print {
        html, body {
            width: ${printBodyWidth};
            background: #fff;
        }
        body {
            padding: 0;
        }
        .receipt-wrap {
            border: 0;
            box-sizing: border-box;
            width: ${printReceiptWidth};
            margin: 0 auto;
            padding: ${printReceiptPadding};
        }
    }
</style>
</head>
<body>
    <div class="receipt-wrap">
        <div class="text-lines">${renderedLinesHtml}</div>
    </div>
</body>
</html>`;
};
