/** @odoo-module **/

import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useState } from "@odoo/owl";

const STATUS_LABELS = {
    free: _t("Available"),
    in_delivery: _t("In Delivery"),
};

const STATUS_COLORS = {
    free: "#2f8f57",
    in_delivery: "#df7a22",
};

const TYPE_LABELS = {
    delivery: _t("Transaction Delivery"),
    order: _t("Client Order"),
};

const FIFO_FALLBACK = "9999-12-31 23:59:59";

function sortPilotsBySignInTime(pilots) {
    return [...pilots].sort((left, right) => {
        const leftTime = left.sign_in_datetime || FIFO_FALLBACK;
        const rightTime = right.sign_in_datetime || FIFO_FALLBACK;
        if (leftTime !== rightTime) {
            return String(leftTime).localeCompare(String(rightTime));
        }
        const leftOrder = left.sign_in_order || 999999;
        const rightOrder = right.sign_in_order || 999999;
        if (leftOrder !== rightOrder) {
            return leftOrder - rightOrder;
        }
        return String(left.name || "").localeCompare(String(right.name || ""), undefined, {
            sensitivity: "base",
        });
    });
}

export class AbPharmacyDeliveryDashboard extends Component {
    static template = "ab_orders_management.PharmacyDeliveryDashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.loadDashboard = this.loadDashboard.bind(this);
        this.onBranchChange = this.onBranchChange.bind(this);
        this.onDepartmentChange = this.onDepartmentChange.bind(this);
        this.selectDepartment = this.selectDepartment.bind(this);
        this.onSearchInput = this.onSearchInput.bind(this);
        this.toggleSidebar = this.toggleSidebar.bind(this);
        this.selectPilot = this.selectPilot.bind(this);
        this.togglePilotSelection = this.togglePilotSelection.bind(this);
        this.selectAllVisiblePilots = this.selectAllVisiblePilots.bind(this);
        this.openPilotWizard = this.openPilotWizard.bind(this);
        this.onPilotDragStart = this.onPilotDragStart.bind(this);
        this.onPilotDragEnd = this.onPilotDragEnd.bind(this);
        this.onQueueDragOver = this.onQueueDragOver.bind(this);
        this.onQueueDragLeave = this.onQueueDragLeave.bind(this);
        this.onQueueDrop = this.onQueueDrop.bind(this);
        this.departmentFilterClass = this.departmentFilterClass.bind(this);
        this.queueDropClass = this.queueDropClass.bind(this);
        this.statusClassName = this.statusClassName.bind(this);
        this.statusDotStyle = this.statusDotStyle.bind(this);
        this.state = useState({
            loading: true,
            sidebarOpen: true,
            selectedBranchId: 0,
            selectedDepartmentId: 0,
            selectedPilotIds: null,
            draggedPilotId: 0,
            dropTargetStatus: "",
            query: "",
            payload: {
                branches: [],
                departments: [],
                pilots: [],
                available_pilots: [],
                available_pilots_fifo: [],
                in_delivery_pilots: [],
                totals: {},
            },
        });
        onWillStart(async () => {
            await this.loadDashboard();
        });
    }

    get sidebarTitle() {
        return _t("Branch Pilots");
    }

    get sidebarToggleTitle() {
        return this.state.sidebarOpen ? _t("Hide search panel") : _t("Show search panel");
    }

    get sidebarToggleAriaLabel() {
        return _t("Toggle search panel");
    }

    get departmentsLabel() {
        return _t("Departments");
    }

    get allTargetDepartmentsLabel() {
        return _t("All target departments");
    }

    get searchPlaceholder() {
        return _t("Search by any word: pilot, order, department, branch");
    }

    get noPilotsFoundLabel() {
        return _t("No pilots found for the current filter.");
    }

    get dashboardTitle() {
        return _t("Pharmacy Delivery Management");
    }

    get branchFocusLabel() {
        return _t("Branch focus:");
    }

    get departmentFocusLabel() {
        return _t("Department focus:");
    }

    get allBranchesLabel() {
        return _t("All branches");
    }

    get refreshLabel() {
        return _t("Refresh");
    }

    get availablePilotsLabel() {
        return _t("Available Pilots");
    }

    get visibleSidebarAvailablePilots() {
        const query = String(this.state.query || "").trim().toLowerCase();
        const pilots = this.state.payload.available_pilots_fifo || this.state.payload.available_pilots || [];
        if (!query) {
            return pilots;
        }
        const tokens = query.split(/\s+/).map((token) => token.trim()).filter(Boolean);
        if (!tokens.length) {
            return pilots;
        }
        return pilots.filter((pilot) => {
            const searchable = [pilot.name, pilot.department_name, pilot.branch_name]
                .filter(Boolean)
                .map((value) => String(value).toLowerCase());
            return tokens.some((token) => searchable.some((item) => item === token || item.includes(token)));
        });
    }

    get visibleSidebarAvailablePilotsSorted() {
        return sortPilotsBySignInTime(this.visibleSidebarAvailablePilots);
    }

    get availablePilotsSorted() {
        return sortPilotsBySignInTime(this.visibleAvailablePilots);
    }

    get ordersLabel() {
        return _t("Orders:");
    }

    get deliveriesLabel() {
        return _t("Deliveries:");
    }

    get totalLabel() {
        return _t("Total:");
    }

    get changeStatusLabel() {
        return _t("Change status");
    }

    get noFreePilotsLabel() {
        return _t("No free pilots in this branch.");
    }

    get noPilotsSelectedLabel() {
        return _t("No pilots selected.");
    }

    get inDeliveryPilotsLabel() {
        return _t("In Delivery pilots");
    }

    get orderFieldLabel() {
        return _t("Order:");
    }

    get typeFieldLabel() {
        return _t("Type:");
    }

    get branchFieldLabel() {
        return _t("Branch:");
    }

    get closeChangeStatusLabel() {
        return _t("Close / change status");
    }

    get noDeliveryPilotsLabel() {
        return _t("No pilots currently in delivery.");
    }

    get availablePilotsSelectionLabel() {
        return _t("Select All");
    }

    get selectAllPilotsLabel() {
        return _t("Select all");
    }

    get selectAllPilotsAriaLabel() {
        return _t("Select all visible pilots");
    }

    get areAllVisibleSidebarPilotsSelected() {
        const pilots = this.visibleSidebarAvailablePilots;
        return Boolean(pilots.length) && pilots.every((pilot) => this.isPilotSelected(pilot.id));
    }

    get filteredPilots() {
        const query = String(this.state.query || "").trim().toLowerCase();
        const pilots = this.state.payload.pilots || [];
        if (!query) {
            return pilots;
        }
        const tokens = query.split(/\s+/).map((token) => token.trim()).filter(Boolean);
        if (!tokens.length) {
            return pilots;
        }
        return pilots.filter((pilot) => {
            const searchable = [
                pilot.name,
                pilot.pilot_code,
                pilot.shift,
                pilot.branch_name,
                pilot.department_name,
                pilot.status_label,
                pilot.current_assignment?.order_number,
                pilot.current_assignment?.branch_name,
                pilot.current_assignment?.transaction_type_label,
            ]
                .filter(Boolean)
                .map((value) => String(value).toLowerCase());
            return tokens.some((token) => searchable.some((item) => item === token || item.includes(token)));
        });
    }

    get scopedPilots() {
        let pilots = this.filteredPilots;
        if (Array.isArray(this.state.selectedPilotIds)) {
            const selectedIds = new Set(this.state.selectedPilotIds);
            pilots = pilots.filter((pilot) => selectedIds.has(pilot.id));
        }
        return pilots;
    }

    get visibleAvailablePilots() {
        return this.scopedPilots.filter((pilot) => pilot.status === "free");
    }

    get visibleInDeliveryPilots() {
        return this.scopedPilots.filter((pilot) => pilot.status === "in_delivery");
    }

    get selectedBranchLabel() {
        return this.state.payload.selected_branch_name || this.allBranchesLabel;
    }

    get selectedDepartmentLabel() {
        if (!this.state.selectedDepartmentId) {
            return this.allTargetDepartmentsLabel;
        }
        const department = (this.state.payload.departments || []).find(
            (item) => item.id === this.state.selectedDepartmentId
        );
        return department?.name || _t("Target department");
    }

    async loadDashboard() {
        this.state.loading = true;
        try {
            const payload = await this.orm.call("ab_pharmacy_delivery_pilot", "get_dashboard_payload", [
                this.state.selectedBranchId || false,
                this.state.selectedDepartmentId || false,
            ]);
            this.state.payload = payload;
            if (!payload.selected_branch_id) {
                this.state.selectedBranchId = 0;
            } else {
                this.state.selectedBranchId = payload.selected_branch_id;
            }
            this.state.selectedDepartmentId = payload.selected_department_id || 0;
            if (this.state.selectedPilotIds === null) {
                this.state.selectedPilotIds = (payload.available_pilots_fifo || payload.available_pilots || []).map((pilot) => pilot.id);
            } else {
                const validIds = new Set((payload.pilots || []).map((pilot) => pilot.id));
                this.state.selectedPilotIds = this.state.selectedPilotIds.filter((pilotId) => validIds.has(pilotId));
            }
        } catch (error) {
            this.notification.add(error?.message || _t("Failed to load dashboard."), { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    async onBranchChange(ev) {
        this.state.selectedBranchId = Number.parseInt(ev.target.value || 0, 10) || 0;
        this.state.selectedPilotIds = null;
        await this.loadDashboard();
    }

    async onDepartmentChange(ev) {
        this.state.selectedDepartmentId = Number.parseInt(ev.target.value || 0, 10) || 0;
        this.state.selectedPilotIds = null;
        await this.loadDashboard();
    }

    async selectDepartment(departmentId) {
        this.state.selectedDepartmentId = departmentId || 0;
        this.state.selectedPilotIds = null;
        await this.loadDashboard();
    }

    departmentFilterClass(departmentId) {
        return (this.state.selectedDepartmentId || 0) === (departmentId || 0) ? "is-active" : "";
    }

    isPilotSelected(pilotId) {
        return Array.isArray(this.state.selectedPilotIds) && this.state.selectedPilotIds.includes(pilotId);
    }

    togglePilotSelection(pilotId) {
        const selected = new Set(Array.isArray(this.state.selectedPilotIds) ? this.state.selectedPilotIds : []);
        if (selected.has(pilotId)) {
            selected.delete(pilotId);
        } else {
            selected.add(pilotId);
        }
        this.state.selectedPilotIds = [...selected];
    }

    selectAllVisiblePilots() {
        this.state.selectedPilotIds = this.visibleSidebarAvailablePilots.map((pilot) => pilot.id);
    }

    toggleSelectAllVisiblePilots(ev) {
        if (ev.target.checked) {
            this.selectAllVisiblePilots();
        } else {
            this.state.selectedPilotIds = [];
        }
    }

    onSearchInput(ev) {
        this.state.query = ev.target.value || "";
    }

    toggleSidebar() {
        this.state.sidebarOpen = !this.state.sidebarOpen;
    }

    selectPilot(pilotId) {
        this.togglePilotSelection(pilotId);
    }

    async openPilotWizard(pilot) {
        try {
            const action = await this.orm.call(
                "ab_pharmacy_delivery_pilot",
                "action_open_status_wizard_from_dashboard",
                [pilot.id]
            );
            await this.action.doAction(action, {
                onClose: async () => {
                    await this.loadDashboard();
                },
            });
        } catch (error) {
            this.notification.add(error?.message || _t("Failed to open the status wizard."), { type: "danger" });
        }
    }

    onPilotDragStart(pilotId) {
        this.state.draggedPilotId = pilotId;
    }

    onPilotDragEnd() {
        this.state.draggedPilotId = 0;
        this.state.dropTargetStatus = "";
    }

    onQueueDragOver(ev, targetStatus) {
        ev.preventDefault();
        this.state.dropTargetStatus = targetStatus;
    }

    onQueueDragLeave(ev, targetStatus) {
        ev.preventDefault();
        if (this.state.dropTargetStatus === targetStatus) {
            this.state.dropTargetStatus = "";
        }
    }

    async onQueueDrop(ev, targetStatus) {
        ev.preventDefault();
        const pilotId = this.state.draggedPilotId;
        this.state.draggedPilotId = 0;
        this.state.dropTargetStatus = "";
        if (!pilotId) {
            return;
        }
        const pilot = (this.state.payload.pilots || []).find((item) => item.id === pilotId);
        if (!pilot || pilot.status === targetStatus) {
            return;
        }
        await this.openPilotWizard(pilot);
    }

    queueDropClass(targetStatus) {
        return this.state.dropTargetStatus === targetStatus ? "is-drop-target" : "";
    }

    statusClassName(status) {
        return status === "in_delivery" ? "is-in-delivery" : "is-free";
    }

    statusDotStyle(status) {
        return `background:${STATUS_COLORS[status] || "#96a1ad"};`;
    }

}

registry.category("actions").add("ab_orders_management.dashboard", AbPharmacyDeliveryDashboard);
