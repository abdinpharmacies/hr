def migrate(cr, version):
    cr.execute(
        """
        UPDATE ab_supplier_claim_cycle
           SET payment_nature = 'bank_transfer'
         WHERE payment_nature = 'non_cash'
        """
    )
