from unittest.mock import MagicMock

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from ..models.ab_eplus_connect import ConnectionProxy, EPlusConnect


@tagged("post_install", "-at_install")
class TestEplusDisconnectedConnection(TransactionCase):
    def test_disconnected_interface_error_is_recognized(self):
        for message in (
            "Not connected to any MS SQL server",
            b"Not connected to any MS SQL server",
        ):
            self.assertTrue(EPlusConnect._is_disconnect_error(RuntimeError(message)))

    def test_disconnected_read_reopens_once(self):
        old = MagicMock()
        new = MagicMock()
        old.cursor.return_value.execute.side_effect = RuntimeError("Not connected to any MS SQL server")
        new.cursor.return_value.execute.return_value = "read completed"
        reopen = MagicMock(return_value=new)
        proxy = ConnectionProxy(old, reopen, EPlusConnect._is_disconnect_error)
        self.assertEqual(proxy.cursor().execute("SELECT 1"), "read completed")
        reopen.assert_called_once_with()
        old.close.assert_called_once_with()
        new.cursor.return_value.execute.assert_called_once_with("SELECT 1")

    def test_failed_retry_is_not_repeated(self):
        old = MagicMock()
        new = MagicMock()
        for connection in (old, new):
            connection.cursor.return_value.execute.side_effect = RuntimeError("Not connected to any MS SQL server")
        reopen = MagicMock(return_value=new)
        proxy = ConnectionProxy(old, reopen, EPlusConnect._is_disconnect_error)
        with self.assertRaisesRegex(RuntimeError, "Not connected"):
            proxy.cursor().execute("SELECT 1")
        reopen.assert_called_once_with()
        new.cursor.return_value.execute.assert_called_once_with("SELECT 1")

    def test_cursor_creation_reopens_disconnected_connection(self):
        old = MagicMock()
        new = MagicMock()
        old.cursor.side_effect = RuntimeError("Not connected to any MS SQL server")
        reopen = MagicMock(return_value=new)
        proxy = ConnectionProxy(old, reopen, EPlusConnect._is_disconnect_error)
        proxy.cursor().execute("SELECT 1")
        reopen.assert_called_once_with()
        new.cursor.return_value.execute.assert_called_once_with("SELECT 1")

    def test_other_query_errors_do_not_reconnect(self):
        old = MagicMock()
        old.cursor.return_value.execute.side_effect = RuntimeError("Invalid column name")
        reopen = MagicMock()
        proxy = ConnectionProxy(old, reopen, EPlusConnect._is_disconnect_error)
        with self.assertRaisesRegex(RuntimeError, "Invalid column"):
            proxy.cursor().execute("SELECT missing_column")
        reopen.assert_not_called()
