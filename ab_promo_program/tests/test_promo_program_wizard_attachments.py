import base64

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestPromoProgramWizardAttachments(TransactionCase):
    def setUp(self):
        super().setUp()
        self.company = self.env['ab_costcenter'].create({
            'name': 'Wizard Compensation Company',
            'code': '1-WIZ-ATT',
        })
        self.product_1 = self._create_product('WIZ-ATT-001')
        self.product_2 = self._create_product('WIZ-ATT-002')

    def _create_product(self, code):
        card = self.env['ab_product_card'].create({'name': code})
        return self.env['ab_product'].create({
            'product_card_id': card.id,
            'code': code,
        })

    def _attachment(self, name, content):
        return self.env['ir.attachment'].create({
            'name': name,
            'datas': base64.b64encode(content),
        })

    @staticmethod
    def _paste_text(rows, include_attachment_header=True):
        headers = [
            'name',
            'product_code',
            'promo_text',
            'rule_date_from',
            'rule_date_to',
            'Compensation Way',
            'Compensation Type',
            'promotion_ownership',
            'Compensation Company',
        ]
        if include_attachment_header:
            headers.append('Approval Attachment File Name')
        return '\n'.join(['\t'.join(headers)] + ['\t'.join(row) for row in rows])

    def _row(self, name, product_code, filename=None):
        row = [
            name,
            product_code,
            '10%',
            '',
            '',
            'Before',
            'Cash',
            'Other Promotion',
            self.company.code,
        ]
        if filename is not None:
            row.append(filename)
        return row

    def test_import_without_attachment_column_or_uploads(self):
        wizard = self.env['ab_promo_program_wizard'].create({
            'from_excel': self._paste_text(
                [self._row('No Attachment Promo', self.product_1.code, filename=None)],
                include_attachment_header=False,
            ),
        })

        wizard.btn_add_promos()

        promo = self.env['ab_promo_program'].search([
            ('name', '=', 'No Attachment Promo'),
        ])
        self.assertEqual(len(promo), 1)
        self.assertFalse(promo.approval_email_attachment)
        self.assertFalse(promo.approval_email_attachment_filename)

    def test_blank_filename_ignores_unused_uploads(self):
        unused_1 = self._attachment('unused.pdf', b'unused')
        unused_2 = self._attachment('UNUSED.PDF', b'also-unused')
        wizard = self.env['ab_promo_program_wizard'].create({
            'from_excel': self._paste_text([
                self._row('Blank Attachment Promo', self.product_1.code, ''),
            ]),
            'approval_attachment_ids': [
                (6, 0, [unused_1.id, unused_2.id]),
            ],
        })

        wizard.btn_add_promos()

        promo = self.env['ab_promo_program'].search([
            ('name', '=', 'Blank Attachment Promo'),
        ])
        self.assertEqual(len(promo), 1)
        self.assertFalse(promo.approval_email_attachment)

    def test_case_insensitive_matching_and_different_files_split_promos(self):
        pdf_attachment = self._attachment('Approval_1.PDF', b'pdf-content')
        image_attachment = self._attachment('approval_2.jpg', b'image-content')
        wizard = self.env['ab_promo_program_wizard'].create({
            'from_excel': self._paste_text([
                self._row('Attached Promo', self.product_1.code, ' approval_1.pdf '),
                self._row('Attached Promo', self.product_2.code, 'APPROVAL_2.JPG'),
            ]),
            'approval_attachment_ids': [
                (6, 0, [pdf_attachment.id, image_attachment.id]),
            ],
        })

        wizard.btn_add_promos()

        promos = self.env['ab_promo_program'].search([
            ('name', '=', 'Attached Promo'),
        ])
        self.assertEqual(len(promos), 2)
        promos_by_filename = {
            promo.approval_email_attachment_filename: promo
            for promo in promos
        }
        self.assertEqual(
            promos_by_filename['Approval_1.PDF'].approval_email_attachment,
            pdf_attachment.datas,
        )
        self.assertEqual(
            promos_by_filename['approval_2.jpg'].approval_email_attachment,
            image_attachment.datas,
        )

    def test_missing_referenced_attachment_is_rejected(self):
        wizard = self.env['ab_promo_program_wizard'].create({
            'from_excel': self._paste_text([
                self._row('Missing Attachment Promo', self.product_1.code, 'missing.pdf'),
            ]),
        })

        with self.assertRaisesRegex(UserError, 'missing.pdf'):
            wizard.btn_add_promos()

        self.assertFalse(self.env['ab_promo_program'].search([
            ('name', '=', 'Missing Attachment Promo'),
        ]))

    def test_ambiguous_uploaded_filename_is_rejected_when_referenced(self):
        attachment_1 = self._attachment('duplicate.pdf', b'first')
        attachment_2 = self._attachment('DUPLICATE.PDF', b'second')
        wizard = self.env['ab_promo_program_wizard'].create({
            'from_excel': self._paste_text([
                self._row('Ambiguous Attachment Promo', self.product_1.code, 'duplicate.pdf'),
            ]),
            'approval_attachment_ids': [
                (6, 0, [attachment_1.id, attachment_2.id]),
            ],
        })

        with self.assertRaisesRegex(UserError, 'multiple uploaded attachments'):
            wizard.btn_add_promos()
