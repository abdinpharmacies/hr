from odoo import api, fields, models

from ..services.legacy_csv import CORRECTED_CODES, INFO_CODES


ISSUE_REASONS = [
    ('empty_file', 'The file is empty.'),
    ('invalid_header', 'The header cannot be read. Use one header row and a supported delimiter.'),
    ('duplicate_header', 'The column name is empty or appears more than once.'),
    ('missing_header', 'A required column is missing.'),
    ('unused_column', 'This column is not used for customer activation; its source data is unchanged.'),
    ('header_normalized', 'Spaces and letter case in the column name were normalized.'),
    ('delimiter_detected', 'The file delimiter was detected automatically.'),
    ('encoding', 'This value contains bytes that cannot be decoded using the selected encoding.'),
    ('quoting', 'Malformed quotation marks: this record is excluded without guessing its customer data.'),
    ('record_boundary', 'This record follows broken quoting and has no reliable customer boundary. It is excluded for manual review.'),
    ('column_count', 'The number of values does not match the header. Original Value shows the actual count; Normalized Value shows the expected count.'),
    ('trailing_empty_columns', 'Extra empty columns at the end of the record were ignored.'),
    ('record_limit', 'A record exceeds 131,072 characters or 32 physical lines. The remaining file was not scanned.'),
    ('row_limit', 'The file exceeds 600,000 records. The remaining file was not scanned.'),
    ('blank_row', 'The empty record was skipped.'),
    ('field_limit', 'The value exceeds the maximum of 4,096 characters.'),
    ('control_character', 'The value contains an unsupported control character.'),
    ('invalid_active', 'Use t/true/1/yes or f/false/0/no for the active flag.'),
    ('inactive', 'The customer is inactive and will not be imported.'),
    ('missing_reference', 'No stable customer reference was provided.'),
    ('invalid_reference', 'The reference must contain 1–80 letters, digits, underscores or hyphens.'),
    ('missing_phone', 'The mobile number is empty.'),
    ('invalid_phone', 'The value is not a valid Egyptian mobile number.'),
    ('scientific_phone', 'The mobile number is in scientific notation. Re-export it as text to preserve its digits.'),
    ('trimmed', 'Leading and trailing spaces were removed.'),
    ('phone_normalized', 'The mobile format was normalized, preserving its digits and restoring an unambiguous leading zero when needed.'),
    ('name_fallback', 'The empty customer name was replaced with the stable reference.'),
    ('name_shortened', 'The customer name was shortened to 200 characters.'),
    ('store_limit', 'The store reference exceeds 80 characters.'),
    ('duplicate_reference', 'This reference appears more than once among active records. All occurrences are excluded.'),
    ('duplicate_phone', 'This mobile number is shared by active records or appears in a damaged record. All candidates using it are excluded.'),
    ('existing_reference', 'This customer reference already exists on the selected website and will be skipped.'),
    ('existing_phone', 'This mobile number already exists on the selected website and will be skipped.'),
    ('file_blocked', 'The file contains ambiguous record boundaries or header errors. Review the issues and upload a corrected file before creating codes.'),
    ('file_unreadable', 'The uploaded file could not be opened. Upload it again.'),
]


class LegacyImportIssue(models.Model):
    _name = 'ab_ecommerce_legacy_import_issue'
    _description = 'Customer Import Validation Issue'
    _order = 'source_row, column_number, id'

    batch_id = fields.Many2one('ab_ecommerce_legacy_batch', required=True, ondelete='restrict', index=True)
    company_id = fields.Many2one(related='batch_id.company_id', store=True, index=True)
    source_row = fields.Integer(string='Source Record', index=True)
    line_start = fields.Integer(string='First File Line')
    line_end = fields.Integer(string='Last File Line')
    column_number = fields.Integer(string='Column Number')
    column_name = fields.Char(string='Column', index=True)
    source_reference = fields.Char(string='Customer Reference')
    original_value = fields.Text(string='Original Value')
    normalized_value = fields.Text(string='Normalized Value')
    issue_code = fields.Selection(ISSUE_REASONS, string='Problem / Reason', required=True, index=True)
    severity = fields.Selection(
        [('error', 'Error'), ('corrected', 'Corrected'), ('info', 'Information')],
        compute='_compute_severity', store=True,
    )
    import_status = fields.Selection([
        ('ready', 'Ready with Corrections'), ('excluded', 'Excluded'),
        ('inactive', 'Inactive'), ('existing', 'Already Exists'),
        ('blocked', 'File Needs Correction'), ('info', 'Information'),
        ('imported', 'Imported'),
    ], string='Import Status', required=True, index=True)

    @api.depends('issue_code')
    def _compute_severity(self):
        for record in self:
            record.severity = 'corrected' if record.issue_code in CORRECTED_CODES else 'info' if record.issue_code in INFO_CODES else 'error'
