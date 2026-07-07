/** @odoo-module **/
import { Component } from "@odoo/owl";

export class Timeline extends Component {
    static template = "core_ui.timeline";
    static props = {
        stages: { type: Array, optional: true },
        detail: { type: Object, optional: true },
    };
    static defaultProps = {
        stages: [],
        detail: null,
    };

    get detailStatusClass() {
        if (!this.props.detail) return '';
        return this.props.detail.status ? `is-${this.props.detail.status}` : '';
    }

    stageStatusClass(stage) {
        return stage.status ? `is-${stage.status}` : '';
    }

    lineStatusClass(stage) {
        if (!stage.status) return 'pending';
        if (stage.status === 'completed') return 'completed';
        if (stage.status === 'current') return 'current';
        return 'pending';
    }

    stageLabelClass(stage) {
        if (!stage.status) return '';
        return stage.status;
    }

    dotContent(stage) {
        if (stage.icon) return stage.icon;
        if (stage.status === 'completed') return '✓';
        if (stage.status === 'current') return '●';
        if (stage.status === 'overdue') return '✈';
        if (stage.status === 'rejection') return '✗';
        if (stage.status === 'delay') return '⚠';
        if (stage.status === 'other') return '◆';
        return '○';
    }

    isLast(index) {
        return index === this.props.stages.length - 1;
    }

    get hasDetailCard() {
        return this.props.detail && this.props.detail.title;
    }
}
