import unittest
from datetime import timedelta
from uuid import uuid4

from psycopg2.errors import SerializationFailure

from odoo import SUPERUSER_ID, api, fields, sql_db
from odoo.exceptions import AccessError
from odoo.service.model import retrying


def run(database_name):
    if not database_name.startswith('crm_session_fix_test_'):
        raise ValueError('Run only on a dedicated crm_session_fix_test_ database.')
    connection = sql_db.db_connect(database_name)
    with connection.cursor() as cursor:
        env = api.Environment(cursor, SUPERUSER_ID, {})
        suffix = uuid4().hex
        user = env['res.users'].create({
            'name': 'Session Concurrency Test',
            'login': 'session-concurrency-' + suffix,
            'group_ids': [fields.Command.set([
                env.ref('base.group_user').id,
                env.ref('ab_sales.group_call_center').id,
            ])],
        })
        employee = env['ab_hr_employee'].create({
            'name': 'Session Concurrency Test',
            'barcode': 'session-' + suffix,
            'user_id': user.id,
        })
        profile = env['ab_employee_access'].create({
            'employee_id': employee.id,
            'pos_pin': '1234',
            'pos_use_custom_permissions': True,
            'pos_allow_pos_screen': True,
        })
        chatter = env['ab_crm_chatter_api'].with_user(user)
        token = chatter.employee_login(profile.id, '1234', 'concurrency-test')['token']
        session_id = chatter._session(token).id
        user_id, company_id = user.id, env.company.id
        cursor.commit()

    class SessionConcurrency(unittest.TestCase):
        def setUp(self):
            self.now = fields.Datetime.now()
            self.stale = self.now - timedelta(minutes=2)
            with connection.cursor() as cursor:
                env = api.Environment(cursor, SUPERUSER_ID, {})
                env['ab_crm_chatter_session'].browse(session_id).write({
                    'last_activity_at': self.stale,
                    'state': 'active',
                    'expires_at': self.now + timedelta(hours=8),
                })
                cursor.commit()
            self.first_cursor = connection.cursor()
            self.second_cursor = connection.cursor()
            self.addCleanup(self.first_cursor.close)
            self.addCleanup(self.second_cursor.close)
            context = {'allowed_company_ids': [company_id]}
            self.first = api.Environment(self.first_cursor, user_id, context)
            self.second = api.Environment(self.second_cursor, user_id, context)
            self.first_session = self.first['ab_crm_chatter_session'].sudo().browse(session_id)
            self.second_session = self.second['ab_crm_chatter_session'].sudo().browse(session_id)

        def test_fresh_activity_does_not_lock(self):
            self.first_session.last_activity_at = self.now
            self.first_cursor.commit()
            session = self.first['ab_crm_chatter_api']._session(token)
            self.assertEqual(session.last_activity_at, self.now)
            self.assertTrue(self.second_session.try_lock_for_update(allow_referencing=True))

        def test_overlapping_activity_update_skips_busy_row(self):
            first = self.first['ab_crm_chatter_api']._session(token)
            self.first.flush_all()
            second = self.second['ab_crm_chatter_api']._session(token)
            self.assertEqual(first.id, second.id)
            self.assertGreaterEqual(first.last_activity_at, self.now)
            self.assertEqual(second.last_activity_at, self.stale)
            self.second.flush_all()
            self.second_cursor.execute('SELECT 1')
            self.assertEqual(self.second_cursor.fetchone(), (1,))

        def test_rolled_back_holder_allows_next_activity_update(self):
            self.first['ab_crm_chatter_api']._session(token)
            self.first.flush_all()
            self.assertEqual(
                self.second['ab_crm_chatter_api']._session(token).last_activity_at,
                self.stale,
            )
            self.first_cursor.rollback()
            session = self.second['ab_crm_chatter_api']._session(token)
            self.second.flush_all()
            self.assertGreaterEqual(session.last_activity_at, self.now)

        def test_committed_competitor_skips_activity_without_sql_error(self):
            self.assertEqual(self.second_session.last_activity_at, self.stale)
            self.second['res.users'].sudo().browse(user_id).write({
                'chatter_failed_attempts': 2,
            })
            self.second.flush_all()
            self.first['ab_crm_chatter_api']._session(token)
            self.first_cursor.commit()
            with self.assertNoLogs('odoo.sql_db', level='ERROR'):
                session = self.second['ab_crm_chatter_api']._session(token)
            self.assertEqual(session.id, session_id)
            self.second.flush_all()
            self.second_cursor.execute(
                'SELECT chatter_failed_attempts FROM res_users WHERE id = %s',
                (user_id,),
            )
            self.assertEqual(self.second_cursor.fetchone(), (2,))
            self.second_cursor.commit()

        def test_native_retry_is_not_needed_for_activity_conflict(self):
            self.assertEqual(self.second_session.last_activity_at, self.stale)
            first = self.first['ab_crm_chatter_api']._session(token)
            timestamp = first.last_activity_at
            self.first_cursor.commit()
            attempts = []

            def request():
                attempts.append(True)
                return self.second['ab_crm_chatter_api']._session(token).last_activity_at

            with self.assertNoLogs('odoo.sql_db', level='ERROR'):
                self.assertEqual(retrying(request, self.second), self.stale)
            self.assertEqual(len(attempts), 1)
            self.assertEqual(self.second_session.last_activity_at, timestamp)

        def test_logout_still_retries_after_competing_activity_commit(self):
            self.assertEqual(self.second_session.last_activity_at, self.stale)
            self.first['ab_crm_chatter_api']._session(token)
            self.first_cursor.commit()
            with self.assertRaises(SerializationFailure):
                self.second['ab_crm_chatter_api'].logout(token)
                self.second.flush_all()
            self.second_cursor.rollback()
            self.assertTrue(retrying(
                lambda: self.second['ab_crm_chatter_api'].logout(token), self.second
            ))
            with self.assertRaises(AccessError):
                self.second['ab_crm_chatter_api']._session(token)

        def test_concurrent_logout_preserves_retry_and_rejects_session(self):
            self.assertEqual(self.second_session.last_activity_at, self.stale)
            self.first['ab_crm_chatter_api'].logout(token)
            self.first_cursor.commit()
            with self.assertNoLogs('odoo.sql_db', level='ERROR'):
                with self.assertRaises(SerializationFailure):
                    self.second['ab_crm_chatter_api']._session(token)
            with self.assertRaises(AccessError):
                retrying(
                    lambda: self.second['ab_crm_chatter_api']._session(token),
                    self.second,
                )

        def test_concurrent_expiry_preserves_retry_and_rejects_session(self):
            self.assertEqual(self.second_session.last_activity_at, self.stale)
            self.first_session.expires_at = self.now - timedelta(seconds=1)
            self.first_cursor.commit()
            with self.assertNoLogs('odoo.sql_db', level='ERROR'):
                with self.assertRaises(SerializationFailure):
                    self.second['ab_crm_chatter_api']._session(token)
            with self.assertRaises(AccessError):
                retrying(
                    lambda: self.second['ab_crm_chatter_api']._session(token),
                    self.second,
                )

    try:
        result = unittest.TextTestRunner(verbosity=2).run(
            unittest.defaultTestLoader.loadTestsFromTestCase(SessionConcurrency)
        )
        if not result.wasSuccessful():
            raise AssertionError('Session concurrency validation failed.')
    finally:
        with connection.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, {})
            env['ab_crm_chatter_session'].browse(session_id).write({'state': 'closed'})
            env['ab_employee_access'].browse(profile.id).write({'pos_allow_login': False})
            env['res.users'].browse(user_id).write({'active': False})
            cursor.commit()
