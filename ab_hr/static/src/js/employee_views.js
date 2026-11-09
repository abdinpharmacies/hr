/** @odoo-module **/
import { onMounted, onWillUnmount, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { formView } from "@web/views/form/form_view";
import { FormRenderer } from "@web/views/form/form_renderer";
import { kanbanView } from "@web/views/kanban/kanban_view";

class EmployeeFormRenderer extends FormRenderer {
    setup() {
        super.setup();
        const root = useRef("compiled_view_root");
        const orm = useService("orm");
        const store = useService("mail.store");
        const onClick = async (event) => {
            if (!event.target.closest(".o_employee_chat_btn")) {
                return;
            }
            event.preventDefault();
            event.stopPropagation();
            const user = this.props.record.data.user_id;
            if (user) {
                const [record] = await orm.read("res.users", [user.id], ["partner_id"]);
                if (record.partner_id) {
                    await store.joinChat(record.partner_id[0], true);
                }
            }
        };
        onMounted(() => root.el.addEventListener("click", onClick));
        onWillUnmount(() => root.el?.removeEventListener("click", onClick));
    }
}

registry.category("views").add("hr_employee_form", { ...formView, Renderer: EmployeeFormRenderer });
registry.category("views").add("hr_employee_kanban", { ...kanbanView });
