/** @odoo-module **/

export const LIMIT = 200;
export const REQUEST_LIMIT = 500;
export const prefix = (scope) => `ab_speed_v1:${encodeURIComponent(scope)}:`;
export const controlKey = (scope) => `${prefix(scope)}control`;
export const uniqueId = () => [...crypto.getRandomValues(new Uint32Array(4))].join("-");

export function readControl(scope) {
    const value = JSON.parse(localStorage.getItem(controlKey(scope)) || "null");
    return value && ["before", "after"].includes(value.phase) && Number.isFinite(value.startedAt) && typeof value.run === "string" ? value : null;
}

export function setControl(scope, phase) {
    if (!phase) {
        localStorage.removeItem(controlKey(scope));
        return;
    }
    localStorage.setItem(controlKey(scope), JSON.stringify({ phase, startedAt: Date.now(), run: uniqueId() }));
}

function readRecords(scope, kind, limit) {
    const keyPrefix = `${prefix(scope)}${kind}:`;
    const rows = [];
    for (let index = 0; index < localStorage.length; index++) {
        const key = localStorage.key(index);
        if (!key?.startsWith(keyPrefix)) continue;
        try {
            const row = JSON.parse(localStorage.getItem(key));
            if (row && ["before", "after"].includes(row.phase) && typeof row.page === "string"
                && Number.isFinite(row.started_at) && typeof row.id === "string") rows.push(row);
        } catch {
            continue;
        }
    }
    return rows.sort((a, b) => a.started_at - b.started_at).slice(-limit);
}

export const readRows = (scope) => readRecords(scope, "visit", LIMIT);
export const readRequests = (scope) => readRecords(scope, "request", REQUEST_LIMIT);
export const saveRow = (scope, row) => saveRecords(scope, [row], "visit", LIMIT);
export const saveRequests = (scope, rows) => saveRecords(scope, rows, "request", REQUEST_LIMIT);

function saveRecords(scope, rows, kind, limit) {
    const keyPrefix = `${prefix(scope)}${kind}:`;
    for (const row of rows.slice(-limit)) localStorage.setItem(`${keyPrefix}${row.id}`, JSON.stringify(row));
    const keys = [];
    for (let index = 0; index < localStorage.length; index++) {
        const key = localStorage.key(index);
        if (key?.startsWith(keyPrefix)) keys.push(key);
    }
    if (keys.length > limit) {
        const keep = new Set(readRecords(scope, kind, limit).map((item) => `${keyPrefix}${item.id}`));
        keys.filter((key) => !keep.has(key)).forEach((key) => localStorage.removeItem(key));
    }
}

export const safePath = (path) => path.replace(/\/[a-f0-9-]{32,}(?=\/|$)/gi, "/:record");

export function endpointSummaries(visits, requests, phase) {
    const groups = new Map();
    const samples = visits.filter((row) => row.navigation !== "bfcache").map((row) => ({ ...row, kind: "page", duration_ms: row.load_ms }));
    for (const row of [...samples, ...requests]) {
        if (row.phase !== phase) continue;
        const kind = row.kind || "request";
        const key = JSON.stringify([row.page, kind]);
        if (!groups.has(key)) groups.set(key, { page: row.page, kind, count: 0, durations: [], responses: [], last: row.started_at, source: row.source_page || row.page });
        const group = groups.get(key);
        group.count++;
        for (const [field, target] of [["duration_ms", "durations"], ["ttfb_ms", "responses"]]) {
            if (Number.isFinite(row[field]) && row[field] >= 0) group[target].push(row[field]);
        }
        if (row.started_at >= group.last) {
            group.last = row.started_at;
            group.source = row.source_page || row.page;
        }
    }
    const mean = (values) => values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null;
    return [...groups.values()].map((group) => ({ ...group, mean: mean(group.durations), ttfb: mean(group.responses), max: group.durations.length ? Math.max(...group.durations) : null }))
        .sort((a, b) => (b.mean ?? -1) - (a.mean ?? -1) || a.page.localeCompare(b.page));
}

export function clearRows(scope) {
    setControl(scope, null);
    const keys = [];
    for (let index = 0; index < localStorage.length; index++) {
        const key = localStorage.key(index);
        if (key?.startsWith(prefix(scope))) keys.push(key);
    }
    keys.forEach((key) => localStorage.removeItem(key));
}

export function comparisons(rows, metric) {
    const groups = new Map();
    for (const row of rows) {
        if (row.navigation === "bfcache" || row.background || row.query_key === null) continue;
        const key = JSON.stringify([row.page, row.query_key, row.lang, row.width, row.height, row.dpr, row.navigation]);
        if (!groups.has(key)) groups.set(key, { sample: row, before: [], after: [] });
        const value = row[metric];
        if (typeof value === "number" && Number.isFinite(value) && value >= 0) groups.get(key)[row.phase].push(value);
    }
    const mean = (values) => values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null;
    return [...groups.values()].map((group) => {
        const before = mean(group.before);
        const after = mean(group.after);
        return { ...group, beforeMean: before, afterMean: after, improvement: before > 0 && after !== null ? (before - after) * 100 / before : null };
    }).sort((a, b) => a.sample.page.localeCompare(b.sample.page));
}
