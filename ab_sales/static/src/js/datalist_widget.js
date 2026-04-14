/** @odoo-module **/

import FormRenderer from 'web.FormRenderer';

// ---------- helpers (scoped to this AMD module) ----------
function parseJsonList(raw) {
    if (typeof raw === 'string' && raw.trim()) {
        try {
            const data = JSON.parse(raw);
            if (Array.isArray(data)) {
                const seen = new Set();
                const out = [];
                for (const s of data) {
                    if (typeof s === 'string' && s && !seen.has(s)) {
                        seen.add(s);
                        out.push(s);
                    }
                }
                return out;
            }
        } catch (e) {
        }
    }
    return [];
}

function ensureDatalistOn(inputEl, id) {
    let dl = document.getElementById(id);
    if (!dl) {
        dl = document.createElement('datalist');
        dl.id = id;
        document.body.appendChild(dl);
    }
    inputEl.setAttribute('list', id);
    inputEl.setAttribute('autocomplete', 'on');
    return dl;
}

function fillDatalist(dl, values) {
    dl.innerHTML = '';
    values.forEach(v => {
        if (!v) return;
        const opt = document.createElement('option');
        opt.value = v;
        opt.textContent = v;
        dl.appendChild(opt);
    });
}

// Return the first class name beginning with "datalist-" and its suffix
function getDatalistSourceFieldFromClassList(el) {
    if (!el || !el.classList) return null;
    for (const cls of el.classList) {
        if (cls.indexOf('datalist-') === 0 && cls.length > 9) {
            return cls.slice(9); // after "datalist-"
        }
    }
    return null;
}

// ---------- RENDERER ----------
FormRenderer.include({
    events: _.extend({}, FormRenderer.prototype.events, {
        // dynamic datalist activation for any input with a class that starts with "datalist-"
        'focusin input': '_maybeActivateDatalist',
        'mousedown input': '_maybeActivateDatalist',
        // 'click input': '_maybeActivateDatalist',
    }),

    _maybeActivateDatalist: function (e) {
        const input = e.target && e.target.closest('input');
        if (!input) return;

        const sourceField = getDatalistSourceFieldFromClassList(input);
        if (!sourceField) return; // input is not marked with datalist-*

        // Build a stable datalist id per input+source
        if (!input.dataset.dlId) {
            const name = input.getAttribute('name') || '';
            input.dataset.dlId = `dl_${sourceField}_${name}_${Date.now().toString(36)}`;
        }
        const dl = ensureDatalistOn(input, input.dataset.dlId);

        const state = this.state || {};
        let raw = '';

// ✅ Check if field exists in state.data
        if (state.data) {
            if (Object.prototype.hasOwnProperty.call(state.data, sourceField)) {
                raw = state.data[sourceField];
            } else {
                console.error(
                    `[datalist] ⚠️ Field "${sourceField}" not found in state.data for model "${state.model}" (res_id: ${state.res_id || 'new record'})`
                );
                raw = '';  // ensure safe empty value
            }
        } else {
            console.error(
                `[datalist] ⚠️ state.data is undefined when trying to access "${sourceField}" (model: ${state.model || 'unknown'})`
            );
        }
        let values = parseJsonList(raw);

        // ✅ If datalist is falsy or empty → clear it
        if (!values || !values.length) {
            dl.innerHTML = '';
        }

        // If we already have values from the current state, render and stop
        if (values.length) {
            fillDatalist(dl, values);
        }
    },

});
