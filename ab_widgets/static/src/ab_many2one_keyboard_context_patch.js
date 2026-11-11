/** @odoo-module **/

import {patch} from "@web/core/utils/patch";
import {ABMany2one} from "@ab_widgets/ab_many2one";

patch(ABMany2one.prototype, {
    get keyboardMapContext() {
        const context = this.props.context || {};
        return {
            ...context,
            ab_widget_keyboard_map_search: true,
        };
    },
});
