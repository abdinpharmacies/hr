/** @odoo-module **/

/**
 * Formatting utilities for the sales dashboard.
 */

let cachedLocale = null;
let cachedIsRtl = null;

export function isRtl() {
    if (cachedIsRtl === null) {
        const html = document.documentElement;
        const lang = (html.lang || "").toLowerCase();
        cachedIsRtl = html.dir === "rtl" || lang.startsWith("ar");
    }
    return cachedIsRtl;
}

export function getLocale() {
    if (cachedLocale === null) {
        const lang = (document.documentElement.lang || "").replace("_", "-");
        cachedLocale = isRtl() ? "ar-EG" : (lang || "en-US");
    }
    return cachedLocale;
}

export function money(value) {
    return new Intl.NumberFormat(getLocale(), {
        style: "currency",
        currency: "EGP",
        maximumFractionDigits: 0,
    }).format(Number(value || 0));
}

export function number(value) {
    return new Intl.NumberFormat(getLocale(), { maximumFractionDigits: 0 }).format(Number(value || 0));
}

export function decimal(value) {
    return new Intl.NumberFormat(getLocale(), { maximumFractionDigits: 2 }).format(Number(value || 0));
}

export function pct(value) {
    return `${decimal(value)}%`;
}

export function shortMoney(value) {
    const num = Number(value || 0);
    if (Math.abs(num) >= 1000000) {
        return `${(num / 1000000).toFixed(1)}M`;
    }
    if (Math.abs(num) >= 1000) {
        return `${(num / 1000).toFixed(1)}K`;
    }
    return money(num);
}
