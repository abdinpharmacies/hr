/** @odoo-module **/
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { Component, useState, xml, useRef, onWillUnmount } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { Dialog } from "@web/core/dialog/dialog";

// ------------------------------------------------------------------
// Helpers
// ------------------------------------------------------------------

function extractBranchList(raw) {
    if (!raw) return [];
    if (raw.records && Array.isArray(raw.records)) return raw.records;
    if (Array.isArray(raw)) return raw;
    return [];
}

// ------------------------------------------------------------------
// Branch Dialog (click-to-open)
// ------------------------------------------------------------------

class BranchDialog extends Component {
    static template = xml`
        <Dialog size="'md'" title="'Assigned Branches'">
            <div class="ab_branch_dialog">
                <div class="ab_branch_dialog_search">
                    <input type="text" class="o_input" placeholder="Search Branch..." t-model="state.searchText"/>
                </div>
                <div class="ab_branch_dialog_list" t-if="filteredBranches.length">
                    <t t-foreach="filteredBranches" t-as="name" t-key="name_index">
                        <span class="ab_branch_dialog_item"><t t-esc="name"/></span>
                    </t>
                </div>
                <div class="ab_branch_dialog_empty" t-else="">
                    No branches match your search.
                </div>
            </div>
        </Dialog>
    `;
    static components = { Dialog };
    static props = {
        branchNames: { type: Array },
        close: { type: Function, optional: true },
    };

    setup() {
        this.state = useState({ searchText: "" });
    }

    get branchNames() {
        return this.props.branchNames;
    }

    get filteredBranches() {
        const q = this.state.searchText.trim().toLowerCase();
        if (!q) return this.props.branchNames;
        return this.props.branchNames.filter((name) =>
            name.toLowerCase().includes(q)
        );
    }
}

// ------------------------------------------------------------------
// Branch Pills Widget
// Shows "N Branches" pill. Hover shows SaaS popover with branch
// names. Click opens a searchable dialog. Uses searchRead only.
// ------------------------------------------------------------------

class BranchPillsWidget extends Component {
    static template = xml`
        <span class="ab_branch_pills_wrapper"
              t-on-mouseenter="onEnter"
              t-on-mouseleave="onLeave"
              t-on-click="onClick"
              t-ref="wrapper">
            <span class="ab_branch_pills_widget">
                <span class="ab_branch_pills_icon">&#x1F3E2;</span>
                <t t-esc="branchCount"/>
                <t t-if="branchCount === 1"> Branch</t>
                <t t-else=""> Branches</t>
            </span>
        </span>
    `;
    static props = { ...standardFieldProps };

    setup() {
        this._loaded = false;
        this._hideTimer = null;
        this.wrapperRef = useRef("wrapper");
        const record = this.props.record;
        if (record && record.model && record.model.dialog) {
            this.dialog = record.model.dialog;
        } else {
            try {
                this.dialog = useService("dialog");
            } catch (_e) {
                this.dialog = null;
            }
        }
        this.popover = document.createElement("div");
        this.popover.style.position = "absolute";
        this.popover.style.zIndex = "9999";
        this.popover.style.display = "none";
        this.popover.className = "ab_branch_popover";
        this.popover.addEventListener("mouseenter", () => this._cancelHide());
        this.popover.addEventListener("mouseleave", () => {
            this._hideTimer = setTimeout(() => { this._hide(); }, 200);
        });
        document.body.appendChild(this.popover);
        onWillUnmount(() => {
            if (this._hideTimer) clearTimeout(this._hideTimer);
            if (this.popover && this.popover.parentNode) {
                this.popover.parentNode.removeChild(this.popover);
            }
        });
    }

    get branchFieldData() {
        return this.props.record.data[this.props.name];
    }

    get branchCount() {
        const raw = this.branchFieldData;
        if (raw && typeof raw.count === "number") return raw.count;
        return extractBranchList(raw).length;
    }

    _populate(names) {
        this.popover.innerHTML =
            '<div class="ab_branch_popover_arrow"></div>' +
            '<div class="ab_branch_popover_header">Assigned Branches</div>' +
            '<div class="ab_branch_popover_list">' +
            names.map(function (n) {
                return '<div class="ab_branch_popover_item"><span class="ab_branch_popover_bullet">\u2022</span>' +
                    _escapeXml(n) + '</div>';
            }).join("") +
            '</div>';
    }

