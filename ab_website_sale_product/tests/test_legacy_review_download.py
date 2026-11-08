import base64
import csv
import io

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged
from odoo.tests.common import HttpCase, new_test_user


@tagged('post_install', '-at_install')
class TestLegacyReviewDownload(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.website = cls.env.ref('website.default_website')
        english = cls.env['res.lang']._activate_lang('en_US')
        cls.website.write({
            'language_ids': [(4, english.id)], 'default_lang_id': english.id,
        })
        cls.env['ir.config_parameter'].sudo().set_param(
            'ab_website_sale_product.development', 'False',
        )
        groups = 'base.group_user,website.group_website_designer'
        if cls.env.ref('ab_store.ab_login_from_anywhere', raise_if_not_found=False):
            groups += ',ab_store.ab_login_from_anywhere'
        cls.owner = new_test_user(
            cls.env, login='review_download_owner', groups=groups,
            company_id=cls.website.company_id.id, lang='en_US',
        )
        cls.other = new_test_user(
            cls.env, login='review_download_other', groups=groups,
            company_id=cls.website.company_id.id,
        )
        cls.portal = new_test_user(
            cls.env, login='review_download_portal', groups='base.group_portal',
            company_id=cls.website.company_id.id,
        )
        cls.administrator = new_test_user(
            cls.env, login='review_download_admin', groups=groups + ',base.group_system',
            company_id=cls.website.company_id.id,
        )

    def _batch(self):
        batch = self.env['ab_ecommerce_legacy_batch'].with_user(self.owner).create({
            'name': 'Review download regression', 'website_id': self.website.id,
            'source_file': base64.b64encode(
                b'source_id,name,mobile_phone\n1,Review customer,01012345678\n',
            ),
        })
        batch.action_preview()
        return batch

    def test_owner_downloads_review_over_http_without_development_mode(self):
        batch = self._batch()
        self.authenticate(self.owner.login, self.owner.login)
        action = batch.action_download_review()
        response = self.url_open(action['url'])
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/csv', response.headers['Content-Type'])
        self.assertIn('no-store', response.headers['Cache-Control'])
        self.assertIn('legacy-customer-review-', response.headers['Content-Disposition'])
        self.assertEqual(response.headers['X-Content-Type-Options'], 'nosniff')
        self.assertTrue(response.content.startswith(b'\xef\xbb\xbf'))
        rows = list(csv.DictReader(io.StringIO(response.content.decode('utf-8-sig'))))
        self.assertEqual(rows[0]['Review: status'], 'Eligible')
        self.assertNotIn('activation_code', rows[0])
        self.assertEqual(batch.state, 'ready')
        self.assertEqual(batch.created_count, 0)

    def test_other_owner_and_portal_cannot_download_review(self):
        batch = self._batch()
        for actor in (self.other, self.portal):
            with self.subTest(actor=actor.login):
                self.authenticate(actor.login, actor.login)
                response = self.url_open(f'/ab_legacy/review/{batch.id}')
                self.assertEqual(response.status_code, 403)
                with self.assertRaises(AccessError):
                    batch.with_user(actor).action_download_review()

    def test_anonymous_download_requires_login(self):
        batch = self._batch()
        response = self.url_open(f'/ab_legacy/review/{batch.id}', allow_redirects=False)
        self.assertEqual(response.status_code, 303)
        self.assertIn('/web/login', response.headers['Location'])

    def test_administrator_can_download_other_owner_review(self):
        batch = self._batch()
        self.authenticate(self.administrator.login, self.administrator.login)
        response = self.url_open(f'/ab_legacy/review/{batch.id}')
        self.assertEqual(response.status_code, 200)

    def test_review_rejects_other_company(self):
        batch = self._batch()
        company = self.env['res.company'].create({'name': 'Review isolated company'})
        website = self.env['website'].create({'name': 'Review isolated website', 'company_id': company.id})
        batch.sudo().write({'website_id': website.id})
        self.authenticate(self.owner.login, self.owner.login)
        self.assertEqual(self.url_open(f'/ab_legacy/review/{batch.id}').status_code, 403)
        with self.assertRaises(AccessError):
            batch.action_download_review()

    def test_activation_code_export_still_requires_https(self):
        batch = self._batch()
        batch.action_process_next()
        self.authenticate(self.owner.login, self.owner.login)
        self.assertEqual(self.url_open(batch.action_download()['url']).status_code, 403)
        self.assertEqual(batch.export_count, 0)

    def test_outdated_preview_still_requires_recheck(self):
        batch = self._batch()
        batch.sudo().write({'review_version': 0})
        with self.assertRaises(UserError):
            batch.action_download_review()
