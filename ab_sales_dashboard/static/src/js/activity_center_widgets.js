/** @odoo-module **/

import { Component, xml } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

// ─── Helpers ──────────────────────────────────────────────

function fmt(v) {
    if (v === 0 || v === false || v === null || v === undefined) return "0";
    return new Intl.NumberFormat("en-US").format(v);
}

function fmtBytes(bytes) {
    const v = parseInt(bytes, 10) || 0;
    if (v < 1024) return fmt(v) + " B";
    if (v < 1048576) return (v / 1024).toFixed(1) + " KB";
    return (v / 1048576).toFixed(1) + " MB";
}

function relativeTime(dateStr) {
    if (!dateStr) return { label: _t("Unknown") };
    const d = new Date(dateStr);
    const now = new Date();
    const diffMs = now - d;
    const diffH = diffMs / 3600000;
    if (diffH < 1) return { label: _t("Just now") };
    if (diffH < 24) return { label: Math.floor(diffH) + " " + _t("h ago") };
    const diffD = diffH / 24;
    if (diffD < 1) return { label: _t("Today") };
    if (diffD < 2) return { label: _t("Yesterday") };
    if (diffD < 30) return { label: Math.floor(diffD) + " " + _t("d ago") };
    return { label: Math.floor(diffD) + " " + _t("d ago") };
}

function formatTime(dateStr) {
    if (!dateStr) return "";
    try {
        const d = new Date(dateStr);
        return d.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: false });
    } catch { return ""; }
}

function formatShortDate(dateStr) {
    if (!dateStr) return "";
    try {
        const d = new Date(dateStr);
        return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
    } catch { return ""; }
}

function titleCase(str) {
    if (!str) return "";
    return String(str).replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
}

const EVENT_TYPE_CONFIG = {
    dashboard_read: {
        icon: "fa-bar-chart",
        color: "violet",
    },
    dashboard_refresh: {
        icon: "fa-refresh",
        color: "cyan",
    },
    summary_read: {
        icon: "fa-file-text-o",
        color: "blue",
    },
    archive_read: {
        icon: "fa-archive",
        color: "amber",
    },
    product_report_read: {
        icon: "fa-cube",
        color: "blue",
    },
    reconciliation_run: {
        icon: "fa-exchange",
        color: "emerald",
    },
};

const COVERAGE_CONFIG = {
    complete: { icon: "fa-check-circle", cls: "ac-badge--complete", label: _t("Complete") },
    partial: { icon: "fa-exclamation-triangle", cls: "ac-badge--partial", label: _t("Partial") },
    unavailable: { icon: "fa-times-circle", cls: "ac-badge--unavailable", label: _t("Unavailable") },
    not_applicable: { icon: "fa-minus-circle", cls: "ac-badge--na", label: _t("N/A") },
};

const PERF_THRESHOLDS = [
    { max: 500, cls: "ac-perf--fast", label: _t("Fast") },
    { max: 2000, cls: "ac-perf--moderate", label: _t("Moderate") },
    { max: 10000, cls: "ac-perf--slow", label: _t("Slow") },
    { max: Infinity, cls: "ac-perf--critical", label: _t("Critical") },
];

function perfConfig(ms) {
    const val = parseInt(ms, 10) || 0;
    return PERF_THRESHOLDS.find(t => val <= t.max) || PERF_THRESHOLDS[PERF_THRESHOLDS.length - 1];
}

const SCOPE_LABELS = {
    single_store: _t("1 Store"),
    "2_10_stores": _t("2–10 Stores"),
    "11_50_stores": _t("11–50 Stores"),
    "51_100_stores": _t("51–100 Stores"),
    over_100_stores: _t("100+ Stores"),
    all_stores: _t("All Stores"),
};

// ══════════════════════════════════════════════════════════════
// 1. EVENT TYPE — Rich identity block
// ══════════════════════════════════════════════════════════════
class ActivityEventType extends Component {
    static template = xml`
        <div class="ac-event" t-att-class="'ac-event--' + eventColor">
            <div class="ac-event__icon">
                <i t-att-class="'fa ' + eventIcon"/>
            </div>
            <div class="ac-event__body">
                <span class="ac-event__title" t-esc="eventTitle"/>
                <span class="ac-event__meta" t-esc="reportModeLabel"/>
            </div>
        </div>
    `;
    static props = { name: String, record: Object, readonly: Boolean };

    get eventKey() {
        const raw = this.props.record.data.event_type || "";
        return String(raw).toLowerCase().replace(/\s+/g, "_");
    }
    get eventConfig() { return EVENT_TYPE_CONFIG[this.eventKey] || { icon: "fa-file-o", color: "default" }; }
    get eventIcon() { return this.eventConfig.icon; }
    get eventColor() { return this.eventConfig.color; }
    get eventTitle() { return titleCase(this.props.record.data.event_type); }
    get reportModeLabel() { return titleCase(this.props.record.data.report_mode); }
}

