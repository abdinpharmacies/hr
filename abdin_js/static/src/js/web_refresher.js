/** @odoo-module **/
import LegacyControlPanel from "web.ControlPanel";

const {Component} = owl;

export class Refresher extends Component {
    _doRefresh() {
        const limit = this.props.limit || 80
        const currentMinimum = this.props.currentMinimum || 1
        return this.trigger("pager-changed", {currentMinimum, limit});
    }
}

Refresher.template = "abdin_js.RefresherButton";

LegacyControlPanel.components = Object.assign({}, LegacyControlPanel.components, {
    Refresher,
});
