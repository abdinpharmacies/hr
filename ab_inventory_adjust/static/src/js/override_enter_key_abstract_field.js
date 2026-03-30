odoo.define('ab_inventory_adjust.override_enter', function (require) {
    "use strict";

    const AbstractField = require('web.AbstractField');
    const Helper = require('ab_inventory_adjust.helper_functions');

    AbstractField.include({
        _onKeydown: function (ev) {
            switch (ev.which) {
                case $.ui.keyCode.TAB:
                    var event = this.trigger_up('navigation_move', {
                        direction: ev.shiftKey ? 'previous' : 'next',
                    });
                    if (event.is_stopped()) {
                        ev.preventDefault();
                        ev.stopPropagation();
                    }
                    break;
                case $.ui.keyCode.ENTER:
                    // Custom logic: Check if the current model is 'ab_inventory_adjust_header'
                    if (Helper.isActiveElementName('product_id')) {
                        // ev.preventDefault();
                        // Skip stopPropagation if condition is met
                    } else {
                        // We preventDefault the ENTER key because of two coexisting behaviours:
                        // - In HTML5, pressing ENTER on a <button> triggers two events: a 'keydown' AND a 'click'
                        // - When creating and opening a dialog, the focus is automatically given to the primary button
                        // The end result caused some issues where a modal opened by an ENTER keypress (e.g. saving
                        // changes in multiple edition) confirmed the modal without any intentionnal user input.
                        ev.stopPropagation();
                        this.trigger_up('navigation_move', {direction: 'next_line'});
                    }
                    break;
                case $.ui.keyCode.ESCAPE:
                    this.trigger_up('navigation_move', {direction: 'cancel', originalEvent: ev});
                    break;
                case $.ui.keyCode.UP:
                    ev.stopPropagation();
                    this.trigger_up('navigation_move', {direction: 'up'});
                    break;
                case $.ui.keyCode.RIGHT:
                    ev.stopPropagation();
                    this.trigger_up('navigation_move', {direction: 'right'});
                    break;
                case $.ui.keyCode.DOWN:
                    ev.stopPropagation();
                    this.trigger_up('navigation_move', {direction: 'down'});
                    break;
                case $.ui.keyCode.LEFT:
                    ev.stopPropagation();
                    this.trigger_up('navigation_move', {direction: 'left'});
                    break;
            }
        },


    });

});