registry.category("fields").add("list.activity_event_type", { component: ActivityEventType });

// ══════════════════════════════════════════════════════════════
// 2. STATUS — Premium badge with icon + color
// ══════════════════════════════════════════════════════════════
class ActivityStatus extends Component {
    static template = xml`
        <span class="ac-badge" t-att-class="badgeCls">
            <i class="fa" t-att-class="badgeIcon"/>
            <t t-esc="badgeLabel"/>
        </span>
    `;
    static props = { name: String, record: Object, readonly: Boolean };

    get raw() {
        const v = this.props.record.data[this.props.name];
        return String(v || "not_applicable").toLowerCase().replace(/\s+/g, "_");
    }
    get cfg() { return COVERAGE_CONFIG[this.raw] || COVERAGE_CONFIG.not_applicable; }
    get badgeCls() { return this.cfg.cls; }
    get badgeIcon() { return this.cfg.icon; }
    get badgeLabel() { return this.cfg.label; }
}

registry.category("fields").add("list.activity_status", { component: ActivityStatus });

// ══════════════════════════════════════════════════════════════
// 3. TIME — Relative + absolute hierarchy
// ══════════════════════════════════════════════════════════════
class ActivityTime extends Component {
    static template = xml`
        <div class="ac-time">
            <span class="ac-time__rel" t-esc="rel"/>
            <span class="ac-time__abs">
                <i class="fa fa-calendar ac-time__icon"/>
                <t t-esc="absDate"/>
                <t t-esc="absTime"/>
            </span>
        </div>
    `;
    static props = { name: String, record: Object, readonly: Boolean };

    get raw() { return this.props.record.data[this.props.name]; }
    get rel() { return relativeTime(this.raw).label; }
    get absDate() { return formatShortDate(this.raw); }
    get absTime() { return this.raw ? formatTime(this.raw) : ""; }
}

registry.category("fields").add("list.activity_time", { component: ActivityTime });

// ══════════════════════════════════════════════════════════════
// 4. PERFORMANCE — Duration chip with color threshold
// ══════════════════════════════════════════════════════════════
class ActivityPerformance extends Component {
    static template = xml`
        <span class="ac-perf" t-att-class="perfCls">
            <i class="fa fa-bolt"/>
            <span class="ac-perf__val" t-esc="value"/>
            <span class="ac-perf__label" t-esc="label"/>
        </span>
    `;
    static props = { name: String, record: Object, readonly: Boolean };

    get raw() { return parseInt(this.props.record.data[this.props.name], 10) || 0; }
    get cfg() { return perfConfig(this.raw); }
    get perfCls() { return this.cfg.cls; }
    get value() { return fmt(this.raw) + " ms"; }
    get label() { return this.cfg.label; }
}

registry.category("fields").add("list.activity_performance", { component: ActivityPerformance });

// ══════════════════════════════════════════════════════════════
// 5. RESULT SIZE — Formatted bytes pill
// ══════════════════════════════════════════════════════════════
class ActivityResultSize extends Component {
    static template = xml`
        <span class="ac-size">
            <i class="fa fa-database"/>
            <t t-esc="formatted"/>
        </span>
    `;
    static props = { name: String, record: Object, readonly: Boolean };

    get formatted() { return fmtBytes(this.props.record.data[this.props.name]); }
}

registry.category("fields").add("list.activity_result_size", { component: ActivityResultSize });

// ══════════════════════════════════════════════════════════════
// 6. SCOPE — Branch scope badge
// ══════════════════════════════════════════════════════════════
class ActivityScope extends Component {
    static template = xml`
        <span class="ac-scope" t-att-class="scopeCls">
            <i class="fa" t-att-class="scopeIcon"/>
            <t t-esc="scopeLabel"/>
            <span class="ac-scope__count" t-if="count" t-esc="count"/>
        </span>
    `;
    static props = { name: String, record: Object, readonly: Boolean };

    get raw() {
        const v = this.props.record.data[this.props.name];
        return String(v || "").toLowerCase().replace(/\s+/g, "_");
    }
    get scopeLabel() { return SCOPE_LABELS[this.raw] || titleCase(this.props.record.data[this.props.name]); }
    get count() {
        const c = this.props.record.data.selected_store_count;
        if (c && parseInt(c, 10) > 0) return fmt(c);
        return "";
    }
    get scopeIcon() {
        if (this.raw === "all_stores") return "fa-globe";
        if (this.raw === "single_store") return "fa-building-o";
        return "fa-building-o";
    }
    get scopeCls() {
        if (this.raw === "all_stores") return "ac-scope--all";
        if (this.raw === "single_store") return "ac-scope--single";
        if (this.raw.startsWith("2_") || this.raw.startsWith("11_")) return "ac-scope--multi";
        return "ac-scope--large";
    }
}

