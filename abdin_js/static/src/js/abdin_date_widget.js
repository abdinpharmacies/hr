odoo.define("abdin_cust.FormView", function (require) {
    "use strict";
    var time = require("web.time");


    // @todo لما نحط تاريخ غلط في بيختار تاريخ عشوائي
    var DateWidget = require("web.datepicker").DateWidget;
    var field_utils = require("web.field_utils");
    DateWidget.include({
        // اللي غيرته هنا كالآتي
        // استدعيت الانيت القديم
        // يفحص dtp_format اللي في الاوبشنز في ملف xml
        // اظهر ال 3 زراير بتوع تاريخ اليوم،ومسح التاريخ،واغلاق النافذة
        init: function (parent, options) {
            this._super.apply(this, arguments);
            this.name = parent.name;
            if (this.options.dtp_format) {
                this.options.format = options.dtp_format;
            }
            let btns = this.options.buttons;
            btns.showToday = true;
            btns.showClear = true;
            btns.showClose = true;
        },
        // اللي غيرته هنا كالآتي
        // اعمل تست على التاريخ المدخل
        // لو لقيته بصيغة m-yy او m-yyyy
        // حط قبله 01- علشان يبقى تاريخ كامل
        // لو لقيت فيه dtp_format في الاوبشنز xml
        // حوله لتاريخ iso
        // لاحظ ان الريجيكس بيشترط النص بالكامل مش جزء منه
        isValid: function () {
            var entry_regex = /^\d{1,2}[-\\/\s]\d{2,4}$/;
            this.valid_date = this.$input.val();
            if (this.valid_date === "") {
                return true;
            } else {
                try {
                    if (entry_regex.test(this.valid_date)) {
                        this.valid_date = "01-" + this.valid_date;
                    } else if (this.options.dtp_format) {
                        this.valid_date = moment(
                            this.valid_date,
                            this.options.dtp_format
                        ).format("YYYY-MM-DD");
                    }

                    this._parseClient(this.valid_date);
                    return true;
                } catch (e) {
                    return false;
                }
            }
        },
        // اللي غيرته هنا كالآتي
        // خد القيمة this.valid_date من دالة isValid وحولها لاوبجكت الاودو للتاريخ
        _setValueFromUi: function () {
            var value = this.valid_date || false;
            this.setValue(this._parseClient(value));
        },
        // اللي غيرته هنا كالآتي
        // if this.options.dtp_format
        // يعني لو حاطط dtp_format في الاوبشنز xml
        //  غير الفورمات وخليه YYYY-MM-DD
        // سواء فاليد او غير فاليد
        changeDatetime: function () {
            let formattedOldValue;
            let formattedNewValue;
            let formattedValue;

            if (this.__libInput > 0) {
                if (this.options.warn_future) {
                    this._warnFuture(this.getValue());
                }
                this.trigger("datetime_changed");
                return;
            }
            var oldValue = this.getValue();
            if (this.isValid()) {
                this._setValueFromUi();
                var newValue = this.getValue();
                var hasChanged = !oldValue !== !newValue;
                if (oldValue && newValue) {
                    if (this.options.dtp_format) {
                        formattedOldValue = oldValue.format("YYYY-MM-DD");
                        formattedNewValue = newValue.format("YYYY-MM-DD");
                    } else {
                        formattedOldValue = oldValue.format(
                            time.getLangDatetimeFormat()
                        );
                        formattedNewValue = newValue.format(
                            time.getLangDatetimeFormat()
                        );
                    }
                    if (formattedNewValue !== formattedOldValue) {
                        hasChanged = true;
                    }
                }
                if (hasChanged) {
                    if (this.options.warn_future) {
                        this._warnFuture(newValue);
                    }
                    this.trigger("datetime_changed");
                }
            } else {
                if (this.options.dtp_format) {
                    formattedValue = oldValue ? oldValue.format("YYYY-MM-DD") : null;
                } else {
                    formattedValue = oldValue ? this._formatClient(oldValue) : null;
                }
                this.$input.val(formattedValue);
            }
        },
        start: function () {
            this._super.apply(this, arguments);
            // if (this.options.dtp_format) {
            //   console.log("raedonly", this.$el.find(".o_form_readonly"));
            // }
        },
    });

    ////////////////////////////////////////////////////////////////////////////

    var RibbonWidget = require("web.ribbon");

    RibbonWidget.include({
        action_taken: "",
        init: function (parent, data, options) {
            this._super.apply(this, arguments);
            if (
                data.model === "abdin_cust.bills_actions" &&
                options?.attrs?.class === "status" &&
                data?.data?.action_status
            ) {
                this.action_taken = data?.data?.action_status;
            }
        },
        start: function () {
            this._super.apply(this, arguments);
            if (this.action_taken) {

                console.log(this)
                let action_class;
                switch (this.action_taken) {
                    case "for_review":
                        action_class = "bg-success";
                        break;
                    case "for_collect":
                        action_class = "bg-dark";
                        break;
                    case "closed":
                        action_class = "bg-danger";
                        break;
                    case "for_review":
                        action_class = "bg-success";
                        break;
                    default:
                        action_class = "bg-info";
                }
                this.$el.html(
                    `<span class="${action_class}">${this.action_taken}</span>`
                );
            }
        },
    });
    ////////////////////////////////////////////////////////////////////////////
});

function props(obj) {
    var p = [];
    for (; obj != null; obj = Object.getPrototypeOf(obj)) {
        var op = Object.getOwnPropertyNames(obj);
        for (var i = 0; i < op.length; i++)
            if (p.indexOf(op[i]) == -1) p.push(`${op[i]} ===== ${obj[op[i]]}`);
    }
    return p;
}
