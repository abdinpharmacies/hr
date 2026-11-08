from unittest.mock import patch

from odoo.tests import HttpCase, tagged, new_test_user
from odoo.tests.common import ChromeBrowser


@tagged("post_install", "-at_install")
class TestApiWorkspace(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        user_env = cls.env(context=dict(cls.env.context, no_reset_password=True))
        cls.admin = new_test_user(
            user_env, login="api_workspace_admin", password="api_workspace_admin",
            groups="base.group_system", lang="en_US",
        )
        cls.employee = new_test_user(
            user_env, login="api_workspace_employee", password="api_workspace_employee",
            groups="base.group_user",
        )
        cls.website = cls.env["website"].search([], limit=1)
        cls.website.language_ids = cls.env["res.lang"].search([("code", "in", ["en_US", "ar_001"])])

    def test_workspace_action_and_menu(self):
        action = self.env.ref("ab_ecommerce_api.action_api_workspace")
        menu = self.env.ref("ab_ecommerce_api.menu_api_docs")
        self.assertEqual(action.tag, "ab_ecommerce_api.workspace")
        self.assertEqual(menu.action, action)
        self.assertEqual(menu.group_ids, self.env.ref("base.group_system"))
        self.assertEqual(self.env.ref("ab_ecommerce_api.action_api_docs").url, "/api/v1/docs")
        self.assertNotEqual(menu.with_context(lang="en_US").name, menu.with_context(lang="ar_001").name)

    def test_embedded_documentation_and_frame_protection(self):
        self.authenticate(self.admin.login, self.admin.login)
        page = self.url_open("/api/v1/docs?embedded=1&lang=en_US")
        self.assertEqual(page.status_code, 200)
        self.assertIn('id="ab-ecommerce-api-swagger"', page.text)
        self.assertIn("/ab_ecommerce_api/static/lib/swagger-ui/swagger-ui-bundle.js", page.text)
        self.assertIn("/ab_ecommerce_api/static/lib/swagger-ui/docs-init.js", page.text)
        self.assertNotIn("<h1>", page.text)
        self.assertEqual(page.headers.get("X-Frame-Options"), "SAMEORIGIN")
        self.assertIn("no-store", page.headers.get("Cache-Control", ""))
        standalone = self.url_open("/api/v1/docs?lang=en_US")
        self.assertIn("<h1>", standalone.text)

    def test_internal_user_cannot_open_documentation(self):
        self.authenticate(self.employee.login, self.employee.login)
        self.assertEqual(self.url_open("/api/v1/docs?embedded=1").status_code, 403)
        self.assertEqual(self.url_open("/api/v1/openapi.json").status_code, 403)

    def _check_workspace_browser(self, lang, size):
        self.admin.lang = lang
        self.browser_size = size
        original_ready = ChromeBrowser._wait_ready

        def capture(browser, condition):
            result = original_ready(browser, condition)
            if result:
                browser.take_screenshot().result(timeout=10)
            return result

        with patch.object(ChromeBrowser, "_wait_ready", capture):
            self.browser_js(
                "/odoo/action-ab_ecommerce_api.action_api_workspace",
                """
                (async () => {
                    const workspace = document.querySelector('.ab_api_workspace');
                    if (workspace.scrollWidth > workspace.clientWidth + 2) {
                        throw new Error('API workspace overflows horizontally');
                    }
                    const docsButton = workspace.querySelector('[data-api-tab="docs"]');
                    const guideButton = workspace.querySelector('[data-api-tab="guide"]');
                    guideButton.click();
                    await new Promise(resolve => setTimeout(resolve, 100));
                    if (getComputedStyle(workspace.querySelector('.ab_api_workspace_guide')).display === 'none') {
                        throw new Error('Quick start is not visible');
                    }
                    docsButton.click();
                    await new Promise(resolve => setTimeout(resolve, 100));
                    const frame = workspace.querySelector('iframe');
                    const swagger = frame.contentDocument;
                    if (!swagger.querySelector('.swagger-ui .authorize')) {
                        throw new Error('Swagger authorization control is missing');
                    }
                    if (swagger.querySelectorAll('.opblock').length !== 62) {
                        throw new Error('API operations were not rendered');
                    }
                    const config = Array.from(swagger.querySelectorAll('.opblock-get')).find(
                        node => node.querySelector('.opblock-summary-path')?.textContent.trim() === '/config'
                    );
                    config.querySelector('.opblock-summary-control').click();
                    let deadline = Date.now() + 5000;
                    while (!config.querySelector('.try-out__btn') && Date.now() < deadline) {
                        await new Promise(resolve => setTimeout(resolve, 50));
                    }
                    const tryButton = config.querySelector('.try-out__btn');
                    if (!tryButton) {
                        throw new Error('Swagger Try it out control is missing');
                    }
                    tryButton.click();
                    deadline = Date.now() + 5000;
                    while (!config.querySelector('.execute') && Date.now() < deadline) {
                        await new Promise(resolve => setTimeout(resolve, 50));
                    }
                    const executeButton = config.querySelector('.execute');
                    if (!executeButton) {
                        throw new Error('Swagger Execute control is missing');
                    }
                    console.log('test successful');
                })();
                """,
                ready="Boolean(document.querySelector('.ab_api_workspace iframe')?.contentDocument?.querySelector('.swagger-ui .opblock'))",
                login=self.admin.login, timeout=90,
            )

    def test_workspace_browser_english(self):
        self._check_workspace_browser("en_US", "1440x1000")

    def test_workspace_browser_arabic(self):
        self._check_workspace_browser("ar_001", "768x1024")
