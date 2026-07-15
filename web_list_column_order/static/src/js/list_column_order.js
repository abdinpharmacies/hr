/** @odoo-module **/

import { ListRenderer } from "@web/views/list/list_renderer";
import { patch } from "@web/core/utils/patch";
import { useBus } from "@web/core/utils/hooks";
import { useSortable } from "@web/core/utils/sortable_owl";
import { onWillStart } from "@odoo/owl";

const SAVE_DELAY = 500;

function debounce(func, wait) {
    let timeout;
    return (...args) => {
        clearTimeout(timeout);
        timeout = setTimeout(() => func(...args), wait);
    };
}

patch(ListRenderer.prototype, {
    setup() {
        super.setup();
        this.columnOrderModel = "list.column.order.pref";
        this.columnOrderPreference = [];
        this.columnOrderSave = debounce(() => this.saveColumnOrderPreference(), SAVE_DELAY);
        this.columnOrderSuppressNextSort = false;

        // Patch point: load the saved preference before the first render so the XML order
        // is replaced by the current user's model/view order without flashing columns.
        onWillStart(async () => {
            await this.loadColumnOrderPreference();
        });

        // Patch point: receive the global list cog-menu reset action and apply it only
        // to the renderer instance matching the current model/view.
        useBus(this.env.bus, "WEB_LIST_COLUMN_ORDER:RESET", async (ev) => {
            const detail = ev.detail || {};
            if (
                detail.modelName === this.props.list.resModel &&
                detail.viewId === this.getColumnOrderViewId()
            ) {
                await this.resetColumnOrderPreference();
            }
        });

        // Patch point: attach Odoo's OWL sortable hook to field header cells only.
        // Selector/action/open-form headers are intentionally excluded from reordering.
        useSortable({
            enable: () => this.canReorderListColumns(),
            ref: this.tableRef,
            elements: "thead tr:first-child th.o_list_column_order_draggable",
            cursor: "grabbing",
            applyChangeOnDrop: true,
            placeholderClasses: ["o_list_column_order_placeholder"],
            onDragStart: () => {
                this.columnOrderDragging = true;
                return true;
            },
            onDragEnd: () => {
                this.columnOrderDragging = false;
            },
            onDrop: (params) => this.onColumnOrderDrop(params),
        });
    },

    getColumnOrderViewId() {
        return this.env.config.viewId || false;
    },

    async loadColumnOrderPreference() {
        try {
            this.columnOrderPreference = await this.orm.call(
                this.columnOrderModel,
                "get_order",
                [this.props.list.resModel, this.getColumnOrderViewId()]
            );
        } catch (error) {
            console.warn("Could not load list column order preference.", error);
            this.columnOrderPreference = [];
        }
    },

    canReorderListColumns() {
        return !this.props.list.model.useSampleModel && !this.editedRecord;
    },

    getColumnPreferenceName(column) {
        return column.type === "field" && column.widget !== "handle" ? column.name : false;
    },

    reorderColumnsByPreference(columns) {
        if (!this.columnOrderPreference.length) {
            return columns;
        }
        const rankByName = new Map(this.columnOrderPreference.map((name, index) => [name, index]));
        const orderedColumns = columns.filter((column) => this.getColumnPreferenceName(column));
        orderedColumns.sort((left, right) => {
            const leftRank = rankByName.has(left.name) ? rankByName.get(left.name) : Number.MAX_SAFE_INTEGER;
            const rightRank = rankByName.has(right.name) ? rankByName.get(right.name) : Number.MAX_SAFE_INTEGER;
            if (leftRank === rightRank) {
                return columns.indexOf(left) - columns.indexOf(right);
            }
            return leftRank - rightRank;
        });
        const reordered = [];
        for (const column of columns) {
            const name = this.getColumnPreferenceName(column);
            reordered.push(name ? orderedColumns.shift() : column);
        }
        return reordered;
    },

    getActiveColumns() {
        // Patch point: preserve Odoo's optional-column and column_invisible filtering,
        // then order only the active field columns according to the saved preference.
        return this.reorderColumnsByPreference(super.getActiveColumns(...arguments));
    },

    getColumnClass(column) {
        const className = super.getColumnClass(...arguments);
        if (this.getColumnPreferenceName(column)) {
            return `${className} o_list_column_order_draggable`;
        }
        return className;
    },

    getColumnOrderFromHeader() {
        const headerCells = this.tableRef.el.querySelectorAll(
            "thead tr:first-child th.o_list_column_order_draggable[data-name]"
        );
        return [...headerCells].map((cell) => cell.dataset.name).filter(Boolean);
    },

    onColumnOrderDrop() {
        const nextOrder = this.getColumnOrderFromHeader();
        if (!nextOrder.length) {
            return;
        }
        this.columnOrderSuppressNextSort = true;
        this.columnOrderPreference = nextOrder;
        this.columns = this.reorderColumnsByPreference(this.columns);
        this.render();
        this.columnOrderSave();
    },

    async saveColumnOrderPreference() {
        try {
            await this.orm.call(this.columnOrderModel, "set_order", [
                this.props.list.resModel,
                this.getColumnOrderViewId(),
                this.columnOrderPreference,
            ]);
        } catch (error) {
            console.warn("Could not save list column order preference.", error);
        }
    },

    async resetColumnOrderPreference() {
        try {
            await this.orm.call(this.columnOrderModel, "reset_order", [
                this.props.list.resModel,
                this.getColumnOrderViewId(),
            ]);
        } catch (error) {
            console.warn("Could not reset list column order preference.", error);
        }
        this.columnOrderPreference = [];
        this.render();
    },

    onClickSortColumn(column) {
        // Patch point: a completed header drag must not also trigger Odoo's column sort.
        if (this.columnOrderDragging || this.columnOrderSuppressNextSort) {
            this.columnOrderSuppressNextSort = false;
            return;
        }
        return super.onClickSortColumn(...arguments);
    },
});
