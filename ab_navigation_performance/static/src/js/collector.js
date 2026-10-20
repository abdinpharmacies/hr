/** @odoo-module **/

import { controlKey, readControl, safePath, saveRow, setControl, uniqueId } from "@ab_navigation_performance/js/core";
import { observeRequests } from "@ab_navigation_performance/js/requests";

async function initializeCollector() {
    const launcher = document.getElementById("ab-speed-launcher");
    if (!launcher || location.pathname.replace(/\/$/, "").endsWith("/ab/performance")) return;
    const scope = launcher.dataset.scope;
    const toggle = launcher.querySelector("[data-action='toggle']");
    const reportLink = launcher.querySelector("a");
    reportLink.addEventListener("click", (event) => {
        if (event.button || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
        const monitor = window.open(reportLink.href, "abSpeedMonitor", "popup,width=1100,height=800,resizable=yes,scrollbars=yes");
        if (monitor) {
            event.preventDefault();
            monitor.focus();
        }
    });
    let control;
    let active;
    let timer;
    let lcp = null;
    let id = uniqueId();
    let restored = false;
    let startedAt = performance.timeOrigin;
    const initiallyHidden = document.visibilityState === "hidden";
    const width = window.innerWidth;
    const height = window.innerHeight;
    let observer;
    let queryKey = "";
    const showError = () => { launcher.querySelector("[data-state='error']").hidden = false; };
    const requests = observeRequests(scope, showError);
    launcher.querySelector("[data-state='unsupported']").hidden = requests.supported;
    if (location.search) {
        try {
            const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(location.search));
            queryKey = Array.from(new Uint8Array(digest), (value) => value.toString(16).padStart(2, "0")).join("");
        } catch {
            queryKey = null;
        }
    }
    const number = (value) => Number.isFinite(value) && value >= 0 ? Math.round(value) : null;
    const save = () => {
        if (!active) return;
        try {
            const current = readControl(scope);
            if (current?.run !== active.run) return;
            const nav = performance.getEntriesByType("navigation")[0];
            const fcp = performance.getEntriesByName("first-contentful-paint")[0];
            saveRow(scope, {
                id, phase: active.phase, run: active.run, started_at: startedAt,
                page: safePath(location.pathname),
                query_key: queryKey, lang: document.documentElement.lang,
                width, height, dpr: window.devicePixelRatio, background: initiallyHidden,
                navigation: restored ? "bfcache" : nav?.type || "navigate",
                ttfb_ms: restored ? null : number(nav?.responseStart),
                fcp_ms: restored ? null : number(fcp?.startTime),
                load_ms: restored ? null : number(nav?.loadEventEnd || NaN),
                lcp_candidate_ms: restored ? null : number(lcp ?? NaN),
            });
        } catch {
            active = null;
            observer?.disconnect();
            showError();
        }
    };
    const schedule = () => {
        clearTimeout(timer);
        timer = setTimeout(save, 500);
    };
    const sync = () => {
        try {
            control = readControl(scope);
            launcher.classList.toggle("ab-speed-recording", !!control);
            toggle.setAttribute("aria-pressed", String(!!control));
            launcher.querySelector("[data-state='start']").hidden = !!control;
            launcher.querySelector("[data-state='stop']").hidden = !control;
            launcher.querySelector("[data-state='error']").hidden = true;
            requests.sync(control);
            if (control?.run === active?.run) return;
            active = control && control.startedAt <= performance.timeOrigin ? control : null;
            observer?.disconnect();
            if (!active) return;
            if (window.PerformanceObserver?.supportedEntryTypes?.includes("largest-contentful-paint")) {
                observer = new PerformanceObserver((list) => {
                    lcp = list.getEntries().at(-1)?.startTime ?? lcp;
                    schedule();
                });
                observer.observe({ type: "largest-contentful-paint", buffered: true });
            }
            schedule();
        } catch {
            active = null;
            showError();
        }
    };
    toggle.addEventListener("click", () => {
        try {
            const current = readControl(scope);
            if (current) {
                save();
                requests.flush();
            }
            setControl(scope, current ? null : "before");
            sync();
        } catch {
            showError();
        }
    });
    window.addEventListener("storage", (event) => {
        if (event.key === controlKey(scope) || event.key === null) sync();
    });
    window.addEventListener("load", schedule);
    window.addEventListener("pagehide", () => { save(); requests.flush(); });
    document.addEventListener("visibilitychange", () => {
        if (document.visibilityState === "hidden") { save(); requests.flush(); }
    });
    window.addEventListener("pageshow", (event) => {
        if (event.persisted) {
            restored = true;
            startedAt = Date.now();
            id = uniqueId();
            sync();
            save();
        }
    });
    sync();
}

if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", initializeCollector, { once: true });
else initializeCollector();
