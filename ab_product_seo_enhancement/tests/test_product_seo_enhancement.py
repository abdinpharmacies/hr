from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestProductSeoEnhancement(TransactionCase):

    def setUp(self):
        super().setUp()
        self.assistant = self.env["ab.seo.assistant"].create({
            "name": "SEO Enhancement Test Assistant",
            "provider": "openai",
            "assistant_type": "ai",
            "model_name": "gpt-4.1-mini",
            "base_url": "https://api.openai.com/v1",
            "endpoint_path": "/chat/completions",
            "api_key": "test-key",
        })

    def _bundle(self, name, **values):
        context = {
            "product_name": name,
            "product_code": values.get("product_code", "TEST"),
            "barcodes": values.get("barcodes", "123456"),
            "manufacturer": values.get("manufacturer", "Test Manufacturer"),
            "category_path": values.get("category_path", ""),
            "scientific_name": values.get("scientific_name", ""),
            "scientific_group": values.get("scientific_group", ""),
            "effective_material": values.get("effective_material", ""),
            "effective_material_conc": values.get("effective_material_conc", ""),
            "usage_manner": values.get("usage_manner", ""),
            "origin": values.get("origin", "Egypt"),
            "is_medicine": values.get("is_medicine", False),
            "existing_descriptions": values.get("existing_descriptions", {}),
            "existing_seo": values.get("existing_seo", {}),
        }
        return self.assistant._build_product_source_bundle(name, product_context=context)

    def test_panadol_classifies_as_medicine(self):
        bundle = self._bundle(
            "Panadol Extra",
            is_medicine=True,
            category_path="Medicines / Pain Relief",
            scientific_name="Paracetamol",
            effective_material="Paracetamol",
            usage_manner="Orally",
        )

        classification = bundle["classification"]

        self.assertEqual(classification["classification"], "medicine")
        self.assertGreaterEqual(classification["classification_confidence"], 0.70)

    def test_augmentin_classifies_as_medicine(self):
        bundle = self._bundle(
            "Augmentin 1g Tablets",
            is_medicine=True,
            category_path="Medicines / Antibiotics",
            scientific_name="Amoxicillin Clavulanate",
            effective_material="Amoxicillin + Clavulanic Acid",
            usage_manner="Orally",
        )

        self.assertEqual(bundle["classification"]["classification"], "medicine")

    def test_dove_powder_stick_classifies_as_cosmetic_or_personal_care(self):
        bundle = self._bundle(
            "Dove Powder Stick 74g",
            category_path="Beauty / Deodorant / Personal Care",
            existing_descriptions={"description": "Deodorant stick for daily freshness."},
        )

        self.assertIn(bundle["classification"]["classification"], ("cosmetic", "personal_care"))
        self.assertGreaterEqual(bundle["classification"]["classification_confidence"], 0.50)

    def test_cetaphil_cleanser_classifies_as_cosmetic_or_personal_care(self):
        bundle = self._bundle(
            "Cetaphil Cleanser",
            category_path="Skin Care / Cleanser",
            existing_descriptions={"description": "Gentle skin cleanser."},
        )

        self.assertIn(bundle["classification"]["classification"], ("cosmetic", "personal_care"))

    def test_jean_paul_gaultier_perfume_uses_formatted_description_template(self):
        product_name = "JEAN PAUL GAULTIER EAU DE PARFUM 125 ML 1 BOX, 1 UNIT"
        bundle = self._bundle(
            product_name,
            category_path="Fragrance / Eau de Parfum",
            manufacturer="Jean Paul Gaultier",
        )
        bad_json_description = (
            '{{ "meta_title": "%s", "meta_description": "", "keywords": "", "slug": "", '
            '"short_description": "", "public_description": "", "active_ingredient": "", '
            '"warnings": "", "contraindications": "", "storage": ""}'
        ) % product_name
        content = {
            "meta_title": product_name,
            "meta_description": "",
            "keyword_text": "",
            "seo_name": "",
            "short_description": "",
            "public_description": bad_json_description,
            "drug_data": {},
        }

        sanitized = self.assistant._sanitize_generated_product_content(content, bundle)

        self.assertEqual(sanitized["classification"], "cosmetic")
        self.assertIn("fragrance product", sanitized["meta_description"])
        self.assertTrue(sanitized["public_description"].startswith("<p>"))
        self.assertIn("fragrance product", sanitized["public_description"])
        self.assertNotIn('"meta_title"', sanitized["public_description"])
        self.assertNotIn("{{", sanitized["public_description"])

    def test_malformed_json_wrapped_in_html_is_replaced_before_ecommerce_write(self):
        product_name = "ABOUT YOU MOISTURISING CREAM 75 GM 1 BOX"
        product_card = self.env["ab_product_card"].create({
            "name": product_name,
            "description": "",
            "is_medicine": False,
        })
        product = self.env["ab_product"].create({
            "product_card_id": product_card.id,
            "code": "ABOUT-YOU-75",
            "default_price": 10.0,
            "allow_sale": True,
        })
        template = self.env["product.template"].create({
            "name": product_name,
            "ab_product_id": product.id,
            "sale_ok": True,
            "is_published": True,
        })
        bulk = self.env["ab.product.seo.bulk.optimization"].create({
            "name": "Malformed JSON Write Guard",
            "assistant_id": self.assistant.id,
            "lang_mode": "en_US",
            "publish_description": True,
        })
        malformed = '<p>{{"meta_title":"كريم مرطب أباوت يو 75 جم | ترطيب ون}</p>'
        content = {
            "meta_title": product_name,
            "meta_description": "",
            "keyword_text": "",
            "seo_name": "",
            "short_description": malformed,
            "public_description": malformed,
            "drug_data": {},
        }

        bulk._write_native_product_seo(template, content, "en_US")

        self.assertTrue(template.description_ecommerce)
        self.assertIn("personal care product", template.description_ecommerce)
        self.assertNotIn("{{", template.description_ecommerce)
        self.assertNotIn('"meta_title"', template.description_ecommerce)
        if "website_description" in template._fields:
            self.assertFalse(template.website_description)

    def test_generated_description_is_not_written_to_website_description(self):
        product_name = "DUPLICATE CONTENT CREAM 75 GM"
        product_card = self.env["ab_product_card"].create({
            "name": product_name,
            "description": "",
            "is_medicine": False,
        })
        product = self.env["ab_product"].create({
            "product_card_id": product_card.id,
            "code": "DUP-CREAM-75",
            "default_price": 10.0,
            "allow_sale": True,
        })
        template = self.env["product.template"].create({
            "name": product_name,
            "ab_product_id": product.id,
            "sale_ok": True,
            "is_published": True,
        })
        public_description = "<p>Generated ecommerce description.</p>"
        if "website_description" in template._fields:
            template.website_description = public_description
        bulk = self.env["ab.product.seo.bulk.optimization"].create({
            "name": "Duplicate Description Guard",
            "assistant_id": self.assistant.id,
            "lang_mode": "en_US",
            "publish_description": True,
        })

        bulk._write_native_product_seo(template, {
            "meta_title": product_name,
            "meta_description": "Generated ecommerce description.",
            "keyword_text": "cream",
            "seo_name": "duplicate-content-cream-75-gm",
            "short_description": "Generated ecommerce description.",
            "public_description": public_description,
            "drug_data": {},
        }, "en_US")

        self.assertEqual(template.description_ecommerce, public_description)
        if "website_description" in template._fields:
            self.assertFalse(template.website_description)

    def test_accu_chek_classifies_as_medical_device(self):
        bundle = self._bundle(
            "Accu-Chek Active Device",
            category_path="Medical Devices / Blood Glucose Meter",
            existing_descriptions={"description": "Blood glucose monitoring device."},
        )

        self.assertEqual(bundle["classification"]["classification"], "medical_device")

    def test_generic_product_falls_back_to_general_product(self):
        bundle = self._bundle(
            "Abdin Gift Bag",
            category_path="General Merchandise",
            manufacturer="",
            barcodes="",
        )

        self.assertEqual(bundle["classification"]["classification"], "general_product")
        self.assertIn("manufacturer missing", bundle["missing_information"])
        self.assertIn("barcode missing", bundle["missing_information"])

    def test_source_bundle_contains_trusted_facts_and_existing_seo(self):
        bundle = self._bundle(
            "Dove Powder Stick 74g",
            product_code="DOVE-74",
            barcodes="622000001",
            manufacturer="Dove",
            category_path="Beauty / Deodorant",
            existing_seo={
                "website_meta_title": "Old Dove Title",
                "website_meta_description": "Old Dove Description",
            },
        )

        facts = bundle["trusted_facts"]

        self.assertEqual(facts["product_name"], "Dove Powder Stick 74g")
        self.assertEqual(facts["product_code"], "DOVE-74")
        self.assertEqual(facts["manufacturer"], "Dove")
        self.assertEqual(bundle["existing_seo"]["website_meta_title"], "Old Dove Title")

    def test_prompt_selection_uses_classification_variant(self):
        cosmetic_prompt = self.assistant._build_ai_product_prompt(
            "Dove Powder Stick 74g",
            "en_US",
            product_context={
                "product_name": "Dove Powder Stick 74g",
                "category_path": "Beauty / Deodorant",
                "manufacturer": "Dove",
            },
        )
        medicine_prompt = self.assistant._build_ai_product_prompt(
            "Panadol Extra",
            "en_US",
            product_context={
                "product_name": "Panadol Extra",
                "is_medicine": True,
                "scientific_name": "Paracetamol",
                "effective_material": "Paracetamol",
                "category_path": "Medicine / Pain Relief",
                "manufacturer": "GSK",
            },
        )

        self.assertIn("Cosmetic rules", cosmetic_prompt)
        self.assertIn("Medicine rules", medicine_prompt)

    def test_sanitization_strips_unsupported_medical_facts_and_preserves_metadata(self):
        bundle = self._bundle(
            "Panadol Extra",
            is_medicine=True,
            category_path="Medicines / Pain Relief",
            scientific_name="Paracetamol",
            effective_material="Paracetamol",
            manufacturer="GSK",
        )
        content = {
            "meta_title": "Panadol Extra",
            "meta_description": "Pain relief product information.",
            "keyword_text": "panadol, pain relief",
            "seo_name": "panadol-extra",
            "short_description": "Pain relief product information.",
            "public_description": "<p>Panadol Extra helps treat pain and fever.</p>",
            "active_ingredient": "Invented Ingredient",
            "warnings": "Invented warning",
            "contraindications": "Invented contraindication",
            "storage": "Invented storage",
            "drug_data": {
                "side_effects": "Invented side effect",
                "common_uses": "Invented use",
            },
            "review_required": False,
            "missing_information": ["test missing"],
            "confidence_score": 0.91,
        }

        sanitized = self.assistant._sanitize_generated_product_content(content, bundle)

        self.assertEqual(sanitized["active_ingredient"], "Paracetamol")
        self.assertFalse(sanitized["warnings"])
        self.assertFalse(sanitized["contraindications"])
        self.assertFalse(sanitized["storage"])
        self.assertEqual(sanitized["drug_data"]["active_ingredient"], "Paracetamol")
        self.assertNotIn("side_effects", sanitized["drug_data"])
        self.assertTrue(sanitized["review_required"])
        self.assertIn("test missing", sanitized["missing_information"])
        self.assertEqual(sanitized["classification"], "medicine")
        self.assertEqual(sanitized["confidence_score"], 0.91)

    def test_backward_compatible_schema_keys_survive(self):
        bundle = self._bundle(
            "Generic Product",
            category_path="General Merchandise",
            manufacturer="Abdin",
        )
        content = {
            "meta_title": "Generic Product",
            "meta_description": "Generic product information.",
            "keyword_text": "generic",
            "seo_name": "generic-product",
            "short_description": "Generic product information.",
            "public_description": "<p>Generic product information.</p>",
            "drug_data": {},
        }

        sanitized = self.assistant._sanitize_generated_product_content(content, bundle)

        for key in (
            "meta_title",
            "meta_description",
            "keyword_text",
            "seo_name",
            "short_description",
            "public_description",
            "active_ingredient",
            "warnings",
            "contraindications",
            "storage",
            "drug_data",
        ):
            self.assertIn(key, sanitized)
        self.assertIn("review_required", sanitized)
        self.assertIn("missing_information", sanitized)
        self.assertIn("confidence_score", sanitized)
