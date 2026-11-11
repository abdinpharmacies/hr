import unittest
from seed_metadata import inspect_metadata


class MetadataTests(unittest.TestCase):
    def scan(self, value, table='ir_ui_view', field='arch_db'):
        return inspect_metadata(value, table, field, {'company_id', 'partner_id', 'res.partner'}, {1, 4, 16})

    def test_formatting_and_dynamic_references_are_not_ids(self):
        self.assertEqual(self.scan('<form><field name="partner_id"/><div style="padding:16px" colspan="4"/></form>'), [])
        self.assertEqual(self.scan('<div style="padding:16px"><t t-out="object.company_id.name"/><a t-attf-href="/logo?company={{object.company_id.id}}">Hello 4</a></div>', 'mail_template', 'body_html'), [])

    def test_documentation_is_not_executed(self):
        for table, field in [('ir_model_fields','help'), ('ir_module_module','description')]:
            self.assertEqual(self.scan({'en_US': "res.partner browse(4)"}, table, field), [])

    def test_domains_and_contexts_with_implicit_model(self):
        for expression in ["[('id','=',4)]", "{'default_partner_id':4}"]:
            self.assertTrue(self.scan(expression, 'ir_act_window', 'context'))
        self.assertTrue(self.scan('''<form><field name="partner_id" domain="[('id','=',4)]"/></form>'''))

    def test_qweb_lookup_and_inline_template_are_blocked(self):
        self.assertTrue(self.scan('''<div><t t-out="env['res.partner'].browse(4).name"/></div>''', 'mail_template', 'body_html'))
        self.assertTrue(self.scan("<p>{{ object.env['res.partner'].browse(4).name }}</p>", 'mail_template', 'body_html'))

    def test_record_links_without_model_marker_are_blocked(self):
        for link in ['/web/image/4', '/web#id=4&amp;model=res.partner', '/odoo/4']:
            self.assertTrue(self.scan('<a href="' + link + '">Record</a>', 'mail_template', 'body_html'))

    def test_translations_and_diagnostics(self):
        findings = self.scan({'en_US':'<form/>','ar_001':'''<form context="{'default_partner_id':4}"/>'''})
        self.assertEqual(findings[0]['language'], 'ar_001')
        self.assertEqual(findings[0]['candidate_ids'], [4])
        self.assertEqual(findings[0]['location'], '/form/@context')

    def test_malformed_view_is_blocked(self):
        self.assertIn('Malformed XML', self.scan('<form')[0]['reason'])

    def test_unmoved_ids_do_not_block(self):
        self.assertEqual(self.scan('''<form context="{'default_partner_id':999}"/>'''), [])

    def test_generic_json_retains_conservative_check(self):
        self.assertTrue(self.scan({'key': 'res.partner,4'}, 'custom_table', 'payload'))

    def test_flags_alongside_dynamic_references_are_unchanged(self):
        for context in ["{'is_modal':1, 'default_model_id':model_id}",
                        "{'group_by':'employee_id','search_default_group_employee_id':1}",
                        "{'search_default_partner_id':partner_id,'search_default_filter':1}"]:
            self.assertEqual(self.scan(context, 'ir_act_window', 'context'), [])
        self.assertEqual(self.scan("[(not not partner_id,'=',1),('partner_id','=',partner_id)]", 'ir_rule','domain_force'), [])
        self.assertEqual(self.scan('<a t-attf-href="{{attachment.get_base_url()}}/web/content/{{attachment.id}}?download=1">Download</a>'), [])

    def test_search_default_record_and_comparison_are_blocked(self):
        self.assertTrue(self.scan("{'search_default_partner_id':4}", 'ir_act_window', 'context'))
        self.assertTrue(self.scan('<form invisible="company_id == 4"/>'))

    def test_generic_json_numeric_reference_is_blocked(self):
        self.assertTrue(self.scan({'partner_id':4}, 'custom_table', 'payload'))
