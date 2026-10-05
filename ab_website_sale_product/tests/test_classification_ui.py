from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestClassificationUI(HttpCase):
    def test_category_button_and_progress_page(self):
        self.env["ab_product_classification_taxonomy"].action_prepare()
        product = self.env["ab_product"].create({"name": "ELVIVE SHAMPOO", "product_card_name": "ELVIVE SHAMPOO", "code": "CLS-UI"})
        self.env["product.template"].create({"name": "New unclassified browser product"})
        node = self.env["ab_product_classification_taxonomy"].search([("key", "=", "hair_care__shampoo")])
        self.env["product.template"].create({"name": "Categorized browser product", "public_categ_ids": [(6, 0, node.category_id.ids)]})
        run = self.env["ab_product_classification_run"]._internal().create({"name": "Browser classification run", "state": "running", "scope": "website", "website_id": self.env["website"].search([], limit=1).id, "requested_by": self.env.ref("base.user_admin").id, "company_id": self.env.company.id, "snapshot_done": True, "total_products": 1})
        self.env["ab_product_classification_result"]._internal().create({"run_id": run.id, "ab_product_id": product.id, "product_key": f"ab:{product.id}", "product_name": product.name})
        run._process_batch()
        self.browser_js("/odoo/ecommerce-categories", """
            (async () => {
            const waitFor = async (selector) => {
                for (let i = 0; i < 100; i++) {
                    const element = document.querySelector(selector);
                    if (element) return element;
                    await new Promise(resolve => setTimeout(resolve, 100));
                }
                throw new Error('Missing UI element: ' + selector);
            };
            await waitFor('.o_list_view');
            const classify = [...document.querySelectorAll('button')].find(b => b.textContent.trim() === 'Classify Products');
            if (!classify) throw new Error('Classification button is missing');
            classify.click();
            await waitFor('.ab_product_classification');
            await waitFor('#ab_classification_scope');
            if (!document.querySelector('.ab_product_classification').textContent.includes('Products in selected scope')) {
                throw new Error('Dashboard data did not render');
            }
            await waitFor('.ab_classification_metrics');
            if (!document.querySelector('.ab_product_classification').textContent.includes('100.0%')) {
                throw new Error('Completed progress did not render');
            }
            const coverage = await waitFor('.ab_classification_coverage_percent');
            const before = parseFloat(coverage.textContent);
            if (!(before > 0 && before < 100)) throw new Error('Coverage must differ from completed run progress');
            const response = await fetch('/web/dataset/call_kw/product.template/create', {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({jsonrpc: '2.0', method: 'call', params: {
                    model: 'product.template', method: 'create',
                    args: [{name: 'Browser new catalog arrival'}], kwargs: {},
                }}),
            });
            const created = await response.json();
            if (created.error) throw new Error('Could not create the test arrival');
            for (let i = 0; i < 100 && parseFloat(coverage.textContent) >= before; i++) {
                await new Promise(resolve => setTimeout(resolve, 100));
            }
            if (!(parseFloat(coverage.textContent) < before)) throw new Error('Coverage did not decrease automatically after a new product');
            const clickButton = async (label, expectedState) => {
                for (let i = 0; i < 100; i++) {
                    const button = [...document.querySelectorAll('.ab_product_classification button')].find(b => b.textContent.trim() === label && !b.disabled);
                    if (button) {
                        button.click();
                        for (let attempt = 0; attempt < 100; attempt++) {
                            await new Promise(resolve => setTimeout(resolve, 100));
                            if (document.querySelector('.ab_product_classification .badge')?.textContent.trim() === expectedState) return;
                        }
                        throw new Error(label + ' did not reach ' + expectedState);
                    }
                    await new Promise(resolve => setTimeout(resolve, 100));
                }
                throw new Error('Missing action: ' + label);
            };
            await clickButton('Start Classification', 'Queued');
            await clickButton('Pause', 'Paused');
            await clickButton('Resume', 'Queued');
            await clickButton('Stop', 'Stopped');
            await clickButton('Resume', 'Queued');
            await clickButton('Stop', 'Stopped');
            console.log('test successful');
            })().catch(error => console.error(error));
        """, login="admin", timeout=90)
