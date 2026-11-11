import {useChatterFeedback} from "./feedback";
import {Component, useState} from "@odoo/owl";
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
    setup() { this.state = useState({feedback: ""});
        this.feedback = useChatterFeedback(this); }
    get url() { return locationMapUrl(this.props.location); }
    get timestamp() { return messageDate(this.props.location.timestamp)?.toLocaleString({dateStyle: "medium", timeStyle: "short"}) || ""; }
    async copy() {
        try { await navigator.clipboard.writeText(this.url); this.feedback.notify(_t("Location link copied."), {type: "success"}); }
        catch { this.feedback.notify(_t("Could not copy the location. Use Open in Maps to copy the link."), {type: "warning"}); }
    }
}