    _show() {
        this.popover.style.display = "block";
    }

    _hide() {
        this.popover.style.display = "none";
    }

    async _loadNames() {
        if (this._loaded) return;
        this._loaded = true;
        const raw = this.branchFieldData;
        if (!raw) return;
        const ids = [...raw.currentIds];
        if (!ids.length) return;
        const model = this.props.record?.model;
        if (!model || !model.orm || !raw.resModel) return;
        if (typeof raw.load === "function" && raw.count > extractBranchList(raw).length) {
            try { await raw.load({ limit: raw.count }); } catch (_) {}
        }
        try {
            const recs = await model.orm.searchRead(
                raw.resModel,
                [["id", "in", ids]],
                ["display_name", "name"],
                { limit: ids.length }
            );
            this._names = recs.map((r) => r.display_name || r.name || String(r.id));
        } catch (e) {
            console.warn("[BranchPillsWidget] searchRead failed", e);
        }
    }

    async onEnter() {
        this._cancelHide();
        const el = this.wrapperRef.el;
        if (!el) return;
        const rect = el.getBoundingClientRect();
        const estWidth = 280;
        console.log("[BranchPillsWidget] rect:", rect);
        console.log("[BranchPillsWidget] window.scrollX:", window.scrollX, "window.scrollY:", window.scrollY);
        await this._loadNames();
        const names = this._names || [];
        if (!names.length) return;
        const estHeight = Math.min(names.length * 32 + 60, 300) + 16;
        const vw = window.innerWidth;
        const vh = window.innerHeight;
        const scrollX = window.scrollX;
        const scrollY = window.scrollY;
        let left = rect.left + scrollX + rect.width / 2 - estWidth / 2;
        let top = rect.bottom + scrollY + 8;
        left = Math.max(8, Math.min(left, scrollX + vw - estWidth - 8));
        if (top + estHeight > scrollY + vh - 8) {
            top = Math.max(8, rect.top + scrollY - estHeight - 8);
        }
        console.log("[BranchPillsWidget] computed top:", top, "left:", left);
        console.log("[BranchPillsWidget] popover parent:", this.popover.parentNode ? this.popover.parentNode.tagName : "none");
        this._populate(names);
        this.popover.style.left = (left | 0) + "px";
        this.popover.style.top = (top | 0) + "px";
        this._show();
    }

    onLeave() {
        this._hideTimer = setTimeout(() => { this._hide(); }, 200);
    }

    _cancelHide() {
        if (this._hideTimer) {
            clearTimeout(this._hideTimer);
            this._hideTimer = null;
        }
    }

    async onClick(ev) {
        if (!this.dialog) return;
        ev.preventDefault();
        ev.stopPropagation();
        this._cancelHide();
        this._hide();
        await this._loadNames();
        const names = this._names && this._names.length
            ? this._names
            : ["(no branch names available)"];
        this.dialog.add(BranchDialog, { branchNames: names });
    }
}

