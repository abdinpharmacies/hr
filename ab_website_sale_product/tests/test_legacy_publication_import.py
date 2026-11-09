import base64
import csv
import io
import json

from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase


class TestLegacyPublicationImport(TransactionCase):
    def setUp(self):
        super().setUp()
        self.website = self.env.ref('website.default_website')
        self.Product = self.env['ab_product'].sudo()
        self.Wizard = self.env['ab_legacy_publication_import']

    def product(self, code, name=None):
        name = name or code
        return self.Product.create({
            'name': name, 'product_card_name': name, 'code': code,
            'active': True, 'allow_sale': True, 'website_sale_available': True,
            'default_price': 20.0,
        })

    def wizard(self, codes):
        rows = [{'id': index, 'default_code': code} for index, code in enumerate(codes, 1)]
        payload = {
            'source': 'https://abdinpharmacies.com',
            'exported_at': '2026-11-08T10:00:00Z',
            'model': 'product.template',
            'publication_field': 'is_published',
            'published_count': len(rows), 'products': rows,
        }
        return self.Wizard.create({
            'website_id': self.website.id,
            'source_file': base64.b64encode(json.dumps(payload).encode()),
        })

    def csv_wizard(self, rows):
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Name', 'Internal Reference', 'Website Product Category'])
        writer.writerows(rows)
        return self.Wizard.create({
            'website_id': self.website.id,
            'source_filename': 'Product Template (product.template) (1).csv',
            'source_file': base64.b64encode(output.getvalue().encode()),
        })

    def test_preview_and_apply_match_old_publication(self):
        published = self.product('LEGACY-PUBLISHED')
        surplus = self.product('LEGACY-SURPLUS')
        surplus_template = surplus._sync_website_products(create_missing=True, publish_requested=True)
        wizard = self.wizard([published.code])
        wizard.action_preview()
        self.assertEqual((wizard.create_count, wizard.publish_count), (1, 1))
        self.assertGreaterEqual(wizard.unpublish_count, 1)
        self.assertTrue(surplus_template.is_published)
        wizard.action_apply()
        self.assertTrue(published.website_product_tmpl_id.is_published)
        self.assertFalse(surplus_template.is_published)
        self.assertEqual(wizard.state, 'done')

    def test_missing_code_is_reported_and_not_published(self):
        included = self.product('LEGACY-INCLUDED')
        surplus = self.product('LEGACY-SURPLUS')
        template = surplus._sync_website_products(create_missing=True, publish_requested=True)
        wizard = self.wizard([included.code, 'NO-MATCH-CODE'])
        wizard.action_preview()
        self.assertEqual(wizard.missing_count, 1)
        self.assertTrue(template.is_published)
        wizard.action_apply()
        self.assertTrue(included.website_product_tmpl_id.is_published)
        self.assertFalse(template.is_published)

    def test_changed_file_requires_new_preview(self):
        product = self.product('LEGACY-PUBLISHED')
        wizard = self.wizard([product.code])
        wizard.action_preview()
        wizard.source_file = self.wizard(['OTHER-CODE']).source_file
        with self.assertRaises(UserError):
            wizard.action_apply()
        self.assertFalse(product.website_product_tmpl_id)

    def test_regular_user_cannot_apply_export(self):
        product = self.product('LEGACY-PUBLISHED')
        wizard = self.wizard([product.code])
        wizard.action_preview()
        with self.assertRaises(AccessError):
            wizard.with_user(self.env.ref('base.public_user')).action_apply()
        self.assertFalse(product.website_product_tmpl_id)

    def test_csv_export_matches_only_listed_products(self):
        included = self.product('LEGACY-CODED')
        missing_code = self.product('LEGACY-NAME-ONLY')
        surplus = self.product('LEGACY-SURPLUS')
        surplus_template = surplus._sync_website_products(create_missing=True, publish_requested=True)
        wizard = self.csv_wizard([
            [included.name, included.code, 'Medicines'],
            ['', '', 'Medicines / Vitamins'],
            [missing_code.name, '', 'Medicines'],
        ])
        wizard.action_preview()
        self.assertEqual((wizard.published_count, wizard.create_count), (2, 2))
        self.assertGreaterEqual(wizard.unpublish_count, 1)
        wizard.action_apply()
        self.assertTrue(included.website_product_tmpl_id.is_published)
        self.assertTrue(missing_code.website_product_tmpl_id.is_published)
        self.assertFalse(surplus_template.is_published)

    def test_csv_unknown_product_without_code_blocks_apply(self):
        wizard = self.csv_wizard([['UNKNOWN OLD PRODUCT', '', 'Medicines']])
        with self.assertRaises(UserError):
            wizard.action_preview()

    def test_ineligible_product_is_reported_and_stays_unpublished(self):
        included = self.product('LEGACY-INCLUDED')
        ineligible = self.product('LEGACY-INELIGIBLE')
        ineligible.website_sale_available = False
        wizard = self.wizard([included.code, ineligible.code])
        wizard.action_preview()
        self.assertEqual(wizard.ineligible_count, 1)
        wizard.action_apply()
        self.assertTrue(included.website_product_tmpl_id.is_published)
        self.assertFalse(ineligible.website_product_tmpl_id)

    def test_csv_uncoded_name_suffix_and_duplicate_coded_row(self):
        axe = self.product('LEGACY-AXE', 'AXE SPRAY EXCITE 150 ML 1 BOX')
        dozova = self.product('LEGACY-DOZOVA', 'DOZOVA ALPHA-LIPOIC ACID')
        wizard = self.csv_wizard([
            ['AXE SPRAY EXCITE 150 ML--', '', 'Personal Care'],
            [dozova.name, '', 'Medicines'],
            [dozova.name, dozova.code, 'Medicines'],
        ])
        wizard.action_preview()
        self.assertEqual(wizard.published_count, 2)
        wizard.action_apply()
        self.assertTrue(axe.website_product_tmpl_id.is_published)
        self.assertTrue(dozova.website_product_tmpl_id.is_published)

    def test_unlinked_templates_follow_export_too(self):
        Template = self.env['product.template'].sudo()
        included = Template.create({
            'name': 'Included Unlinked', 'default_code': 'CSV-UNLINKED-IN',
            'is_published': False,
        })
        excluded = Template.create({
            'name': 'Excluded Unlinked', 'default_code': 'CSV-UNLINKED-OUT',
            'is_published': True,
        })
        uncoded = Template.create({
            'name': 'Excluded Without Code', 'is_published': True,
        })
        wizard = self.csv_wizard([[included.name, included.default_code, 'Medicines']])
        wizard.action_preview()
        wizard.action_apply()
        self.assertTrue(included.is_published)
        self.assertFalse(excluded.is_published)
        self.assertFalse(uncoded.is_published)
