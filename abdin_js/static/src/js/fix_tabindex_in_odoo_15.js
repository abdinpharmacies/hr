odoo.define('abdin_js.fix_tab_index', function (require) {
    "use strict";

    var FormRenderer = require('web.FormRenderer');
    var core = require('web.core');


    FormRenderer.include({
        setLocalState: function (state) {
            for (const notebook of this.el.querySelectorAll(':scope div.o_notebook')) {
                if (notebook.closest(".o_field_widget")) {
                    continue;
                }
                const name = notebook.dataset.name;
                if (name in state) {
                    const navs = notebook.querySelectorAll(':scope .o_notebook_headers .nav-item');
                    const pages = notebook.querySelectorAll(':scope > .tab-content > .tab-pane');
                    // We can't base the amount on the 'navs' length since some overrides
                    // are adding pageless nav items.
                    const validTabsAmount = pages.length;
                    if (!validTabsAmount) {
                        continue; // No page defined on the notebook.
                    }
                    let activeIndex = state[name];
                    if (activeIndex in navs && navs[activeIndex].classList.contains('o_invisible_modifier')) {
                        activeIndex = [...navs].findIndex(
                            nav => !nav.classList.contains('o_invisible_modifier')
                        );
                    }
                    if (activeIndex <= 0) {
                        continue; // No visible tab OR first tab = active tab (no change to make).
                    }
                    for (let i = 0; i < validTabsAmount; i++) {
                        navs[i].querySelector('.nav-link').classList.toggle('active', activeIndex === i);
                        pages[i].classList.toggle('active', activeIndex === i);
                    }
                    core.bus.trigger('DOM_updated');
                }
            }
            const sheetBg = this.el.querySelector('.o_form_sheet_bg');
            if (sheetBg) {
                sheetBg.scrollTop = state.scrollValue;
            }
        },

    });
})
