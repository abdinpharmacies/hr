import {Component, useState} from "@odoo/owl";
import {Dialog} from "@web/core/dialog/dialog";
import {_t} from "@web/core/l10n/translation";
import {messageDate} from "./message";

export function locationMapUrl(location) {
    const {latitude, longitude} = location;
    if (!Number.isFinite(latitude) || !Number.isFinite(longitude) || Math.abs(latitude) > 90 || Math.abs(longitude) > 180) return "";
    return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(`${latitude},${longitude}`)}`;
}

export class LocationCard extends Component {
    static template = "ab_crm_sales_workspace.LocationCard";
    static props = {location: Object, provider: {type: String, optional: true}, useDelivery: {type: Function, optional: true}, busy: {type: Boolean, optional: true}};
    setup() { this.state = useState({feedback: ""}); }
    get url() { return locationMapUrl(this.props.location); }
    get timestamp() { return messageDate(this.props.location.timestamp)?.toLocaleString({dateStyle: "medium", timeStyle: "short"}) || ""; }
    async copy() {
        try { await navigator.clipboard.writeText(this.url); this.state.feedback = _t("Location link copied."); }
        catch { this.state.feedback = _t("Could not copy the location. Use Open in Maps to copy the link."); }
    }
}

export class DeliveryLocationPicker extends Component {
    static template = "ab_crm_sales_workspace.DeliveryLocationPicker";
    static components = {Dialog};
    static props = {orders: Array, select: Function, newOrder: Function, close: Function};
    setup() { this.title = _t("Use for delivery"); this.state = useState({busy: false, error: ""}); }
    async choose(id) {
        if (this.state.busy) return;
        this.state.busy = true;
        try { await (id ? this.props.select(id) : this.props.newOrder()); this.props.close(); }
        catch (error) { this.state.error = error.data?.message || error.message; }
        finally { this.state.busy = false; }
    }
}
