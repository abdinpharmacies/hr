/** @odoo-module **/

const ENABLED_KEY = "ab_storefront_performance_enabled";
const RECORDS_KEY = "ab_storefront_performance_records";
const LIMIT = 100;

function startNavigationPerformance() {
    if (!document.body.classList.contains("ab-storefront")) {
        return;
    }
    let enabled;
    try {
        const option = new URLSearchParams(location.search).get("ab_perf");
        if (option === "0") {
            sessionStorage.removeItem(ENABLED_KEY);
            sessionStorage.removeItem(RECORDS_KEY);
        } else if (option === "1") {
            sessionStorage.setItem(ENABLED_KEY, "1");
        }
        enabled = sessionStorage.getItem(ENABLED_KEY) === "1";
    } catch {
        return;
    }
    if (!enabled || window.abStorefrontPerformance) {
        return;
    }

    const round = (value) => Number.isFinite(value) ? Math.round(value) : null;
    const read = () => {
        try {
            const rows = JSON.parse(sessionStorage.getItem(RECORDS_KEY) || "[]");
            return Array.isArray(rows) ? rows.slice(-LIMIT) : [];
        } catch {
            return [];
        }
    };
    let id = `${performance.timeOrigin}`;
    let restored = false;
    let lcp = null;
    const observers = [];
    const route = (name) => {
        try {
            const url = new URL(name, location.origin);
            if (url.origin !== location.origin) {
                return "external";
            }
            return url.pathname.replace(/\/[a-z0-9-]{20,}(?=\/|$)/gi, "/:record");
        } catch {
            return "unknown";
        }
    };
    const snapshot = () => {
        const navigation = performance.getEntriesByType("navigation")[0];
        const resources = restored ? [] : performance.getEntriesByType("resource");
        const fcp = performance.getEntriesByName("first-contentful-paint")[0];
        return {
            id,
            page: route(location.href),
            captured_at: new Date().toISOString(),
            navigation: restored ? "bfcache" : navigation?.type,
            ttfb_ms: restored ? null : round(navigation?.responseStart),
            document_download_ms: restored ? null : round(navigation?.responseEnd - navigation?.responseStart),
            dom_ready_ms: restored ? null : round(navigation?.domContentLoadedEventEnd || NaN),
            load_ms: restored ? null : round(navigation?.loadEventEnd || NaN),
            fcp_ms: restored ? null : round(fcp?.startTime),
            lcp_candidate_ms: restored ? null : round(lcp ?? NaN),
            resource_count: resources.length,
            transfer_bytes: resources.reduce((total, entry) => total + entry.transferSize, 0),
            slow_resources: [...resources].sort((a, b) => b.duration - a.duration).slice(0, 10).map((entry) => ({
                resource: route(entry.name),
                type: entry.initiatorType,
                duration_ms: round(entry.duration),
            })),
        };
    };
    const save = () => {
        if (!enabled) {
            return;
        }
        const row = snapshot();
        const rows = read().filter((item) => item.id !== id);
        rows.push(row);
        try {
            sessionStorage.setItem(RECORDS_KEY, JSON.stringify(rows.slice(-LIMIT)));
        } catch {
            return row;
        }
        return row;
    };
    if (window.PerformanceObserver?.supportedEntryTypes?.includes("largest-contentful-paint")) {
        const observer = new PerformanceObserver((list) => {
            lcp = list.getEntries().at(-1)?.startTime ?? lcp;
            save();
        });
        observer.observe({ type: "largest-contentful-paint", buffered: true });
        observers.push(observer);
    }
    const onLoad = () => setTimeout(save, 0);
    const onVisibility = () => {
        if (document.visibilityState === "hidden") {
            save();
        }
    };
    const onPageShow = (event) => {
        if (event.persisted) {
            restored = true;
            id = `${performance.timeOrigin}-${Date.now()}`;
            save();
        }
    };
    window.addEventListener("load", onLoad);
    window.addEventListener("pagehide", save);
    window.addEventListener("pageshow", onPageShow);
    document.addEventListener("visibilitychange", onVisibility);
    window.abStorefrontPerformance = {
        report() {
            save();
            const rows = read();
            console.table(rows.map(({ slow_resources, id: recordId, ...row }) => row));
            return rows;
        },
        export() {
            save();
            return JSON.stringify(read(), null, 2);
        },
        stop() {
            enabled = false;
            observers.forEach((observer) => observer.disconnect());
            window.removeEventListener("load", onLoad);
            window.removeEventListener("pagehide", save);
            window.removeEventListener("pageshow", onPageShow);
            document.removeEventListener("visibilitychange", onVisibility);
            try {
                sessionStorage.removeItem(ENABLED_KEY);
                sessionStorage.removeItem(RECORDS_KEY);
            } catch {
                return;
            } finally {
                delete window.abStorefrontPerformance;
            }
        },
    };
    save();
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", startNavigationPerformance, { once: true });
} else {
    startNavigationPerformance();
}
