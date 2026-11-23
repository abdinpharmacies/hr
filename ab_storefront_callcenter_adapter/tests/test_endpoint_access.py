from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestEndpointAccess(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.foreign_company = cls.env['res.company'].create({'name': 'Endpoint foreign company'})
        internal = cls.env.ref('base.group_user')
        service = cls.env.ref('ab_storefront_callcenter_adapter.group_service')
        system = cls.env.ref('base.group_system')
        companies = cls.company | cls.foreign_company
        cls.worker = cls.env['res.users'].create({'name': 'Endpoint worker', 'login': 'endpoint-worker',
            'company_id': cls.company.id, 'company_ids': [Command.set(companies.ids)],
            'group_ids': [Command.set((internal | service).ids)]})
        cls.other_worker = cls.env['res.users'].create({'name': 'Other endpoint worker', 'login': 'endpoint-other-worker',
            'company_id': cls.company.id, 'company_ids': [Command.set(cls.company.ids)],
            'group_ids': [Command.set((internal | service).ids)]})
        cls.admin = cls.env['res.users'].create({'name': 'Endpoint administrator', 'login': 'endpoint-admin',
            'company_id': cls.company.id, 'company_ids': [Command.set(companies.ids)],
            'group_ids': [Command.set((internal | service | system).ids)]})
        cls.endpoints = cls.env['ab_storefront_callcenter_endpoint']
        for name, company, worker in [('Owned endpoint', cls.company, cls.worker),
                ('Other endpoint', cls.company, cls.other_worker),
                ('Foreign endpoint', cls.foreign_company, cls.worker)]:
            website = cls.env['website'].create({'name': name, 'company_id': company.id})
            cls.endpoints |= cls.env['ab_storefront_callcenter_endpoint'].create({
                'name': name, 'website_id': website.id, 'service_user_id': worker.id})

    def test_admin_with_service_role_sees_allowed_company_endpoints(self):
        model = self.env['ab_storefront_callcenter_endpoint'].with_user(self.admin).with_context(
            allowed_company_ids=self.company.ids)
        expected = self.endpoints.filtered(lambda endpoint: endpoint.company_id == self.company)
        self.assertEqual(model.search([('id', 'in', self.endpoints.ids)]), expected)
        other = expected.filtered(lambda endpoint: endpoint.service_user_id == self.other_worker)
        self.assertEqual(model.browse(other.id).read(['name'])[0]['name'], other.name)
        foreign = self.endpoints - expected
        with self.assertRaises(AccessError):
            model.browse(foreign.id).read(['name'])
        self.assertEqual(model.with_context(allowed_company_ids=self.foreign_company.ids).search(
            [('id', 'in', self.endpoints.ids)]), foreign)

    def test_service_role_retains_ownership_company_and_write_restrictions(self):
        model = self.env['ab_storefront_callcenter_endpoint'].with_user(self.worker).with_context(
            allowed_company_ids=self.company.ids)
        own = self.endpoints.filtered(lambda endpoint: endpoint.company_id == self.company
            and endpoint.service_user_id == self.worker)
        self.assertEqual(model.search([('id', 'in', self.endpoints.ids)]), own)
        for endpoint in self.endpoints - own:
            with self.assertRaises(AccessError):
                model.browse(endpoint.id).read(['name'])
        with self.assertRaises(AccessError):
            model.browse(own.id).write({'name': 'Unauthorized change'})
