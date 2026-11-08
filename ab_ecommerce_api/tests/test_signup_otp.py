from odoo.exceptions import AccessDenied
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from ..controllers.api import EcommerceApi


@tagged("post_install", "-at_install")
class TestApiSignupOtp(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.website = cls.env.ref("website.default_website")
        cls.user = cls.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Pending OTP API customer", "login": "+201012345680",
            "password": "Original9!Pass", "ab_signup_otp_pending": True,
            "company_id": cls.website.company_id.id,
            "company_ids": [(6, 0, cls.website.company_id.ids)],
            "group_ids": [(6, 0, [cls.env.ref("base.group_portal").id])],
        })

    def test_pending_customer_cannot_receive_bearer_tokens(self):
        with self.assertRaises(AccessDenied):
            self.env["ab_ecommerce_api_session"]._issue(self.user, self.website)
        result = EcommerceApi()._tokens(self.user)
        self.assertTrue(result["verification_required"])
        self.assertEqual(result["verification_url"], "/web/login")
        self.assertNotIn("access_token", result)

    def test_verified_customer_can_receive_bearer_tokens(self):
        self.user.ab_signup_otp_pending = False
        session, tokens = self.env["ab_ecommerce_api_session"]._issue(self.user, self.website)
        self.assertEqual(session.user_id, self.user)
        self.assertTrue(tokens["access_token"])

    def test_email_customer_can_receive_tokens_even_with_old_pending_flag(self):
        self.user.login = "pending.api.otp@example.test"
        self.assertTrue(self.user.ab_signup_otp_pending)
        session, tokens = self.env["ab_ecommerce_api_session"]._issue(self.user, self.website)
        self.assertEqual(session.user_id, self.user)
        self.assertTrue(tokens["access_token"])
