/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useState } from "@odoo/owl";

class AbPosAction extends Component {
    static template = "ab_pos.AbPosAction";

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this._productSearchTimer = null;

        this.state = useState({
            loading: true,
            stores: [],
            selectedStoreId: null,
            customerQuery: "",
            customers: [],
            selectedCustomerId: null,
            productQuery: "",
            products: [],
            lines: [], // {product, qty}
            saving: false,
        });

        this.selectCustomer = this.selectCustomer.bind(this);
        this.addProduct = this.addProduct.bind(this);
        this.incLine = this.incLine.bind(this);
        this.decLine = this.decLine.bind(this);
        this.save = this.save.bind(this);

        onWillStart(async () => {
            await this.loadInit();
        });
    }

    async loadInit() {
        this.state.loading = true;
        try {
            const stores = await this.orm.call("ab_pos.api", "get_stores", [], { limit: 200 });
            this.state.stores = stores || [];
            this.state.selectedStoreId = this.state.stores[0]?.id || null;

            this.state.products = await this.orm.call("ab_pos.api", "search_products", [], {
                query: "",
                limit: 50,
            });
        } catch (e) {
            this.notification.add(e?.message || "Failed to load Ab POS data.", { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    productLabel(p) {
        return p.name || p.product_card_name || `${p.code || ""}`.trim() || `#${p.id}`;
    }

    formatPrice(value) {
        const numberValue = typeof value === "number" ? value : parseFloat(value || 0);
        if (Number.isFinite(numberValue)) {
            return numberValue.toFixed(2);
        }
        return "0.00";
    }

    async onSearchProducts(ev) {
        this.state.productQuery = ev.target.value || "";
        if (this._productSearchTimer) {
            clearTimeout(this._productSearchTimer);
        }
        this._productSearchTimer = setTimeout(async () => {
            try {
                const query = this.state.productQuery;
                this.state.products = await this.orm.call("ab_pos.api", "search_products", [], {
                    query,
                    limit: 50,
                });
            } catch (e) {
                this.notification.add(e?.message || "Failed to search products.", { type: "danger" });
            }
        }, 150);
    }

    async onSearchCustomers(ev) {
        this.state.customerQuery = ev.target.value || "";
        this.state.customers = await this.orm.call("ab_pos.api", "search_customers", [], {
            query: this.state.customerQuery,
            limit: 50,
        });
    }

    selectCustomer(customer) {
        this.state.selectedCustomerId = customer?.id || null;
    }

    addProduct(product) {
        const existing = this.state.lines.find((l) => l.product.id === product.id);
        if (existing) {
            existing.qty += 1;
            return;
        }
        this.state.lines.push({ product, qty: 1 });
    }

    incLine(line) {
        line.qty += 1;
    }

    decLine(line) {
        line.qty -= 1;
        if (line.qty <= 0) {
            this.state.lines.splice(this.state.lines.indexOf(line), 1);
        }
    }

    get total() {
        return this.state.lines.reduce(
            (sum, l) => sum + Number(l.product.default_price || 0) * Number(l.qty || 0),
            0
        );
    }

    async save() {
        if (!this.state.selectedStoreId) {
            this.notification.add("Select a store first.", { type: "warning" });
            return;
        }
        if (!this.state.lines.length) {
            this.notification.add("Add at least one product.", { type: "warning" });
            return;
        }

        this.state.saving = true;
        try {
            const payload = {
                store_id: this.state.selectedStoreId,
                customer_id: this.state.selectedCustomerId,
                lines: this.state.lines.map((l) => ({
                    product_id: l.product.id,
                    qty: l.qty,
                    qty_str: String(l.qty),
                    sell_price: l.product.default_price,
                })),
                description: "Created from Ab POS (simple)",
            };
            const res = await this.orm.call("ab_pos.api", "create_sale", [], { payload });
            this.notification.add(`Saved: #${res.header_id}`, { type: "success" });
            this.state.lines.splice(0, this.state.lines.length);
        } catch (e) {
            this.notification.add(e?.message || "Failed to save.", { type: "danger" });
        } finally {
            this.state.saving = false;
        }
    }
}

registry.category("actions").add("ab_pos.action", AbPosAction);
