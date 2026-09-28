"""Preserve legacy references before the ORM creates the new supplier relation."""
from psycopg2 import sql

from odoo.exceptions import ValidationError


def migrate(cr, version):
    # Legacy schema rollbacks can leave newer supplier IDs under a cost-center
    # foreign key. Keep raw values until post-migration can consult audit history.
    cr.execute("""
        SELECT c.conname, c.confrelid = 'ab_costcenter'::regclass
          FROM pg_constraint c
          JOIN pg_attribute a ON a.attrelid = c.conrelid
                             AND c.conkey = ARRAY[a.attnum]::smallint[]
         WHERE c.conrelid = 'ab_supplier_claim_cycle'::regclass
           AND c.contype = 'f' AND a.attname = 'supplier_id'
    """)
    constraints = cr.fetchall()
    if not any(is_legacy for _, is_legacy in constraints):
        return
    cr.execute('LOCK TABLE ab_supplier_claim_cycle IN ACCESS EXCLUSIVE MODE')
    cr.execute("""
        SELECT attname FROM pg_attribute
         WHERE attrelid = 'ab_supplier_claim_cycle'::regclass
           AND attnum > 0 AND NOT attisdropped
    """)
    columns = {row[0] for row in cr.fetchall()}
    if 'status' not in columns or 'state' in columns or 'legacy_supplier_reference_id' in columns:
        raise ValidationError('Unexpected legacy claim schema; supplier recovery stopped without changing records.')
    for name, _ in constraints:
        cr.execute(sql.SQL('ALTER TABLE ab_supplier_claim_cycle DROP CONSTRAINT {}').format(sql.Identifier(name)))
    cr.execute('ALTER TABLE ab_supplier_claim_cycle RENAME COLUMN supplier_id TO legacy_supplier_reference_id')
    cr.execute('ALTER TABLE ab_supplier_claim_cycle ALTER COLUMN legacy_supplier_reference_id DROP NOT NULL')
    cr.execute('ALTER TABLE ab_supplier_claim_cycle ALTER COLUMN status DROP NOT NULL')
    cr.execute('ALTER TABLE ab_supplier_claim_cycle ADD COLUMN legacy_supplier_reference_model varchar')
    cr.execute('ALTER TABLE ab_supplier_claim_cycle ADD COLUMN legacy_claim_recovered boolean DEFAULT false')
    # Odoo creates the new supplier FK; post-migration fills it and enforces
    # NOT NULL before this same upgrade transaction can commit.
