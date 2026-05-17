odoo.define('abdin_loyalty_redesign.ProgramTypeSelector', function (require) {
    'use strict';

    var AbstractField = require('web.AbstractField');
    var fieldRegistry = require('web.field_registry');

    var ProgramTypeSelector = AbstractField.extend({
        supportedFieldTypes: ['selection'],

        programTypeData: {
            'coupons': {
                icon: 'fa-ticket',
                title: 'Coupons',
                desc: 'Generate unique coupon codes for customers',
                color: '#6366f1',
                bg: '#eef2ff',
            },
            'promo_code': {
                icon: 'fa-percent',
                title: 'Promo Code',
                desc: 'Shareable discount code',
                color: '#f59e0b',
                bg: '#fffbeb',
            },
            'promotion': {
                icon: 'fa-star',
                title: 'Promotion',
                desc: 'Automatic promotion on cart conditions',
                color: '#8b5cf6',
                bg: '#f5f3ff',
            },
            'buy_x_get_y': {
                icon: 'fa-gift',
                title: 'Buy X Get Y',
                desc: 'Free product on qualifying purchase',
                color: '#10b981',
                bg: '#ecfdf5',
            },
            'loyalty': {
                icon: 'fa-id-card',
                title: 'Loyalty Program',
                desc: 'Points-based loyalty system',
                color: '#3b82f6',
                bg: '#eff6ff',
            },
            'gift_card': {
                icon: 'fa-credit-card',
                title: 'Gift Card',
                desc: 'Prepaid gift card for store credit',
                color: '#ec4899',
                bg: '#fdf2f8',
            },
            'ewallet': {
                icon: 'fa-wallet',
                title: 'eWallet',
                desc: 'Digital wallet for balance management',
                color: '#14b8a6',
                bg: '#f0fdfa',
            },
        },

        _getAvailableTypes: function () {
            var self = this;
            var allTypes = this.field.selection || [];
            var rawOpts = this.field.options || {};
            var opts = typeof rawOpts === 'string' ? JSON.parse(rawOpts || '{}') : rawOpts;
            var blacklisted = opts.blacklisted_values || [];
            var whitelisted = opts.whitelisted_values || [];

            var filtered = _.filter(allTypes, function (t) {
                var val = t[0];
                if (!val) return false;
                if (blacklisted.length > 0) return !_.contains(blacklisted, val);
                if (whitelisted.length > 0) return _.contains(whitelisted, val);
                return true;
            });

            return _.map(filtered, function (t) {
                var val = t[0];
                var label = t[1];
                var data = self.programTypeData[val] || {
                    icon: 'fa-tag',
                    title: label,
                    desc: '',
                    color: '#64748b',
                    bg: '#f1f5f9',
                };
                return _.extend({}, data, {value: val, label: label});
            });
        },

        _renderEdit: function () {
            var self = this;
            var value = this.value;
            var types = this._getAvailableTypes();

            var html = '<div class="abdin-pt-selector">';
            _.each(types, function (t) {
                var isActive = t.value === value;
                var activeClass = isActive ? ' abdin-pt-card--active' : '';
                html += '<div class="abdin-pt-card' + activeClass + '" data-value="' + _.str.escapeHTML(t.value) + '">';
                html += '<div class="abdin-pt-card-accent" style="background:' + t.color + '"></div>';
                html += '<div class="abdin-pt-card-inner">';
                html += '<div class="abdin-pt-card-icon" style="background:' + t.bg + ';color:' + t.color + '"><i class="fa ' + t.icon + '"></i></div>';
                html += '<div class="abdin-pt-card-info">';
                html += '<div class="abdin-pt-card-title">' + _.str.escapeHTML(t.title) + '</div>';
                html += '<div class="abdin-pt-card-desc">' + _.str.escapeHTML(t.desc) + '</div>';
                html += '</div>';
                html += '<div class="abdin-pt-card-check"><i class="fa fa-check-circle"></i></div>';
                html += '</div></div>';
            });
            html += '</div>';

            this.$el.addClass('abdin-pt-container').html(html);

            this.$el.on('click', '.abdin-pt-card', function () {
                var val = $(this).data('value');
                if (val && val !== self.value) {
                    self._setValue(val);
                }
            });
        },

        _renderReadonly: function () {
            var val = this.value;
            if (!val) {
                this.$el.empty();
                return;
            }
            var t = this.programTypeData[val];
            if (t) {
                var html = '<div class="abdin-pt-selector abdin-pt-selector--readonly">';
                html += '<div class="abdin-pt-card abdin-pt-card--readonly">';
                html += '<div class="abdin-pt-card-accent" style="background:' + t.color + '"></div>';
                html += '<div class="abdin-pt-card-inner">';
                html += '<div class="abdin-pt-card-icon" style="background:' + t.bg + ';color:' + t.color + '"><i class="fa ' + t.icon + '"></i></div>';
                html += '<div class="abdin-pt-card-info">';
                html += '<div class="abdin-pt-card-title">' + _.str.escapeHTML(t.title) + '</div>';
                html += '<div class="abdin-pt-card-desc">' + _.str.escapeHTML(t.desc) + '</div>';
                html += '</div></div></div></div>';
                this.$el.addClass('abdin-pt-container').html(html);
            }
        },
    });

    fieldRegistry.add('abdin_program_type', ProgramTypeSelector);
    return ProgramTypeSelector;
});
