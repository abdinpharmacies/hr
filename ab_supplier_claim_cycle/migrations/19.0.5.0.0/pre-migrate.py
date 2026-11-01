import json
import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def parse_amount(value):
    text = str(value or '').strip()
    if not re.fullmatch(r'[+]?\d+(?:\.\d+)?|[+]?\d{1,3}(?:,\d{3})+(?:\.\d+)?', text):
        raise ValueError('Invalid amount')
    try:
        amount = Decimal(text.replace(',', '')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except InvalidOperation:
        raise ValueError('Invalid amount') from None
    if not amount.is_finite() or amount <= 0:
        raise ValueError('Invalid amount')
    return amount


def migrate(cr, version):
    cr.execute('SELECT id, amount_of_check FROM ab_supplier_claim_cycle ORDER BY id')
    values = []
    invalid = []
    for claim_id, raw in cr.fetchall():
        try:
            values.append((parse_amount(raw), claim_id))
        except ValueError:
            invalid.append(claim_id)
    if invalid:
        raise ValueError('Supplier claim migration stopped: invalid claim amounts for IDs %s. Original values remain unchanged.' % invalid)
    cr.execute('SELECT id FROM res_company WHERE active ORDER BY id')
    companies = [row[0] for row in cr.fetchall()]
    assignments = []
    if len(companies) == 1:
        assignments = [(companies[0], claim_id) for amount, claim_id in values]
    else:
        cr.execute('SELECT value FROM ir_config_parameter WHERE key=%s', ['ab_supplier_claim_cycle.migration_company_map'])
        row = cr.fetchone()
        mapping = json.loads(row[0]) if row else {}
        for amount, claim_id in values:
            xmlid = mapping.get(str(claim_id), '')
            module, separator, name = xmlid.partition('.')
            if not separator:
                raise ValueError('Legacy claim %s requires an explicit company XML ID in ab_supplier_claim_cycle.migration_company_map' % claim_id)
            cr.execute('SELECT res_id FROM ir_model_data WHERE module=%s AND name=%s AND model=%s', [module, name, 'res.company'])
            company = cr.fetchone()
            if not company or company[0] not in companies:
                raise ValueError('Invalid company XML ID for legacy claim %s' % claim_id)
            assignments.append((company[0], claim_id))
    cr.execute('ALTER TABLE ab_supplier_claim_cycle ADD COLUMN IF NOT EXISTS company_id integer')
    cr.executemany('UPDATE ab_supplier_claim_cycle SET company_id=%s WHERE id=%s', assignments)
    cr.execute('ALTER TABLE ab_supplier_claim_cycle ADD COLUMN IF NOT EXISTS claim_amount double precision')
    cr.executemany('UPDATE ab_supplier_claim_cycle SET claim_amount=%s WHERE id=%s', values)
    cr.execute('ALTER TABLE ab_supplier_claim_cycle ADD COLUMN IF NOT EXISTS supplier_cheque_attachment bytea')
    cr.execute('ALTER TABLE ab_supplier_claim_cycle ADD COLUMN IF NOT EXISTS supplier_cheque_filename varchar')
    cr.execute('UPDATE ab_supplier_claim_cycle SET supplier_cheque_attachment=cheque_attachment, supplier_cheque_filename=cheque_filename')
    cr.execute('SELECT id FROM ab_supplier_claim_cycle WHERE supplier_cheque_attachment IS DISTINCT FROM cheque_attachment OR supplier_cheque_filename IS DISTINCT FROM cheque_filename')
    if cr.fetchall():
        raise ValueError('Supplier claim attachment migration verification failed')
