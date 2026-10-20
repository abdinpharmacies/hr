/** @odoo-module **/

import { prefix, readControl, setControl, readRows, readRequests, clearRows, comparisons, endpointSummaries } from "@ab_navigation_performance/js/core";

function initializeMonitor() {
    const root = document.getElementById("ab-speed-monitor");
    if (!root) return;
    const scope = root.dataset.scope;
    const metric = root.querySelector("#ab-speed-metric");
    const phase = root.querySelector("#ab-speed-phase");
    const endpointPhase = root.querySelector("#ab-speed-endpoint-phase");
    const labels = Object.fromEntries([...root.querySelectorAll("[data-label]")].map((element) => [element.dataset.label, element.textContent]));
    const status = (state) => root.querySelectorAll("[data-state]").forEach((element) => { element.hidden = element.dataset.state !== state; });
    const format = (value) => typeof value === "number" && Number.isFinite(value) ? `${Math.round(value).toLocaleString()} ${labels.ms}` : "—";
    const sampleLabel = (sample) => `${sample.width}×${sample.height} · ${sample.lang} · ${labels[sample.navigation] || sample.navigation}${sample.query_key ? ` · #${sample.query_key.slice(0, 8)}` : ""}`;
    const appendRow = (target, values, improvement = null) => {
        const row = root.querySelector("#ab-speed-row").content.firstElementChild.cloneNode(true);
        [...row.children].forEach((cell, index) => {
            if (index >= values.length) cell.remove();
            else cell.textContent = values[index];
        });
        if (improvement !== null) row.children[3].className = improvement > 0 ? "ab-speed-better" : improvement < 0 ? "ab-speed-worse" : "";
        target.appendChild(row);
    };
    const render = () => {
        try {
            const control = readControl(scope);
            const rows = readRows(scope);
            const requests = readRequests(scope);
            status(control?.phase || "idle");
            if (control) phase.value = control.phase;
            phase.disabled = !!control;
            root.querySelector("[data-action='toggle']").setAttribute("aria-pressed", String(!!control));
            root.querySelector("[data-toggle='start']").hidden = !!control;
            root.querySelector("[data-toggle='stop']").hidden = !control;
            const endpoints = endpointSummaries(rows, requests, endpointPhase.value);
            const endpointTable = root.querySelector("#ab-speed-endpoints");
            endpointTable.replaceChildren();
            endpoints.forEach((endpoint) => appendRow(endpointTable, [
                `${endpoint.page}\n${labels[endpoint.kind] || endpoint.kind}`, endpoint.count,
                format(endpoint.mean), format(endpoint.max), format(endpoint.ttfb), endpoint.source,
            ]));
            root.querySelector("[data-empty='endpoints']").hidden = endpoints.length > 0;
            const groups = comparisons(rows, metric.value);
            for (const phase of ["before", "after"]) root.querySelector(`[data-count='${phase}']`).textContent = rows.filter((row) => row.phase === phase).length;
            root.querySelector("[data-count='matched']").textContent = groups.filter((group) => group.before.length && group.after.length).length;
            const table = root.querySelector("#ab-speed-comparison");
            table.replaceChildren();
            groups.forEach((group) => appendRow(table, [
                `${group.sample.page}\n${sampleLabel(group.sample)}`,
                format(group.beforeMean), format(group.afterMean),
                group.improvement === null ? "—" : `${group.improvement > 0 ? "+" : ""}${group.improvement.toFixed(1)}%`,
                `${group.before.length} / ${group.after.length}`,
            ], group.improvement));
            const visits = root.querySelector("#ab-speed-visits");
            visits.replaceChildren();
            rows.slice(-30).reverse().forEach((row) => appendRow(visits, [
                `${new Date(row.started_at).toLocaleTimeString()}\n${labels[row.phase]}`,
                `${row.page}\n${sampleLabel(row)}${row.background ? ` · ${labels.background}` : ""}`,
                format(row.ttfb_ms), format(row.fcp_ms), format(row.load_ms), format(row.lcp_candidate_ms),
            ]));
            root.querySelector("[data-empty='comparison']").hidden = groups.length > 0;
            root.querySelector("[data-empty='visits']").hidden = rows.length > 0;
        } catch {
            status("error");
        }
    };
    root.addEventListener("click", (event) => {
        const action = event.target.closest("[data-action]")?.dataset.action;
        if (!action) return;
        try {
            if (action === "toggle") {
                const control = readControl(scope);
                setControl(scope, control ? null : phase.value);
                if (!control) endpointPhase.value = phase.value;
            }
            if (action === "clear") root.querySelector("#ab-speed-clear").showModal();
            if (action === "export") {
                const rows = readRows(scope);
                const requests = readRequests(scope);
                const report = { version: 2, exported_at: new Date().toISOString(), origin: location.origin, visits: rows, requests, endpoints: { before: endpointSummaries(rows, requests, "before"), after: endpointSummaries(rows, requests, "after") }, comparison: comparisons(rows, metric.value), metric: metric.value };
                const url = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], { type: "application/json" }));
                const link = document.createElement("a");
                link.href = url;
                link.download = `storefront-speed-${Date.now()}.json`;
                link.click();
                setTimeout(() => URL.revokeObjectURL(url), 1000);
            }
            render();
        } catch {
            status("error");
        }
    });
    const dialog = root.querySelector("#ab-speed-clear");
    dialog.addEventListener("close", () => {
        if (dialog.returnValue === "confirm") {
            try { clearRows(scope); } catch { status("error"); return; }
        }
        render();
    });
    metric.addEventListener("change", render);
    endpointPhase.addEventListener("change", render);
    let renderTimer;
    window.addEventListener("storage", (event) => {
        if (event.key === null || event.key.startsWith(prefix(scope))) {
            if (renderTimer) return;
            renderTimer = setTimeout(() => { renderTimer = null; render(); }, 200);
        }
    });
    window.addEventListener("focus", render);
    render();
}

if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", initializeMonitor, { once: true });
else initializeMonitor();
