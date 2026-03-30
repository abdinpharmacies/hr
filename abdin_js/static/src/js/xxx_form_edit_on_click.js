odoo.define("form_edit_on_click.form_edit", function (require) {
    "use strict";
    var core = require("web.core");
    var _t = core._t;
    var dialogs = require("web.view_dialogs");
    var FormController = require("web.FormController");
    FormController.include({
        _onOpenOne2ManyRecord: async function (ev) {
            ev.stopPropagation();
            var data = ev.data;
            var record;
            if (data.id) {
                record = this.model.get(data.id, {raw: true});
            }

            // Sync with the mutex to wait for potential onchanges
            await this.model.mutex.getUnlockedDef();
            var context = data.context
            var readonly = !(context?.allow_edit === '1') || !ev.target.activeActions?.create;
            new dialogs.FormViewDialog(this, {
                context: data.context,
                domain: data.domain,
                fields_view: data.fields_view,
                model: this.model,
                on_saved: data.on_saved,
                on_remove: data.on_remove,
                parentID: data.parentID,
                readonly: readonly,
                deletable: record ? data.deletable : false,
                recordID: record && record.id,
                res_id: record && record.res_id,
                res_model: data.field.relation,
                shouldSaveLocally: false,
                title:
                    (record ? _t("Open: ") : _t("Create ")) +
                    (ev.target.string || data.field.string),
            }).open();
        },
    });

    var FieldMany2Many = require("web.relational_fields").FieldMany2Many;
    FieldMany2Many.include({
        _onOpenRecord: function (ev) {
            ev.data.readonly = false;
            var context = this.record.getContext(this.recordParams);
            var readonly = !(context?.allow_edit === '1') || !this.activeActions?.create;
            var self = this;
            _.extend(ev.data, {
                context: context,
                domain: this.record.getDomain(this.recordParams),
                fields_view: this.attrs.views && this.attrs.views.form,
                on_saved: function () {
                    self
                        ._setValue({operation: "TRIGGER_ONCHANGE"}, {forceChange: true})
                        .then(function () {
                            self.trigger_up("reload", {db_id: ev.data.id});
                        });
                },
                on_remove: function () {
                    self._setValue({operation: "FORGET", ids: [ev.data.id]});
                },
                readonly: readonly,
                deletable: this.activeActions.delete && this.view.arch.tag !== "tree",
                string: this.string,
            });
        },

    });
});


