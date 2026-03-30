odoo.define("abdin_js.urgent_save_firefox_fix", function (require) {
  "use strict";
  let FormController = require("web.FormController");
  FormController.include({
    /**
     * Save the record when we are about to leave Odoo.
     *
     * @override
     */
    sleep: function (ms) {
      return new Promise((resolve) => setTimeout(resolve, ms));
    },
    _onBeforeUnload: async function () {
      this._urgentSave(this.handle);

      await this.sleep(1);
      return true;
    },
  });
});