function _escapeXml(s) {
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

registry.category("fields").add("ab_inventory_branch_pills", {
    component: BranchPillsWidget,
});

// ------------------------------------------------------------------
// KPI Widget
// Displays numeric value with icon + label passed via options.
// ------------------------------------------------------------------

class KpiWidget extends Component {
    static template = xml`
        <span class="ab_kpi_widget">
            <span t-att-class="'ab_kpi_icon ab_kpi_icon--' + props.kpiIcon">
                <t t-esc="props.kpiIconChar"/>
            </span>
            <span class="ab_kpi_value"><t t-esc="formattedValue"/></span>
            <span class="ab_kpi_label"><t t-esc="props.kpiLabel"/></span>
        </span>
    `;
    static props = {
        ...standardFieldProps,
        kpiIcon: { type: String, optional: true },
        kpiIconChar: { type: String, optional: true },
        kpiLabel: { type: String, optional: true },
    };

    get rawValue() {
        return this.props.record.data[this.props.name] || 0;
    }

    get formattedValue() {
        const n = Number(this.rawValue);
        if (isNaN(n)) return "0";
        return n.toLocaleString();
    }
}

registry.category("fields").add("ab_inventory_kpi", {
    component: KpiWidget,
    extractProps: ({ attrs }) => {
        const opts = attrs.options || {};
        const icon = opts.icon || "items";
        const chars = { items: "\u25A0", requests: "\u25B6", processes: "\u2713" };
        const labels = { items: "Items", requests: "Requests", processes: "Processed" };
        return {
            kpiIcon: icon,
            kpiIconChar: chars[icon] || "#",
            kpiLabel: opts.label || labels[icon] || "",
        };
    },
});

// ------------------------------------------------------------------
// State Badge Widget
// Renders state as a colored pill badge.
// ------------------------------------------------------------------

class StateBadgeWidget extends Component {
    static template = xml`
        <span t-att-class="'ab_state_badge ab_state_' + stateValue">
            <t t-esc="stateLabel"/>
        </span>
    `;
    static props = {
        ...standardFieldProps,
    };

    get stateValue() {
        return this.props.record.data[this.props.name] || "";
    }

    get stateLabel() {
        const labels = {
            draft: "Draft",
            submitted: "Submitted",
            cancelled: "Cancelled",
            in_progress: "In Progress",
            completed: "Completed",
        };
        return labels[this.stateValue] || this.stateValue;
    }
}

registry.category("fields").add("ab_inventory_state_badge", {
    component: StateBadgeWidget,
});

// ------------------------------------------------------------------
// Row Title Widget
// Displays record name with subtitle + quick actions dropdown.
// ------------------------------------------------------------------

class RowTitleWidget extends Component {
    static template = xml`
        <div class="ab_row_title">
            <div class="ab_row_title_main">
                <span class="ab_row_title_name">
                    <t t-esc="recordName"/>
                </span>
                <span class="ab_quick_actions_wrapper"
                      t-on-click.stop="toggleMenu"
                      t-ref="actionsWrapper">
                    <button class="ab_quick_actions_btn"
                            t-att-title="'Actions'"
                            aria-label="Actions">&#x22EE;</button>
                     <div t-att-class="'ab_quick_actions_menu' + (state.menuOpen ? ' ab_quick_actions_menu--open' : '')"
                         t-ref="menu">
                        <t t-foreach="actionItems" t-as="action" t-key="action_index">
                            <div class="ab_quick_actions_item"
                                 t-on-click.stop="() => this.handleAction(action)">
                                <span class="ab_quick_actions_item_icon"><t t-esc="action.icon"/></span>
                                <t t-esc="action.label"/>
                            </div>
                        </t>
                    </div>
                </span>
            </div>
            <t t-if="subtitle">
                <span class="ab_row_title_subtitle">
                    <t t-esc="subtitle"/>
                </span>
            </t>
        </div>
    `;
    static props = {
        ...standardFieldProps,
    };

    setup() {
        this.state = useState({ menuOpen: false });
        this.actionsWrapperRef = useRef("actionsWrapper");
        this.menuRef = useRef("menu");
        this.actionService = useService("action");
        this.orm = useService("orm");
        onWillUnmount(() => {
            this._removeClickListener();
        });
    }

    get recordName() {
        return this.props.record.data[this.props.name] || "";
    }

    get requesterName() {
        const raw = this.props.record.data.requester_id;
        if (!raw) return "";
        if (Array.isArray(raw)) return raw[1] || "";
        if (typeof raw === "object") return raw.display_name || raw.name || "";
        return String(raw);
    }

    get submittedDate() {
        const raw = this.props.record.data.submitted_date;
        if (!raw) return null;
        const d = new Date(raw);
        if (isNaN(d.getTime())) return null;
        const now = new Date();
        const diff = now - d;
        const days = Math.floor(diff / (1000 * 60 * 60 * 24));
        if (days === 0) return "Today";
        if (days === 1) return "Yesterday";
        if (days < 7) return days + " days ago";
        return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
    }

    get subtitle() {
        const state = this.props.record.data.state;
        if (state === "draft") {
            return this.requesterName
                ? "Draft by " + this.requesterName
                : "Draft";
        }
        if (state === "submitted") {
            const parts = [];
            if (this.requesterName) parts.push(this.requesterName);
            if (this.submittedDate) parts.push(this.submittedDate);
            return parts.length ? "Submitted by " + parts.join(", ") : "Submitted";
        }
        if (state === "cancelled") {
            return this.requesterName
                ? "Cancelled by " + this.requesterName
                : "Cancelled";
        }
        return this.requesterName ? "by " + this.requesterName : "";
    }

    get actionItems() {
        const state = this.props.record.data.state;
        const isDraft = state === "draft";
        const model = this.props.record.model;
        const resId = this.props.record.resId;

        const items = [];
        items.push({ id: "open", label: "Open", icon: "\u2197", action: "open" });
        if (isDraft) {
            items.push({ id: "edit", label: "Edit", icon: "\u270E", action: "edit" });
        }
        items.push({ id: "duplicate", label: "Duplicate", icon: "\uD83D\uDCCB", action: "duplicate" });
        return items;
    }

    handleAction(action) {
        this.state.menuOpen = false;
        this._removeClickListener();
        const record = this.props.record;
        const modelName = record.model.name;
        const resId = record.resId;
        if (!modelName || !resId) return;

        if (action.action === "open" || action.action === "edit") {
            this.actionService.doAction({
                type: "ir.actions.act_window",
                res_model: modelName,
                res_id: resId,
                views: [[false, "form"]],
                view_mode: "form",
                target: "current",
            });
        } else if (action.action === "duplicate") {
            this.orm.call(modelName, "copy", [resId], {}).then((newId) => {
                this.actionService.doAction({
                    type: "ir.actions.act_window",
                    res_model: modelName,
                    res_id: newId,
                    views: [[false, "form"]],
                    view_mode: "form",
                    target: "current",
                });
            });
        }
    }

    toggleMenu() {
        this.state.menuOpen = !this.state.menuOpen;
        if (this.state.menuOpen) {
            this._addClickListener();
        } else {
            this._removeClickListener();
        }
    }

    _addClickListener() {
        this._removeClickListener();
        this._clickHandler = (ev) => {
            if (this.menuRef.el && !this.menuRef.el.contains(ev.target)) {
                this.state.menuOpen = false;
                this._removeClickListener();
            }
        };
        document.addEventListener("click", this._clickHandler, true);
    }

    _removeClickListener() {
        if (this._clickHandler) {
            document.removeEventListener("click", this._clickHandler, true);
            this._clickHandler = null;
        }
    }
}

registry.category("fields").add("ab_inventory_row_title", {
    component: RowTitleWidget,
});

// ------------------------------------------------------------------
// Deadline Widget
// Color-coded deadline display with urgency indicator.
// ------------------------------------------------------------------

class DeadlineWidget extends Component {
    static template = xml`
        <span t-att-class="'ab_deadline_widget ab_deadline--' + urgencyClass">
            <span class="ab_deadline_icon"><t t-esc="icon"/></span>
            <span t-esc="displayText"/>
        </span>
    `;
    static props = {
        ...standardFieldProps,
    };

    get rawValue() {
        return this.props.record.data[this.props.name];
    }

    get displayText() {
        if (!this.rawValue) return "No deadline";
        const d = new Date(this.rawValue);
        if (isNaN(d.getTime())) return "Invalid date";
        const now = new Date();
        const diff = d - now;
        const days = Math.ceil(diff / (1000 * 60 * 60 * 24));
        if (days < 0) return Math.abs(days) + " day" + (Math.abs(days) === 1 ? "" : "s") + " overdue";
        if (days === 0) return "Due today";
        if (days === 1) return "Due tomorrow";
        if (days <= 7) return "Due in " + days + " days";
        return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
    }

    get icon() {
        if (!this.rawValue) return "\u2014";
        const d = new Date(this.rawValue);
        if (isNaN(d.getTime())) return "\u2014";
        const now = new Date();
        const diff = d - now;
        const days = Math.ceil(diff / (1000 * 60 * 60 * 24));
        if (days < 0) return "\u26A0";
        if (days <= 1) return "\u23F0";
        if (days <= 3) return "\u23F3";
        return "\u2705";
    }

    get urgencyClass() {
        if (!this.rawValue) return "none";
        const d = new Date(this.rawValue);
        if (isNaN(d.getTime())) return "none";
        const now = new Date();
        const diff = d - now;
        const days = Math.ceil(diff / (1000 * 60 * 60 * 24));
        if (days < 0) return "past";
        if (days <= 1) return "urgent";
        if (days <= 3) return "warning";
        return "normal";
    }
}

registry.category("fields").add("ab_inventory_deadline", {
    component: DeadlineWidget,
});
