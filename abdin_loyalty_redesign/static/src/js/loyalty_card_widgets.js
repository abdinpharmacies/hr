odoo.define('abdin_loyalty_redesign.CardWidgets', function (require) {
    'use strict';

    var AbstractField = require('web.AbstractField');
    var fieldRegistry = require('web.field_registry');

    /* -----------------------------------------------------------------
     * Wallet Code — Monospace secure token + copy-to-clipboard
     * ----------------------------------------------------------------*/
    var WalletCode = AbstractField.extend({
        supportedFieldTypes: ['char'],
        className: 'abdin_widget_code',

        events: {
            'click .abdin_copy_btn': '_onCopy',
        },

        _renderReadonly: function () {
            var val = _.escape(this.value || '');
            this.$el.html(
                '<div class="abdin_widget_code_wrap">' +
                    '<span class="abdin_widget_code_value">' + val + '</span>' +
                    '<button class="abdin_copy_btn" title="Copy coupon code">' +
                        '<i class="fa fa-copy"></i>' +
                        '<span class="abdin_copy_text">Copy</span>' +
                    '</button>' +
                '</div>'
            );
        },

        _onCopy: async function (ev) {
            ev.preventDefault();
            var btn = this.$(ev.currentTarget);
            try {
                await navigator.clipboard.writeText(this.value || '');
                btn.addClass('abdin_copied');
                btn.find('i').removeClass('fa-copy').addClass('fa-check');
                btn.find('.abdin_copy_text').text('Copied!');
                setTimeout(function () {
                    btn.removeClass('abdin_copied');
                    btn.find('i').removeClass('fa-check').addClass('fa-copy');
                    btn.find('.abdin_copy_text').text('Copy');
                }, 2000);
            } catch (e) {
                /* clipboard not available */
            }
        },

        _renderEdit: function () {
            this._renderReadonly();
        },
    });


    /* -----------------------------------------------------------------
     * Wallet Expiry — Date display + remaining-days badge
     * ----------------------------------------------------------------*/
    var WalletExpiry = AbstractField.extend({
        supportedFieldTypes: ['date', 'datetime'],
        className: 'abdin_widget_expiry',

        _renderReadonly: function () {
            var val = this.value;
            var status = 'active';
            var daysText = '';

            if (val) {
                var expDate = moment(val, moment.ISO_8601);
                var now = moment();
                var daysLeft = expDate.diff(now, 'days');
                var formatted = expDate.format('MMM D, YYYY');

                if (daysLeft < 0) {
                    status = 'expired';
                    daysText = 'Expired ' + Math.abs(daysLeft) + 'd ago';
                } else if (daysLeft === 0) {
                    status = 'expiring_soon';
                    daysText = 'Expires today';
                } else if (daysLeft <= 7) {
                    status = 'expiring_soon';
                    daysText = daysLeft + ' day' + (daysLeft > 1 ? 's' : '') + ' left';
                } else {
                    status = 'active';
                    daysText = daysLeft + ' days remaining';
                }

                this.$el.html(
                    '<div class="abdin_widget_expiry_wrap">' +
                        '<span class="abdin_widget_expiry_date">' + _.escape(formatted) + '</span>' +
                        '<span class="abdin_status_pill abdin_status_pill--' + status + '">' +
                            _.escape(daysText) +
                        '</span>' +
                    '</div>'
                );
            } else {
                this.$el.html(
                    '<div class="abdin_widget_expiry_wrap">' +
                        '<span class="abdin_widget_expiry_date abdin_no_expiry_text">No expiration date</span>' +
                        '<span class="abdin_status_pill abdin_status_pill--active">Unlimited</span>' +
                    '</div>'
                );
            }
        },

        _renderEdit: function () {
            this._renderReadonly();
        },
    });


    /* -----------------------------------------------------------------
     * Wallet Balance — Animated KPI counter
     * ----------------------------------------------------------------*/
    var WalletBalance = AbstractField.extend({
        supportedFieldTypes: ['char', 'float', 'integer'],
        className: 'abdin_widget_balance',

        _renderReadonly: function () {
            var raw = this.value || '0';
            var match = raw.match(/[\d,]+\.?\d*/);
            var numericVal = match ? parseFloat(match[0].replace(/,/g, '')) : 0;
            var formatted = Math.floor(numericVal).toLocaleString();

            this.$el.html(
                '<div class="abdin_widget_balance_wrap">' +
                    '<span class="abdin_widget_balance_number" data-target="' + numericVal + '">0</span>' +
                    '<span class="abdin_widget_balance_unit">pts</span>' +
                '</div>'
            );

            this._animateCounter(numericVal);
        },

        _animateCounter: function (target) {
            var $el = this.$('.abdin_widget_balance_number');
            if (!$el.length) return;

            var duration = 800;
            var startTime = performance.now();

            var step = function (timestamp) {
                var progress = Math.min((timestamp - startTime) / duration, 1);
                var eased = 1 - Math.pow(1 - progress, 3);
                var current = Math.floor(eased * target);
                $el.text(current.toLocaleString());
                if (progress < 1) {
                    requestAnimationFrame(step);
                } else {
                    $el.text(Math.floor(target).toLocaleString());
                }
            };

            requestAnimationFrame(step);
        },

        _renderEdit: function () {
            this._renderReadonly();
        },
    });


    fieldRegistry.add('abdin_wallet_code', WalletCode);
    fieldRegistry.add('abdin_wallet_expiry', WalletExpiry);
    fieldRegistry.add('abdin_wallet_balance', WalletBalance);

    return { WalletCode: WalletCode, WalletExpiry: WalletExpiry, WalletBalance: WalletBalance };
});
