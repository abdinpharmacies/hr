/** @odoo-module **/

import { readControl, safePath, saveRequests, uniqueId } from "@ab_navigation_performance/js/core";

export function observeRequests(scope, onError) {
    let observer;
    let run;
    const seen = new WeakSet();
    const collect = (entries) => {
        try {
            const control = readControl(scope);
            if (!control || control.run !== run) return;
            const rows = [];
            for (const entry of entries) {
                if (seen.has(entry)) continue;
                seen.add(entry);
                if (!["fetch", "xmlhttprequest"].includes(entry.initiatorType)) continue;
                const startedAt = performance.timeOrigin + entry.startTime;
                if (startedAt < control.startedAt || !Number.isFinite(entry.duration) || entry.duration < 0) continue;
                const url = new URL(entry.name, location.href);
                if (url.origin !== location.origin || url.pathname.replace(/\/$/, "").endsWith("/ab/performance")) continue;
                rows.push({
                    id: uniqueId(), phase: control.phase, run: control.run, started_at: startedAt,
                    page: safePath(url.pathname), source_page: safePath(location.pathname),
                    kind: entry.initiatorType, duration_ms: Math.round(entry.duration),
                    ttfb_ms: entry.responseStart > 0 ? Math.round(Math.max(0, entry.responseStart - entry.startTime)) : null,
                    status: entry.responseStatus || null,
                });
            }
            if (rows.length) saveRequests(scope, rows);
        } catch {
            observer?.disconnect();
            onError();
        }
    };
    return {
        supported: !!window.PerformanceObserver?.supportedEntryTypes?.includes("resource"),
        sync(control) {
            if (run === control?.run) return;
            observer?.disconnect();
            run = control?.run;
            if (!run || !this.supported) return;
            observer = new PerformanceObserver((list) => collect(list.getEntries()));
            observer.observe({ type: "resource", buffered: true });
        },
        flush() {
            if (observer) collect(observer.takeRecords());
        },
    };
}
