from odoo.tests import HttpCase, tagged, no_retry


@tagged('post_install', '-at_install')
class TestWebsiteUI(HttpCase):
    @no_retry
    def test_website_assets_and_arabic_labels(self):
        self.env['res.lang']._activate_lang('ar_001')
        self.env.ref('base.user_admin').lang = 'ar_001'
        self.browser_js(
            '/odoo?debug=assets',
            '''
            (async () => {
                const env = odoo.__WOWL_DEBUG__.root.env;
                await env.services.action.doAction('ab_crm_sales_workspace.action_workspace');
                if (!document.querySelector('.ab_crm_sales_workspace')) throw new Error('Workspace template failed');
                await env.services.action.doAction('ab_crm_sales_workspace.action_pos');
                if (!document.querySelector('.ab_pos_hr_overlay')) throw new Error('Native POS login missing');
                const actions = odoo.loader.modules.get('@web/core/registry').registry.category('actions');
                const Native = actions.get('ab_sales.pos');
                const Adapter = actions.get('ab_crm_sales_workspace.pos');
                const {CrmPosAction} = odoo.loader.modules.get('@ab_crm_sales_workspace/pos_handoff');
                if (Adapter !== CrmPosAction || Adapter.template !== Native.template) throw new Error('General POS action changed');
                if (document.querySelector('.ab_website_pos_quotation')) throw new Error('Website quotation remains in POS');
                const translate = odoo.loader.modules.get('@web/core/l10n/translation')._t;
                if (translate('View invoice') !== 'عرض الفاتورة' || translate('Hide invoice') !== 'اخفاء الفاتورة')
                    throw new Error('Invoice toggle Arabic translation missing');
                if (translate('Order Reference') !== 'مرجع الطلب') throw new Error('Order reference Arabic translation missing');
                if (translate('Payment method:') !== 'طريقة الدفع:')
                    throw new Error('Payment method Arabic translation missing');
                const {Component, useState} = odoo.loader.modules.get('@odoo/owl');
                const {mountComponent} = odoo.loader.modules.get('@web/env');
                class ArabicInvoice extends Component {
                    static template = 'ab_crm_website.OrderMessage';
                    static props = [];
                    setup() {
                        this.state = useState({detail: {id: 1, owned: true}});
                        this.message = {website_order: {reference: 'WEB-AR', public_reference: 'NO-151126-E4CRGK',
                            customer: {name: 'Customer', phone: '01012345678', address: 'Cairo'},
                            lines: [{name: 'Long product name repeated to check narrow layouts', quantity: 2,
                                unit_name: 'علبة', unit: 'source-box', price: 20, discount: 0, total: 40}],
                            display_delivery_address: 'Sohag | 12 Main Street, building 3, floor 2',
                            total: 40, currency: 'EGP', payment_method_label: 'الدفع عند الاستلام'}};
                    }
                }
                const host = document.createElement('section');
                host.className = 'ab_crm_sales_workspace';
                host.style.width = '320px';
                const target = document.createElement('article');
                target.className = 'ab_message in ab_website_message';
                host.append(target); document.body.append(host);
                const app = await mountComponent(ArabicInvoice, target, {env});
                try {
                    if (target.querySelector('button')) throw new Error('Website invoice must be display only');
                    if (target.querySelectorAll('thead th').length !== 5 || target.querySelectorAll('tbody tr td').length !== 5 ||
                        target.querySelector('tbody tr td:nth-child(3)').textContent !== '20' || target.textContent.includes('علبة'))
                        throw new Error('Invoice must show five columns without the unit');
                    const address = target.querySelector('.ab_website_delivery_address');
                    const reference = target.querySelector('.ab_website_order_reference');
                    if (!address.textContent.includes(' | ') || getComputedStyle(address).whiteSpace !== 'nowrap' ||
                        address.nextElementSibling.nextElementSibling !== reference ||
                        reference.textContent !== 'NO-151126-E4CRGK')
                        throw new Error('Delivery address or order reference layout failed');
                    const invoice = target.querySelector('details');
                    const show = target.querySelector('.ab_invoice_show');
                    const hide = target.querySelector('.ab_invoice_hide');
                    if (show.textContent !== 'عرض الفاتورة' || getComputedStyle(hide).display !== 'none')
                        throw new Error('Arabic closed invoice label failed: ' + JSON.stringify([show.textContent, getComputedStyle(hide).display]));
                    invoice.querySelector('summary').click();
                    await new Promise(resolve => setTimeout(resolve));
                    if (hide.textContent !== 'اخفاء الفاتورة' || getComputedStyle(show).display !== 'none')
                        throw new Error('Arabic open invoice label failed');
                    if (!target.textContent.includes('طريقة الدفع:') || !target.textContent.includes('الدفع عند الاستلام'))
                        throw new Error('Arabic payment display failed');
                    if (host.scrollWidth > host.clientWidth + 1) throw new Error('Invoice must not widen the chat layout');
                } finally { app.destroy(); host.remove(); }

                console.log('test successful');
            })().catch(error => console.error(error));
        ''',
            ready="!!odoo.__WOWL_DEBUG__?.root",
            login='admin',
            timeout=90,
        )


    @no_retry
    def test_incoming_invoice_is_display_only(self):
        self.browser_js(
            '/odoo?debug=assets',
            '''
            (async () => {
                const {Component, useState} = odoo.loader.modules.get('@odoo/owl');
                const {mountComponent} = odoo.loader.modules.get('@web/env');
                const env = odoo.__WOWL_DEBUG__.root.env;
                const calls = [];
                const actions = [];
                class OrderMessage extends Component {
                    static template = 'ab_crm_website.OrderMessage';
                    static props = [];
                    setup() {
                        this.state = useState({token: 'staff-session', busy: false, navigating: false,
                            detail: {id: 12, owned: true, contact: {id: 34, phones: [{id: 56}]}}});
                        this.message = {conversation_id: 13, website_order: {reference: 'WEB-MESSAGE', public_reference: 'NO-151126-ABC123',
                            customer: {name: 'Customer', phone: '01012345678', address: 'Cairo'},
                            lines: [{name: 'Item', quantity: 2, unit: 'box', price: 20, total: 40}],
                            display_delivery_address: 'Cairo | 12 Main Street',
                            total: 40, currency: 'EGP', display_notes: '', payment_method_label: 'Cash on delivery', payments: [], fulfillment: {state: 'sale'}}};
                        this.select = async id => {this.state.detail.id = id;};
                        this.stopRecording = () => {};
                        this.rememberDraft = () => {};
                        this.run = callback => callback();
                        this.call = async (...args) => {calls.push(args); return 78;};
                        this.action = {doAction: async (...args) => actions.push(args)};
                    }
                }
                const target = document.createElement('article');
                target.className = 'ab_message in ab_website_message';
                const host = document.createElement('section');
                host.className = 'ab_crm_sales_workspace';
                host.append(target); document.body.append(host);
                const app = await mountComponent(OrderMessage, target, {env});
                try {
                    const button = target.querySelector('.ab_website_create_order');
                    if (button || !target.textContent.includes('WEB-MESSAGE') ||
                        !target.textContent.includes('Item')) throw new Error('Incoming order card missing');
                    if (target.querySelector('button')) throw new Error('Website invoice must be display only');
                    const address = target.querySelector('.ab_website_delivery_address');
                    const reference = target.querySelector('.ab_website_order_reference');
                    if (!address.textContent.includes(' | ') || getComputedStyle(address).whiteSpace !== 'nowrap' ||
                        address.nextElementSibling.nextElementSibling !== reference ||
                        reference.textContent !== 'NO-151126-ABC123')
                        throw new Error('Delivery address or order reference layout failed');
                    const invoice = target.querySelector('details');
                    if (invoice.open || !target.querySelector('.ab_website_order_title').textContent.includes('Website Order:'))
                        throw new Error('Invoice should start closed with the centered order heading');
                    invoice.querySelector('summary').click();
                    await new Promise(resolve => setTimeout(resolve));
                    if (!invoice.open || target.textContent.includes('pending') || !target.textContent.includes('Cash on delivery'))
                        throw new Error('Invoice toggle or payment method display failed');
                    const headers = [...target.querySelectorAll('thead th')].map(cell => cell.textContent);
                    if (JSON.stringify(headers) !== JSON.stringify(['Product', 'Quantity', 'Price', 'Discount', 'Total']) ||
                        target.querySelectorAll('tbody tr td').length !== 5 || target.textContent.includes('box'))
                        throw new Error('Invoice product columns are incorrect');
                    if (calls.length || actions.length) throw new Error('Invoice triggered POS preparation');
                } finally { app.destroy(); host.remove(); }
                console.log('test successful');
            })().catch(error => console.error(error));
            ''',
            ready="!!odoo.__WOWL_DEBUG__?.root",
            login='admin',
            timeout=90,
        )

    @no_retry
    def test_general_contact_navigation_and_manual_product_entry(self):
        self.browser_js(
            '/odoo?debug=assets',
            """
            (async () => {
                const {SalesWorkspace} = odoo.loader.modules.get('@ab_crm_sales_workspace/workspace');
                const {CrmPosAction} = odoo.loader.modules.get('@ab_crm_sales_workspace/pos_handoff');
                const registry = odoo.loader.modules.get('@web/core/registry').registry;
                if (registry.category('actions').get('ab_crm_sales_workspace.workspace') !== SalesWorkspace)
                    throw new Error('General workspace action changed');
                const calls = [], actions = [];
                const workspace = {
                    state: {token: 'staff', detail: {id: 12, contact: {id: 34, phones: [{id: 56}]}}},
                    run: callback => callback(), stopRecording() {}, rememberDraft() {},
                    call: async (...args) => {calls.push(args); return 78;},
                    action: {doAction: async (...args) => actions.push(args)},
                };
                await SalesWorkspace.prototype.createOrder.call(workspace);
                if (calls[0][1] !== 'pos_handoff_start' || calls[0][3].contact_id !== 34 ||
                    calls[0][3].conversation_id !== 12 || actions[0][1].additionalContext.crm_handoff_id !== 78)
                    throw new Error('General contact navigation failed');
                const bill = {header: {}, lines: []};
                const pos = {
                    currentBill: bill, billEditable: () => true,
                    _extractUomInfo: () => ({uomId: 3, uomName: 'Box', uomFactor: 1}),
                    loadLineDetails() {}, _recomputeBill() {}, schedulePromoRefresh() {},
                    scheduleLinePosBalanceRefresh() {}, persistCache() {},
                };
                const line = CrmPosAction.prototype.addProduct.call(pos, {id: 1, name: 'Manual item', default_price: 25}, 2);
                if (bill.lines.length !== 1 || line.qty !== 2 || line.sell_price !== 25 || line.uom_id !== 3)
                    throw new Error('Manual native product entry failed');
                console.log('test successful');
            })().catch(error => console.error(error));
            """,
            ready="!!odoo.__WOWL_DEBUG__?.root",
            login='admin',
            timeout=90,
        )

    @no_retry
    def test_branch_import_toolbar_english_and_arabic(self):
        self.env['res.lang']._activate_lang('ar_001')
        for language, label in [('en_US', 'Import Branch Locations'),
                                ('ar_001', 'استيراد مواقع الفروع')]:
            self.env.ref('base.user_admin').lang = language
            self.browser_js(
                '/odoo?debug=assets',
                """
                (async () => {
                    const env = odoo.__WOWL_DEBUG__.root.env;
                    await env.services.action.doAction('ab_crm_sales_workspace.action_branch_locations');
                    const button = [...document.querySelectorAll('.o_control_panel button')]
                        .find(button => button.textContent.trim() === LABEL);
                    if (!button || !document.querySelector('.o_list_button_add'))
                        throw new Error('Import button must be visible beside New with no selection');
                    if (document.querySelector('.o_data_row_selected'))
                        throw new Error('Unexpected selection');
                    button.click();
                    for (let attempt = 0; attempt < 50 && !document.querySelector('.modal .o_field_widget[name="file"]'); attempt++)
                        await new Promise(resolve => setTimeout(resolve, 100));
                    if (!document.querySelector('.modal .o_field_widget[name="file"]'))
                        throw new Error('Import popup missing');
                    console.log('test successful');
                })().catch(error => console.error(error));
                """.replace('LABEL', repr(label)),
                ready="!!odoo.__WOWL_DEBUG__?.root", login='admin', timeout=90,
            )
