#
# #################################################################################################
# # ###################### TRANSFER OLD DATA ######################################################
# #################################################################################################
# def insert_je(self):
#     cr = self.env.cr
#     cr.execute("select max(old_je_serial) from ab_accounting_je_line")
#     last_accid = cr.fetchone()
#     last_accid = last_accid and last_accid[0] or 0
#     sql = """
#         select
#             abg2.id as with_account,
#             abg.id as account_id,
#             q.credit_val,
#             q.debit_val,
#             q.net_val,
#             q.due_date,
#             q.settlement_date,
#             q.final_date,
#             q.doc_no,
#             absto.id as store_id,
#             abco.id as costcenter_id,
#             q.accid,
#             q.explain::varchar,
#             q.create_date,
#             q.write_date,
#             q.create_uid,
#             q.write_uid
#         from abdin_gl_qryje q
#         left join abdin_gl_tblaccguide g on g.id = q.on_account
#         left join ab_accounting_account_guide abg on g.level_code = abg.code
#
#         left join abdin_gl_tblaccguide g2 on g2.id = q.with_account
#         left join ab_accounting_account_guide abg2 on g2.level_code = abg2.code
#
#         left join abdin_gl_tblbranch br on br.id = q.branch_id
#         left join ab_store absto on  absto.code::integer = br.id
#
#         left join abdin_gl_tblcostcenters co on co.id = q.cost_center
#         left join ab_costcenter abco on abco.code = co.accid
#         where q.active=True and q.accid>%s and from_server=true
#         group by abg2.id, abg.id, q.credit_val, q.debit_val, q.net_val,
#         q.due_date, q.settlement_date,q.final_date, q.doc_no,
#         absto.id, abco.id, q.accid,q.explain, q.create_date, q.write_date, q.create_uid, q.write_uid
#         order by with_account
#             """
#     cr.execute(sql, (last_accid,))
#     # cr.execute(sql)
#     rows = cr.fetchall()
#     x = 10000
#     i = 0
#     start = perf_counter()
#     with_account = None
#     header_id = 0
#
#     for row in rows:
#         if not row[0] == with_account:
#             header_id = self.env['ab_accounting_je_header'].create(
#                 {'is_posted': True, 'active': False, 'account_id': row[0],
#                  'doctype_id': 7}).id
#             self.env.cr.commit()
#         with_account = row[0]
#         row = row[1:] + (header_id,)
#         i += 1
#         if i % x == 0:
#             cr.commit()
#         sql = """
#         INSERT INTO ab_accounting_je_line(
#             account_id,
#             credit_val,
#             debit_val,
#             net_val,
#             due_date,
#             settlement_date,
#             final_date,
#             doc_no,
#             store_id,
#             costcenter_id,
#             old_je_serial,
#             explain,
#             create_date,
#             write_date,
#             create_uid,
#             write_uid,
#             header_id,
#             active,
#             is_confirmed
#             )
#         VALUES({},True,True)
#         """.format(",".join(["%s"] * len(row)))
#         cr.execute(sql, row)
#
#
# def update_je(self):
#     cr = self.env.cr
#     sql = """
#         UPDATE ab_accounting_je_line abje
#         SET
#             account_id=qry.account_id,
#             credit_val=qry.credit_val,
#             debit_val=qry.debit_val,
#             net_val=qry.debit_val-qry.credit_val,
#             due_date=qry.due_date,
#             settlement_date=qry.settlement_date,
#             doc_no=qry.doc_no,
#             store_id=qry.store_id,
#             costcenter_id=qry.costcenter_id,
#             old_je_serial=qry.accid,
#             explain=qry.explain,
#             write_date=qry.write_date
#         FROM  ( select
#             abg2.id as with_account,
#             abg.id as account_id,
#             q.credit_val,
#             q.debit_val,
#             q.due_date,
#             q.settlement_date,
#             q.doc_no,
#             absto.id as store_id,
#             abco.id as costcenter_id,
#             q.accid,
#             q.explain::varchar,
#             q.create_date,
#             q.write_date,
#             q.create_uid,
#             q.write_uid
#         from abdin_gl_qryje q
#         left join abdin_gl_tblaccguide g on g.id = q.on_account
#         left join ab_accounting_account_guide abg on g.level_code = abg.code
#
#         left join abdin_gl_tblaccguide g2 on g2.id = q.with_account
#         left join ab_accounting_account_guide abg2 on g2.level_code = abg2.code
#
#         left join abdin_gl_tblbranch br on br.id = q.branch_id
#         left join ab_store absto on  absto.code::integer = br.id
#
#         left join abdin_gl_tblcostcenters co on co.id = q.cost_center
#         left join ab_costcenter abco on abco.code = co.accid
#         where q.active=True and q.accid>0) as qry
#         WHERE  qry.accid= abje.old_je_serial and qry.account_id=abje.account_id
#             """
#     cr.execute(sql)
#
#
# def delete_duplicated_je(self):
#     self.env.cr.execute("""
#             DELETE FROM ab_accounting_je_line a USING (
#           SELECT MIN(id) as ctid, old_je_serial,account_id
#             FROM ab_accounting_je_line
#             GROUP BY old_je_serial,account_id HAVING COUNT(*) > 1
#           ) b
#           WHERE
#           a.old_je_serial = b.old_je_serial
#           and a.account_id = b.account_id
#           AND a.id <> b.ctid
#
#     """
#                         )
