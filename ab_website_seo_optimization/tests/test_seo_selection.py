from lxml import etree

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSeoSelection(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        card = cls.env['ab_product_card'].create({'name': 'SEO Selection Product'})
        source = cls.env['ab_product'].create({'product_card_id': card.id, 'code': 'SEO-SELECTION-TEST'})
        cls.product = cls.env['product.template'].create({'name': card.name, 'ab_product_id': source.id, 'is_published': True, 'sale_ok': True})
        cls.seo = cls.env['ab.product.seo'].create({'product_template_id': cls.product.id})
        cls.english = cls.seo.translation_ids.filtered(lambda row: row.lang_code == 'en_US')

    def fill_content(self):
        self.english.write({'meta_title': 'SEO Selection Product', 'meta_description': 'Product description for selection.'})

    def test_blank_record_is_not_processed(self):
        self.assertFalse(self.product.ab_has_seo_content)
        self.assertTrue(self.product.filtered_domain([('ab_has_seo_content', '=', False)]))

    def test_content_updates_indicator_and_search(self):
        self.assertFalse(self.product.ab_has_seo_content)
        self.fill_content()
        self.assertTrue(self.product.ab_has_seo_content)
        self.assertEqual(self.env['product.template'].search([('id', '=', self.product.id), ('ab_has_seo_content', '=', True)]), self.product)
        self.assertFalse(self.env['product.template'].search([('id', '=', self.product.id), ('ab_has_seo_content', '=', False)]))
        self.seo.active = False
        self.assertFalse(self.product.ab_has_seo_content)
        self.assertFalse(self.env['product.template'].search([('id', '=', self.product.id), ('ab_has_seo_content', '=', True)]))

    def test_fields_must_belong_to_same_language(self):
        self.english.meta_title = 'English title'
        self.seo.translation_ids.filtered(lambda row: row.lang_code == 'ar_001').meta_description = 'وصف عربي'
        self.assertFalse(self.product.ab_has_seo_content)
        self.assertFalse(self.env['product.template'].search([('id', '=', self.product.id), ('ab_has_seo_content', '=', True)]))

    def test_website_scope_matches_indicator_and_filter(self):
        self.fill_content()
        website = self.env['website'].create({'name': 'SEO Selection Website'})
        other = self.env['website'].create({'name': 'Other SEO Selection Website'})
        self.seo.website_id = website
        scoped = self.product.with_context(ab_seo_website_id=other.id)
        self.assertFalse(scoped.ab_has_seo_content)
        self.assertFalse(scoped.search([('id', '=', self.product.id), ('ab_has_seo_content', '=', True)]))
        self.assertTrue(self.product.with_context(ab_seo_website_id=website.id).ab_has_seo_content)
        self.seo.website_id = False
        self.assertTrue(scoped.ab_has_seo_content)

    def test_other_company_content_is_not_exposed_to_seo_user(self):
        self.fill_content()
        other = self.env['res.company'].create({'name': 'SEO Selection Other Company'})
        self.seo.company_id = other
        group = self.env.ref('ab_website_seo_optimization.group_ab_website_seo_optimization_user')
        user = self.env['res.users'].create({'name': 'SEO Selection Reader', 'login': 'seo_selection_reader',
            'group_ids': [(6, 0, (group | self.env.ref('base.group_user')).ids)],
            'company_id': self.env.company.id, 'company_ids': [(6, 0, self.env.company.ids)]})
        product = self.product.with_user(user)
        self.assertFalse(product.ab_has_seo_content)
        self.assertFalse(product.action_open_existing_seo())
        self.assertFalse(product.search([('id', '=', self.product.id), ('ab_has_seo_content', '=', True)]))
        self.seo.company_id = self.env.company
        self.assertTrue(product.ab_has_seo_content)
        self.assertEqual(product.action_open_existing_seo()['res_id'], self.seo.id)
        self.assertEqual(product.search([('id', '=', self.product.id), ('ab_has_seo_content', '=', True)]), product)

    def test_public_user_cannot_read_indicator(self):
        with self.assertRaises(AccessError):
            self.product.with_user(self.env.ref('base.public_user')).read(['ab_has_seo_content'])

    def test_selection_views_are_scoped_to_seo(self):
        product = self.env['product.template']
        default = etree.fromstring(product.get_view(view_type='list')['arch'])
        self.assertFalse(default.xpath("//field[@name='ab_has_seo_content']"))
        custom = product.with_context(list_view_ref='ab_website_seo_optimization.view_seo_product_selection_list',
            search_view_ref='ab_website_seo_optimization.view_seo_product_selection_search')
        tree = etree.fromstring(custom.get_view(view_type='list')['arch'])
        self.assertTrue(tree.xpath("//field[@name='ab_has_seo_content']"))
        search = etree.fromstring(custom.get_view(view_type='search')['arch'])
        self.assertTrue(search.xpath("//filter[@name='ab_without_seo_content']"))

    def test_selection_labels_are_translated(self):
        english = self.env['product.template'].with_context(lang='en_US')
        arabic = self.env['product.template'].with_context(lang='ar_001')
        self.assertEqual(english.fields_get(['ab_has_seo_content'])['ab_has_seo_content']['string'], 'Has SEO Content')
        self.assertEqual(arabic.fields_get(['ab_has_seo_content'])['ab_has_seo_content']['string'], 'تم إعداد محتوى SEO')
        status = arabic.fields_get(['ab_seo_content_status'])['ab_seo_content_status']
        self.assertEqual(status['string'], 'حالة SEO')
        self.assertEqual(dict(status['selection'])['prepared'], 'تم إعداد SEO')
        self.assertEqual(dict(status['selection'])['missing'], 'لم يُعد بعد')
        search = etree.fromstring(arabic.with_context(search_view_ref='ab_website_seo_optimization.view_seo_product_selection_search').get_view(view_type='search')['arch'])
        self.assertEqual(search.xpath("//filter[@name='ab_without_seo_content']/@string"), ['لم يُعد له محتوى SEO'])

    def test_status_badge_and_existing_record_action(self):
        self.assertEqual(self.product.ab_seo_content_status, 'missing')
        self.assertEqual(self.product.action_open_existing_seo()['res_id'], self.seo.id)
        self.fill_content()
        self.assertEqual(self.product.ab_seo_content_status, 'prepared')
        action = self.product.action_open_existing_seo()
        self.assertEqual(action['res_model'], 'ab.product.seo')
        self.assertEqual(action['res_id'], self.seo.id)
        self.assertEqual(action['target'], 'current')
        self.seo.active = False
        self.assertFalse(self.product.action_open_existing_seo())

    def test_existing_record_action_respects_website_and_company(self):
        self.fill_content()
        website = self.env['website'].create({'name': 'SEO Dialog Website'})
        other_website = self.env['website'].create({'name': 'Other SEO Dialog Website'})
        self.seo.website_id = website
        self.assertFalse(self.product.with_context(ab_seo_website_id=other_website.id).action_open_existing_seo())
        self.assertEqual(self.product.with_context(ab_seo_website_id=website.id).action_open_existing_seo()['res_id'], self.seo.id)
        other_company = self.env['res.company'].create({'name': 'SEO Dialog Other Company'})
        self.seo.company_id = other_company
        self.assertFalse(self.product.action_open_existing_seo())

    def test_public_cannot_open_existing_seo(self):
        self.fill_content()
        with self.assertRaises(AccessError):
            self.product.with_user(self.env.ref('base.public_user')).action_open_existing_seo()

    def test_selector_uses_default_filter_and_wide_status_badge(self):
        product = self.env['product.template'].with_context(list_view_ref='ab_website_seo_optimization.view_seo_product_selection_list')
        view = etree.fromstring(product.get_view(view_type='list')['arch'])
        status = view.xpath("//field[@name='ab_seo_content_status']")[0]
        self.assertEqual(status.get('widget'), 'badge')
        self.assertEqual(status.get('width'), '180px')
        form = etree.fromstring(self.env['ab.product.seo'].get_view(view_type='form')['arch'])
        selector = form.xpath("//field[@name='product_template_id']")[0]
        self.assertEqual(selector.get('widget'), 'ab_seo_product_selector')
        self.assertIn("'search_default_ab_without_seo_content': 1", selector.get('context'))
        bulk = etree.fromstring(self.env['ab.product.seo.bulk.optimization'].get_view(view_type='form')['arch'])
        self.assertIn("'search_default_ab_without_seo_content': 1", bulk.xpath("//field[@name='product_selection_ids']/@context")[0])

    def test_blank_draft_is_detected_before_content_exists(self):
        self.assertFalse(self.product.ab_has_seo_content)
        self.assertEqual(self.product.action_open_existing_seo()['res_id'], self.seo.id)
        self.english.meta_title = 'Incomplete SEO draft'
        self.assertFalse(self.product.ab_has_seo_content)
        self.assertEqual(self.product.action_open_existing_seo()['res_id'], self.seo.id)

    def test_existing_record_matches_exact_website_scope(self):
        website = self.env['website'].create({'name': 'Draft selector website'})
        scoped = self.product.with_context(ab_seo_website_id=website.id)
        self.assertFalse(scoped.action_open_existing_seo())
        specific = self.env['ab.product.seo'].create({'product_template_id': self.product.id, 'website_id': website.id})
        self.assertEqual(scoped.action_open_existing_seo()['res_id'], specific.id)
        self.assertEqual(self.product.action_open_existing_seo()['res_id'], self.seo.id)
