/** @odoo-module **/
import { Component, useState, onWillUnmount } from "@odoo/owl";
import { xml } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";

/**
 * BatchesLoadingOverlay
 *
 * Premium glassmorphism full-tab loading overlay for batch operations.
 * Usage: <t t-if="condition"><BatchesLoadingOverlay/></t>
 *        or with text: <BatchesLoadingOverlay loadingText="Custom msg"/>
 */
export class BatchesLoadingOverlay extends Component {
    static template = xml`
        <div class="ab-batches-loading-overlay">
            <div class="ab-batches-overlay-backdrop"/>
            <div class="ab-batches-overlay-content">
                <div class="ab-batches-loader">
                    <div class="ab-batches-spinner"/>
                    <div class="ab-batches-loader-text"><t t-esc="props.loadingText"/></div>
                </div>
            </div>
        </div>
    `;

    static props = {
        loadingText: { type: String, optional: true },
    };

    static defaultProps = {
        loadingText: _t("Loading batches..."),
    };
}

/**
 * useBatchLoading
 *
 * OWL hook that provides managed loading state with:
 * - Configurable minimum display duration (prevents flash for fast loads)
 * - Stack-safe show/hide (multiple concurrent calls tracked via counter)
 * - Auto-cleanup on component destruction
 *
 * Usage in setup():
 *   const loading = useBatchLoading({ minDuration: 600 });
 *   loading.show();
 *   await someRpc();
 *   loading.hide();
 *
 * Template:
 *   <t t-if="loading.state.isLoading">
 *     <BatchesLoadingOverlay loadingText={loading.state.text}/>
 *   </t>
 */
export function useBatchLoading(options = {}) {
    const minDuration = options.minDuration || 500;
    const state = useState({ isLoading: false, text: _t("Loading batches...") });
    let counter = 0;
    let timer = null;

    onWillUnmount(() => {
        clearTimeout(timer);
        counter = 0;
        state.isLoading = false;
    });

    function show(text) {
        counter++;
        if (counter === 1) {
            state.text = text || _t("Loading batches...");
            state.isLoading = true;
        }
    }

    function hide() {
        counter = Math.max(0, counter - 1);
        if (counter === 0) {
            clearTimeout(timer);
            timer = setTimeout(() => {
                state.isLoading = false;
            }, minDuration);
        }
    }

    function forceHide() {
        counter = 0;
        clearTimeout(timer);
        state.isLoading = false;
    }

    return { state, show, hide, forceHide };
}
