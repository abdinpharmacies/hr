/** @odoo-module **/
import { ListController } from "@web/views/list/list_controller";
import { listView } from "@web/views/list/list_view";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { onMounted, onPatched, onWillUnmount, useEffect } from "@odoo/owl";

class MappingListController extends ListController {
    setup() {
        super.setup();

        this.STORAGE_KEY_SIZE = "ab_mapping_page_size";
        this.STORAGE_KEY_PAGE = "ab_mapping_page_num";
        this.actionService = useService("action");

        this._keyHandler = this._onKeyDown.bind(this);

        onMounted(() => this._build());
        onPatched(() => this._refresh());
        onWillUnmount(() => {
            window.removeEventListener("keydown", this._keyHandler);
            this._cleanup();
        });

        window.addEventListener("keydown", this._keyHandler);
    }

    // ------------------------------------------------------------------
    //  Storage
    // ------------------------------------------------------------------
    _loadPageSize() {
        return parseInt(localStorage.getItem(this.STORAGE_KEY_SIZE) || "25", 10);
    }
    _savePageSize(v) {
        localStorage.setItem(this.STORAGE_KEY_SIZE, String(v));
    }
    _savePage(v) {
        localStorage.setItem(this.STORAGE_KEY_PAGE, String(v));
    }

    // ------------------------------------------------------------------
    //  Helpers
    // ------------------------------------------------------------------
    get _pager() {
        return this.env.config.pagerProps;
    }
    get _page() {
        const p = this._pager;
        return p && p.limit ? Math.floor(p.offset / p.limit) + 1 : 1;
    }
    get _totalPages() {
        const p = this._pager;
        return p && p.limit && p.total ? Math.ceil(p.total / p.limit) : 1;
    }

    // ------------------------------------------------------------------
    //  Lifecycle
    // ------------------------------------------------------------------
    _build() {
        this._hideDefaultPager();
        this._injectFooter();
        this._refresh();
        this._listenDoubleClick();
    }
    _cleanup() {
        const footer = document.getElementById("ab-mapping-footer");
        if (footer) footer.remove();
        const style = document.getElementById("ab-mapping-pager-hide");
        if (style) style.remove();
    }

    _refresh() {
        const p = this._pager;
        if (!p) return;
        this._renderFooter(p);
    }

    _hideDefaultPager() {
        const style = document.createElement("style");
        style.id = "ab-mapping-pager-hide";
        style.textContent = `
            body:has(#ab-mapping-footer) .o_control_panel .o_pager { display:none !important; }
            body:has(#ab-mapping-footer) .o_control_panel .o_pager_compact { display:none !important; }
        `;
        document.head.appendChild(style);
    }

    _injectFooter() {
        let el = document.getElementById("ab-mapping-footer");
        if (el) return;
        el = document.createElement("div");
        el.id = "ab-mapping-footer";
        el.className = "ab-mapping-footer";
        const list = document.querySelector(".o_list_view");
        if (list && list.parentNode) {
            list.parentNode.insertBefore(el, list.nextSibling);
        }
    }

    _renderFooter(p) {
        const footer = document.getElementById("ab-mapping-footer");
        if (!footer) return;

        const dir = document.documentElement.getAttribute("dir") || "ltr";
        const rtl = dir === "rtl";
        const page = this._page;
        const total = p.total || 0;
        const limit = p.limit || this._loadPageSize();
        const totalP = this._totalPages;
        const from = p.offset + 1;
        const to = Math.min(p.offset + limit, total);

        if (!total) {
            footer.classList.add("ab-mapping-footer--empty");
            footer.innerHTML = '<div class="ab-mapping-empty"><span class="ab-mapping-empty-icon">📋</span><span>No suppliers found</span></div>';
            return;
        }
        footer.classList.remove("ab-mapping-footer--empty");

        const prevDisabled = page <= 1;
        const nextDisabled = page >= totalP;

        footer.innerHTML = `
            <div class="ab-mapping-pager-inner">
                <div class="ab-mapping-pager-left">
                    <span class="ab-mapping-row-count">
                        Showing <strong>${from}</strong>–<strong>${to}</strong> of <strong>${total}</strong> suppliers
                    </span>
                </div>
                <div class="ab-mapping-pager-center">
                    <button class="ab-mapping-pager-btn ab-mapping-pager-prev" ${prevDisabled ? "disabled" : ""} aria-label="Previous page">
                        ${rtl ? "→" : "←"} <span>Previous</span>
                    </button>
                    <span class="ab-mapping-pager-indicator">${page} / ${totalP}</span>
                    <button class="ab-mapping-pager-btn ab-mapping-pager-next" ${nextDisabled ? "disabled" : ""} aria-label="Next page">
                        <span>Next</span> ${rtl ? "←" : "→"}
                    </button>
                </div>
                <div class="ab-mapping-pager-right">
                    <span class="ab-mapping-page-size-wrap">
                        <select class="ab-mapping-page-size">
                            ${[10, 25, 50, 100].map(n =>
                                `<option value="${n}" ${n === limit ? "selected" : ""}>${n}</option>`
                            ).join("")}
                        </select>
                        per page
                    </span>
                </div>
            </div>
        `;

        footer.querySelector(".ab-mapping-pager-prev")?.addEventListener("click", () => this._go(page - 1));
        footer.querySelector(".ab-mapping-pager-next")?.addEventListener("click", () => this._go(page + 1));
        footer.querySelector(".ab-mapping-page-size")?.addEventListener("change", (e) => this._resize(parseInt(e.target.value)));
    }

    // ------------------------------------------------------------------
    //  Navigation
    // ------------------------------------------------------------------
    async _go(page) {
        const p = this._pager;
        if (!p || page < 1 || page > this._totalPages) return;
        this._savePage(page);
        const offset = (page - 1) * p.limit;
        await p.onUpdate({ offset, limit: p.limit }, true);
    }

    async _resize(limit) {
        const p = this._pager;
        if (!p) return;
        this._savePageSize(limit);
        this._savePage(1);
        await p.onUpdate({ offset: 0, limit }, true);
    }

    // ------------------------------------------------------------------
    //  Keyboard
    // ------------------------------------------------------------------
    _onKeyDown(ev) {
        const tag = ev.target.tagName;
        if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
        if (ev.key === "ArrowLeft") {
            ev.preventDefault();
            this._go(this._page - 1);
        } else if (ev.key === "ArrowRight") {
            ev.preventDefault();
            this._go(this._page + 1);
        }
    }

    // ------------------------------------------------------------------
    //  Double-click
    // ------------------------------------------------------------------
    _listenDoubleClick() {
        const renderer = document.querySelector(".o_list_renderer");
        if (!renderer) return;
        renderer.addEventListener("dblclick", (ev) => {
            const row = ev.target.closest(".o_data_row");
            if (!row) return;
            const resId = parseInt(row.dataset.resId);
            if (!resId) return;
            this.actionService.doAction({
                type: "ir.actions.act_window",
                res_model: "ab.supplier.mapping",
                res_id: resId,
                views: [[false, "form"]],
            });
        });
    }
}

const mappingListView = {
    ...listView,
    Controller: MappingListController,
};

registry.category("views").add("ab_supplier_mapping", mappingListView);
