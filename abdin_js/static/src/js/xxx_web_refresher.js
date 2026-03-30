odoo.define("abdin_js.refresher", function(require) {
    "use strict";
    var pager = require("web.Pager");
    pager.include({
        start: function() {
            var self = this;
            var res = self._super();

            var $button = $("<span>", {
                class: "fa fa-refresh fa-6x btn btn-icon o_pager_refresh text-success",
                css: {"margin-right": "8px;"},
                "aria-label": "Refresh",
            });
            $button.on("click", function() {
                self._changeSelection(0);
            });

            self.$el.prepend($button);
            return res;
        },
    });
});
