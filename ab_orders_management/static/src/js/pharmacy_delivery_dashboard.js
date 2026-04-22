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

const STORAGE_KEY = "ab_orders_pilot_data";

function saveToLocalStorage(data) {
    try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
    } catch (e) {
        console.warn("Failed to save to localStorage:", e);
    }
}

function loadFromLocalStorage() {
    try {
        const stored = localStorage.getItem(STORAGE_KEY);
        return stored ? JSON.parse(stored) : null;
    } catch (e) {
        console.warn("Failed to load from localStorage:", e);
        return null;
    }
}

export class AbPharmacyDeliveryDashboard extends Component {
    static template = "ab_orders_management.PharmacyDeliveryDashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.loadDashboard = this.loadDashboard.bind(this);
        this.onBranchChange = this.onBranchChange.bind(this);
        this.selectDepartment = this.selectDepartment.bind(this);
        this.toggleSidebar = this.toggleSidebar.bind(this);
        this.openPilotWizard = this.openPilotWizard.bind(this);
        this.onPilotDragStart = this.onPilotDragStart.bind(this);
        this.onPilotDragEnd = this.onPilotDragEnd.bind(this);
        this.onQueueDragOver = this.onQueueDragOver.bind(this);
        this.onQueueDragLeave = this.onQueueDragLeave.bind(this);
        this.onQueueDrop = this.onQueueDrop.bind(this);
        this.queueDropClass = this.queueDropClass.bind(this);
        this.statusDotStyle = this.statusDotStyle.bind(this);
        this.toggleSortByAttendance = this.toggleSortByAttendance.bind(this);
        this.toggleSortByDeliveries = this.toggleSortByDeliveries.bind(this);
        this.openAddOrderWizard = this.openAddOrderWizard.bind(this);
        this.closeAddOrderModal = this.closeAddOrderModal.bind(this);
        this.submitAddOrder = this.submitAddOrder.bind(this);
        this.state = useState({
            loading: true,
            sidebarOpen: true,
            selectedBranchId: 0,
            selectedDepartmentId: 0,
            selectedPilotIds: null,
            draggedPilotId: 0,
            dropTargetStatus: "",
            sortByAttendance: false,
            sortByDeliveries: null,
            addOrderModalOpen: false,
            addOrderPilot: null,
            addOrderForm: {
                order_number: "",
                transaction_type: "delivery",
                branch_id: 0,
                note: "",
            },
            addOrderErrors: {},
            addOrderSubmitting: false,
            payload: {
                branches: [],
                departments: [],
                pilots: [],
                available_pilots: [],
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
        return _t("All departments");
    }

    get allBranchesLabel() {
        return _t("All branches");
    }

    get refreshLabel() {
        return _t("Refresh");
    }

    get dashboardTitle() {
        return _t("Pharmacy Delivery Management");
    }

    get branchesLabel() {
        return _t("Branches");
    }

    get allTargetDepartmentsLabel() {
        return _t("All departments");
    }

    get noPilotsFoundLabel() {
        return _t("No pilots found.");
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

    get sortByLabel() {
        return _t("Sort by deliveries");
    }

    get sortOffLabel() {
        return _t("OFF");
    }

    get sortOnLabel() {
        return _t("ON");
    }

    get deliveriesIconClass() {
        const sortMode = this.state.sortByDeliveries;
        if (sortMode === "asc") {
            return "oi oi-arrow-up";
        }
        if (sortMode === "desc") {
            return "oi oi-arrow-down";
        }
        return "oi oi-minus";
    }

    get activePilotsCount() {
        return (this.state.payload.available_pilots || []).length;
    }

    get availablePilotsLabel() {
        return _t("Available Pilots");
    }

    get visibleSidebarAvailablePilots() {
        const query = String(this.state.query || "").trim().toLowerCase();
        const pilots = this.state.payload.available_pilots || [];
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
        return _t("Close");
    }

    get addOrderModalTitle() {
        return _t("Add Additional Order");
    }

    get addOrderPilotName() {
        return this.state.addOrderPilot?.name || "";
    }

    get addOrderOrderNumberLabel() {
        return _t("Order Number");
    }

    get addOrderOrderNumberPlaceholder() {
        return _t("Enter order number (numbers only)");
    }

    get addOrderTypeLabel() {
        return _t("Transaction Type");
    }

    get addOrderDeliveryTypeLabel() {
        return _t("Transaction Delivery");
    }

    get addOrderClientTypeLabel() {
        return _t("Client Order");
    }

    get addOrderBranchLabel() {
        return _t("Branch");
    }

    get addOrderNoteLabel() {
        return _t("Notes");
    }

    get addOrderNotePlaceholder() {
        return _t("Optional notes");
    }

    get addOrderCancelLabel() {
        return _t("Cancel");
    }

    get addOrderSubmitLabel() {
        return _t("Add Order");
    }

    get addAnotherOrderLabel() {
        return _t("Add Another Order");
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
        return pilots;
    }

    get visibleAvailablePilots() {
        const pilots = this.scopedPilots.filter((pilot) => pilot.status === "free");
        return this.sortPilots(pilots);
    }

    get visibleInDeliveryPilots() {
        const pilots = this.scopedPilots.filter((pilot) => pilot.status === "in_delivery");
        return this.sortPilots(pilots);
    }

    sortPilots(pilots) {
        const sortByAttendance = this.state.sortByAttendance;
        const sortByDeliveries = this.state.sortByDeliveries;
        return pilots.sort((a, b) => {
            if (sortByDeliveries === "asc") {
                const deliveriesA = a.delivery_completed_count || 0;
                const deliveriesB = b.delivery_completed_count || 0;
                if (deliveriesA !== deliveriesB) {
                    return deliveriesA - deliveriesB;
                }
            }
            if (sortByDeliveries === "desc") {
                const deliveriesA = a.delivery_completed_count || 0;
                const deliveriesB = b.delivery_completed_count || 0;
                if (deliveriesA !== deliveriesB) {
                    return deliveriesB - deliveriesA;
                }
            }
            if (sortByAttendance) {
                const orderA = a.sign_in_order || 999999;
                const orderB = b.sign_in_order || 999999;
                if (orderA !== orderB) {
                    return orderA - orderB;
                }
            }
            return String(a.name || "").localeCompare(String(b.name || ""));
        });
    }

    toggleSortByAttendance() {
        this.state.sortByAttendance = !this.state.sortByAttendance;
    }

    toggleSortByDeliveries() {
        const current = this.state.sortByDeliveries;
        if (current === null) {
            this.state.sortByDeliveries = "desc";
        } else if (current === "desc") {
            this.state.sortByDeliveries = "asc";
        } else {
            this.state.sortByDeliveries = null;
        }
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
        let payload = null;
        try {
            payload = await this.orm.call("ab_pharmacy_delivery_pilot", "get_dashboard_payload", [
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
                this.state.selectedPilotIds = (payload.pilots || []).map((pilot) => pilot.id);
            } else {
                const validIds = new Set((payload.pilots || []).map((pilot) => pilot.id));
                this.state.selectedPilotIds = this.state.selectedPilotIds.filter((pilotId) => validIds.has(pilotId));
            }
            this.saveToStorage();
        } catch (error) {
            console.warn("Failed to load from server, using offline data:", error);
            const storedData = this.loadFromStorage();
            if (storedData && storedData.pilots && storedData.pilots.length > 0) {
                this.state.payload = {
                    branches: storedData.branches || [],
                    departments: storedData.departments || [],
                    pilots: storedData.pilots || [],
                    available_pilots: storedData.pilots.filter(p => p.status === "free") || [],
                    selected_branch_id: storedData.selectedBranchId || 0,
                    selected_branch_name: storedData.selectedBranchName || "",
                    selected_department_id: storedData.selectedDepartmentId || 0,
                };
                this.state.selectedBranchId = storedData.selectedBranchId || 0;
                this.state.selectedDepartmentId = storedData.selectedDepartmentId || 0;
                this.state.selectedPilotIds = (storedData.pilots || []).map(p => p.id);
                this.notification.add(_t("Offline mode - showing cached data"), { type: "warning" });
            } else {
                this.notification.add(error?.message || _t("Failed to load dashboard."), { type: "danger" });
            }
        } finally {
            this.state.loading = false;
        }
    }

    saveToStorage() {
        const data = {
            selectedBranchId: this.state.selectedBranchId,
            selectedBranchName: this.state.payload.selected_branch_name || "",
            selectedDepartmentId: this.state.selectedDepartmentId,
            pilots: this.state.payload.pilots || [],
            branches: this.state.payload.branches || [],
            departments: this.state.payload.departments || [],
            timestamp: Date.now(),
        };
        saveToLocalStorage(data);
    }

    loadFromStorage() {
        const stored = loadFromLocalStorage();
        if (stored && stored.pilots && stored.pilots.length > 0) {
            const age = Date.now() - (stored.timestamp || 0);
            const maxAge = 24 * 60 * 60 * 1000;
            if (age < maxAge) {
                return stored;
            }
        }
        return null;
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

    openAddOrderWizard(pilot) {
        this.state.addOrderModalOpen = true;
        this.state.addOrderPilot = pilot;
        this.state.addOrderForm = {
            order_number: "",
            transaction_type: "delivery",
            branch_id: pilot.branch_id || 0,
            note: "",
        };
        this.state.addOrderErrors = {};
    }

    closeAddOrderModal() {
        this.state.addOrderModalOpen = false;
        this.state.addOrderPilot = null;
        this.state.addOrderErrors = {};
    }

    submitAddOrder() {
        const errors = {};
        const orderNum = String(this.state.addOrderForm.order_number || "").trim();
        if (!orderNum) {
            errors.order_number = _t("Order number is required.");
        } else if (!/^\d+$/.test(orderNum)) {
            errors.order_number = _t("Order number must contain only numbers.");
        }
        if (Object.keys(errors).length > 0) {
            this.state.addOrderErrors = errors;
            return;
        }
        const pilot = this.state.addOrderPilot;
        if (!pilot) {
            return;
        }
        this.state.addOrderSubmitting = true;
        (async () => {
            try {
                await this.orm.call(
                    "ab_pharmacy_delivery_pilot",
                    "action_add_additional_assignment",
                    [
                        pilot.id,
                        orderNum,
                        this.state.addOrderForm.transaction_type,
                        this.state.addOrderForm.branch_id || false,
                        String(this.state.addOrderForm.note || "").trim() || false,
                    ]
                );
                this.notification.add(_t("Additional order added successfully."), { type: "success" });
                this.closeAddOrderModal();
                await this.loadDashboard();
            } catch (error) {
                this.notification.add(error?.message || _t("Failed to add additional order."), { type: "danger" });
            } finally {
                this.state.addOrderSubmitting = false;
            }
        })();
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
