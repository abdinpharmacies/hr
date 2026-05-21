/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { ListController } from "@web/views/list/list_controller";
import { patch } from "@web/core/utils/patch";

patch(ListController.prototype, {
    get abRequestCreateButtonLabel() {
        if (this.props.resModel === "ab_request") {
            return _t("New Request or Complaint");
        }
        return _t("New");
    },
});
