import hashlib
from types import SimpleNamespace
from unittest.mock import patch

from odoo.exceptions import AccessError
from .test_adapter import TestCapture
from ..models.chat import opaque


class TestCheckoutIdentity(TestCapture):
    def test_account_metadata_is_captured_before_confirmation(self):
        self.endpoint.guest_metadata_enabled = True
        owner = hashlib.sha256(f'user:{self.env.uid}'.encode()).hexdigest()
        submission = self.env['ab_storefront_submission']._issue('checkout', self.website, owner)
        self.assertEqual(submission.callcenter_origin, 'account')
        self.assertEqual(submission.callcenter_account_identity, opaque(self.endpoint.source, 'account:' + str(self.env.uid)))
        order = self.cart()
        order.ab_checkout_submission_id = submission
        order._cart_add(self.product.id, 1)
        order.action_confirm()
        self.assertEqual(order._ab_callcenter_snapshot()['origin_kind'], 'account')
        with self.assertRaises(AccessError):
            submission.write({'callcenter_origin': 'guest'})

    def test_guest_metadata_requires_trusted_browser_owner(self):
        self.endpoint.guest_metadata_enabled = True
        owner = hashlib.sha256(b'guest:trusted-browser').hexdigest()
        submissions = self.env['ab_storefront_submission'].with_user(self.website.user_id)
        with patch('odoo.http.request', SimpleNamespace(session={'ab_submission_owner': 'trusted-browser'})):
            submission = submissions._issue('checkout', self.website, owner)
            forged = submissions._issue('checkout', self.website, hashlib.sha256(b'guest:foreign').hexdigest())
        self.assertEqual(submission.callcenter_origin, 'guest')
        self.assertEqual(submission.callcenter_visitor_identity, opaque(self.endpoint.source, 'checkout:' + owner))
        self.assertFalse(forged.callcenter_origin)
        order = self.cart()
        order.ab_checkout_submission_id = submission
        order._cart_add(self.product.id, 1)
        order.action_confirm()
        snapshot = order._ab_callcenter_snapshot()
        self.assertEqual(snapshot['origin_kind'], 'guest')
        self.assertEqual(snapshot['visitor_identity'], submission.callcenter_visitor_identity)

    def test_optional_metadata_is_disabled_by_default(self):
        owner = hashlib.sha256(f'user:{self.env.uid}'.encode()).hexdigest()
        submission = self.env['ab_storefront_submission']._issue('checkout', self.website, owner)
        self.assertFalse(submission.callcenter_origin)