registry.category("fields").add("list.activity_scope", { component: ActivityScope });

// ══════════════════════════════════════════════════════════════
// 7. RANGE BUCKET — Date range badge
// ══════════════════════════════════════════════════════════════
class ActivityRange extends Component {
    static template = xml`
        <span class="ac-range">
            <i class="fa fa-calendar"/>
            <t t-esc="label"/>
        </span>
    `;
    get label() {
        const v = this.props.record.data[this.props.name];
        if (!v) return "";
        if (v === "1_7_days") return "1–7 " + _t("days");
        if (v === "8_31_days") return "8–31 " + _t("days");
        if (v === "32_60_days") return "32–60 " + _t("days");
        if (v === "61_90_days") return "61–90 " + _t("days");
        return titleCase(v);
    }
}

registry.category("fields").add("list.activity_range", { component: ActivityRange });

// ══════════════════════════════════════════════════════════════
// 8. REPORT MODE — Small badge
// ══════════════════════════════════════════════════════════════
class ActivityReportMode extends Component {
    static template = xml`
        <span class="ac-mode" t-att-class="modeCls">
            <i class="fa" t-att-class="modeIcon"/>
            <t t-esc="label"/>
        </span>
    `;
    static props = { name: String, record: Object, readonly: Boolean };

    get raw() {
        return String(this.props.record.data[this.props.name] || "").toLowerCase().replace(/\s+/g, "_");
    }
    get label() { return titleCase(this.props.record.data[this.props.name]); }
    get modeIcon() {
        const m = {
            full: "fa-file-text-o",
            summary: "fa-file-o",
            archive: "fa-archive",
            product_report: "fa-cube",
            reconciliation: "fa-exchange",
        };
        return m[this.raw] || "fa-file-o";
    }
    get modeCls() {
        const m = {
            full: "ac-mode--full",
            summary: "ac-mode--summary",
            archive: "ac-mode--archive",
            product_report: "ac-mode--product",
            reconciliation: "ac-mode--recon",
        };
        return m[this.raw] || "";
    }
}

registry.category("fields").add("list.activity_report_mode", { component: ActivityReportMode });

// ══════════════════════════════════════════════════════════════
// 9. METRIC — Number with label
// ══════════════════════════════════════════════════════════════
class ActivityMetric extends Component {
    static template = xml`
        <span class="ac-metric">
            <i class="fa" t-att-class="metricIcon"/>
            <t t-esc="metricValue"/>
        </span>
    `;
    static props = { name: String, record: Object, readonly: Boolean };

    get raw() { return this.props.record.data[this.props.name]; }
    get metricValue() {
        const v = fmt(parseInt(this.raw, 10) || 0);
        if (this.props.name === "requested_days") return v + " " + _t("days");
        return v;
    }
    get metricIcon() {
        if (this.props.name === "requested_days") return "fa-calendar";
        if (this.props.name === "selected_store_count") return "fa-building-o";
        return "fa-hashtag";
    }
}

registry.category("fields").add("list.activity_metric", { component: ActivityMetric });

// ══════════════════════════════════════════════════════════════
// 10. BOOLEAN — Enabled/Disabled badge
// ══════════════════════════════════════════════════════════════
class ActivityBoolean extends Component {
    static template = xml`
        <span class="ac-boolean" t-att-class="boolCls">
            <i class="fa" t-att-class="boolIcon"/>
            <t t-esc="boolLabel"/>
        </span>
    `;
    static props = { name: String, record: Object, readonly: Boolean };

    get val() { return Boolean(this.props.record.data[this.props.name]); }
    get boolCls() { return this.val ? "ac-boolean--on" : "ac-boolean--off"; }
    get boolIcon() { return this.val ? "fa-check-circle" : "fa-circle-o"; }
    get boolLabel() { return this.val ? _t("On") : _t("Off"); }
}

registry.category("fields").add("list.activity_boolean", { component: ActivityBoolean });

// ══════════════════════════════════════════════════════════════
// 11. UNSUPPORTED — Flag badge
// ══════════════════════════════════════════════════════════════
class ActivityUnsupported extends Component {
    static template = xml`
        <span class="ac-unsup" t-att-class="unsupCls">
            <i class="fa" t-att-class="unsupIcon"/>
        </span>
    `;
    static props = { name: String, record: Object, readonly: Boolean };

    get val() { return Boolean(this.props.record.data[this.props.name]); }
    get unsupCls() { return this.val ? "ac-unsup--yes" : "ac-unsup--no"; }
    get unsupIcon() { return this.val ? "fa-exclamation-triangle" : "fa-check"; }
}

registry.category("fields").add("list.activity_unsupported", { component: ActivityUnsupported });
