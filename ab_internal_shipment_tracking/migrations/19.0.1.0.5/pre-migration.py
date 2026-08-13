def migrate(cr, version):
    cr.execute(
        """
        SELECT res_id
          FROM ir_model_data
         WHERE module = 'base'
           AND name = 'group_user'
           AND model = 'res.groups'
         LIMIT 1
        """
    )
    row = cr.fetchone()
    if not row:
        return
    internal_group_id = row[0]

    cr.execute(
        """
        SELECT res_id
          FROM ir_model_data
         WHERE module = 'ab_internal_shipment_tracking'
           AND name = 'group_ab_internal_shipment_user'
           AND model = 'res.groups'
         LIMIT 1
        """
    )
    row = cr.fetchone()
    if not row:
        return
    shipment_group_id = row[0]

    cr.execute(
        """
        INSERT INTO res_groups_users_rel (uid, gid)
        SELECT internal_rel.uid, %s
          FROM res_groups_users_rel internal_rel
         WHERE internal_rel.gid = %s
           AND NOT EXISTS (
                SELECT 1
                  FROM res_groups_users_rel shipment_rel
                 WHERE shipment_rel.uid = internal_rel.uid
                   AND shipment_rel.gid = %s
           )
        """,
        (shipment_group_id, internal_group_id, shipment_group_id),
    )
