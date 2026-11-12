from unittest.mock import MagicMock, patch

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from ..models.ab_eplus_connect import ConnectionProxy, EPlusConnect, EplusConnectionError


@tagged("post_install", "-at_install")
class TestEplusDisconnectedConnection(TransactionCase):
    def test_probe_timeout_is_retryable_only_when_requested(self):
        connector = self.env["ab_eplus_connect"]
        with patch("odoo.addons.ab_eplus_connect.models.ab_eplus_connect.threading.Thread") as thread:
            thread.return_value.is_alive.return_value = True
            self.assertFalse(connector.is_connection_valid(None, server="test", max_seconds=5))
            with self.assertRaises(EplusConnectionError):
                connector.is_connection_valid(None, server="test", max_seconds=5, retryable_validation=True)

    def test_probe_reports_network_failure_but_does_not_retry_login_rejection(self):
        connector = self.env["ab_eplus_connect"]
        args = ("test", "test", "test", "test", "%s", "CP1256", 1433, 5)
        with patch("odoo.addons.ab_eplus_connect.models.ab_eplus_connect.pymssql") as driver:
            driver.connect.side_effect = RuntimeError(20009, "connection timed out")
            with self.assertRaises(EplusConnectionError):
                connector._probe_connection(*args, retryable_validation=True)
            driver.connect.side_effect = RuntimeError(18456, "login failed")
            self.assertFalse(connector._probe_connection(*args, retryable_validation=True))

    def test_threaded_probe_propagates_retryable_network_failure(self):
        connector = self.env["ab_eplus_connect"]
        with patch.object(type(connector), "_probe_connection", side_effect=EplusConnectionError("offline")):
            with self.assertRaises(EplusConnectionError):
                connector.is_connection_valid(None, server="test", max_seconds=5, retryable_validation=True)

    def test_read_connection_retries_transient_open_failure(self):
        connector = self.env["ab_eplus_connect"]
        failed = MagicMock()
        failed.__enter__.side_effect = EplusConnectionError("offline")
        working = MagicMock()
        with (
            patch.object(type(connector), "connect_eplus", side_effect=[failed, working]) as connect,
            patch("odoo.addons.ab_eplus_connect.models.ab_eplus_connect.time.sleep") as sleep,
        ):
            with connector._connect_eplus_read() as connection:
                self.assertEqual(connection, working.__enter__.return_value)
            self.assertEqual(connect.call_count, 2)
            self.assertFalse(connect.call_args.kwargs["use_validation_cache"])
            self.assertEqual(connect.call_args.kwargs["port_timeout"], 5)
            sleep.assert_called_once_with(1)
        working.__exit__.assert_called_once()

    def test_read_connection_stops_after_three_open_attempts(self):
        connector = self.env["ab_eplus_connect"]
        with (
            patch.object(type(connector), "connect_eplus", side_effect=EplusConnectionError("offline")) as connect,
            patch("odoo.addons.ab_eplus_connect.models.ab_eplus_connect.time.sleep") as sleep,
        ):
            with self.assertRaises(EplusConnectionError):
                with connector._connect_eplus_read():
                    self.fail("The connection should not open")
            self.assertEqual(connect.call_count, 3)
            self.assertEqual(sleep.call_count, 2)

    def test_read_connection_does_not_retry_permission_or_configuration_errors(self):
        connector = self.env["ab_eplus_connect"]
        for error in [AccessError("denied"), UserError("invalid configuration")]:
            with patch.object(type(connector), "connect_eplus", side_effect=error) as connect:
                with self.assertRaises(type(error)):
                    with connector._connect_eplus_read():
                        self.fail("The connection should not open")
                connect.assert_called_once()

    def test_read_connection_does_not_replay_a_started_operation(self):
        connector = self.env["ab_eplus_connect"]
        with patch.object(type(connector), "connect_eplus", return_value=MagicMock()) as connect:
            with self.assertRaises(EplusConnectionError):
                with connector._connect_eplus_read():
                    raise EplusConnectionError("disconnected after query started")
            connect.assert_called_once()

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
