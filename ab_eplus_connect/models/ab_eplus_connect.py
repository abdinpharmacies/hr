# -*- coding: utf-8 -*-
import logging
import sys
import time
import threading

from odoo import models, api
from odoo.tools.translate import _
from odoo.exceptions import UserError
from .check_port_mssql import is_port_open
from contextlib import contextmanager
from cryptography.fernet import Fernet
from odoo.tools import config

SERVER = None
try:
    import pymssql

    pymssqlProgrammingError = pymssql.ProgrammingError
except ImportError:
    pymssqlProgrammingError = Exception
    pymssql = None

try:
    import pyodbc

    pyodbcProgrammingError = pyodbc.ProgrammingError
except ImportError:
    pyodbcProgrammingError = Exception
    pyodbc = None


def _get_main_server():
    global SERVER
    if SERVER:
        return SERVER

    conf_bconnect_ips = [config.get('bconnect_ip1'), config.get('bconnect_ip2'), ]
    if not conf_bconnect_ips:
        raise UserError(_("NO IPs in odoo config file."))

    for value in conf_bconnect_ips:
        _logger.info(f"######## Trying IP {value} #########")
        if is_port_open(value, port=1433):
            SERVER = value
            return SERVER
    raise UserError(_("All BConnect Server IPs may be Offline."))


USER = config.get('bconnect_user')
DB = config.get('bconnect_db')
DECRYPTION_KEY = config.get('decryption_key')


def _get_int_config(key, default):
    try:
        val = config.get(key, default)
        if val is None:
            return default
        return int(val)
    except Exception as ex:
        _logger.info(repr(ex))
        return default


DEFAULT_VALIDATE_TIMEOUT = _get_int_config('bconnect_validate_timeout', 3)
DEFAULT_CONNECT_TIMEOUT = _get_int_config('bconnect_connect_timeout', 5)
DEFAULT_VALIDATE_TTL = _get_int_config('bconnect_validate_ttl', 0)
DEFAULT_VALIDATE_FAIL_TTL = _get_int_config('bconnect_validate_fail_ttl', 10)

_logger = logging.getLogger(__name__)


class EPlusConnect(models.AbstractModel):
    _name = 'ab_eplus_connect'
    _description = 'ab_eplus_connect'

    # Connection pool to store connections by user
    _connection_pool = {}
    _connection_health_cache = {}

    @staticmethod
    def is_port_open(host, port=1433, timeout=2):
        return is_port_open(host, port, timeout)

    def decrypt_password(self):
        encrypted_password = bytes(self.env['ir.config_parameter'].sudo().get_param("bconnect_crypt_pass"), 'utf-8')
        cipher = Fernet(bytes(DECRYPTION_KEY, 'utf-8'))
        password = cipher.decrypt(encrypted_password).decode('utf-8')
        return password

    @staticmethod
    def _validate_connection_now(conn, max_seconds):
        ok = False
        start = time.monotonic()
        cursor = None
        prev_conn_timeout = None
        try:
            cursor = conn.cursor()
            if max_seconds and max_seconds > 0:
                if hasattr(conn, "timeout"):
                    try:
                        prev_conn_timeout = conn.timeout
                        conn.timeout = max_seconds
                    except Exception as ex:
                        _logger.info(repr(ex))
                        prev_conn_timeout = None
                if hasattr(cursor, "timeout"):
                    try:
                        cursor.timeout = max_seconds
                    except Exception as ee:
                        _logger.info(repr(ee))
                        pass
            cursor.execute('SELECT 1')
            elapsed = time.monotonic() - start
            if max_seconds and elapsed > max_seconds:
                _logger.warning(
                    "Connection validation exceeded %ss (took %.2fs)",
                    max_seconds,
                    elapsed,
                )
                ok = False
            else:
                ok = True
        except Exception as ex:
            _logger.error(f"Connection validation error: {ex}")
            ok = False
        finally:
            if cursor:
                try:
                    cursor.close()
                except Exception as ee:
                    _logger.info(repr(ee))
                    pass
            if prev_conn_timeout is not None and hasattr(conn, "timeout"):
                try:
                    conn.timeout = prev_conn_timeout
                except Exception as ee:
                    _logger.info(repr(ee))
                    pass
        return ok

    def _probe_connection(self, server, db, user, password, param_str, charset, port, max_seconds):
        if not server:
            return False
        if password is None:
            password = self.decrypt_password()

        ok = False
        start = time.monotonic()
        conn = None
        cursor = None
        try:
            if param_str == '?':
                if not pyodbc:
                    return False
                sqldrivers = [sqldriver for sqldriver in pyodbc.drivers() if 'SQL Server' in sqldriver]
                if not sqldrivers:
                    return False
                conn = pyodbc.connect(
                    f'Driver={sqldrivers[-1]};'
                    f'Server={server};'
                    f'Database={db};'
                    f'Port={port};'
                    'TrustServerCertificate=yes;'
                    'MARS_Connection=yes;'
                    f'UID={user};'
                    f'PWD={password};'
                    f'Connection Timeout={max_seconds or DEFAULT_VALIDATE_TIMEOUT}',
                    autocommit=True,
                )
            else:
                if not pymssql:
                    return False
                conn = pymssql.connect(
                    server=server,
                    user=user,
                    password=password,
                    database=db,
                    timeout=max_seconds or DEFAULT_VALIDATE_TIMEOUT,
                    port=str(port),
                    appname=None,
                    login_timeout=max_seconds or DEFAULT_VALIDATE_TIMEOUT,
                    charset=charset,
                    autocommit=True,
                )

            cursor = conn.cursor()
            if max_seconds and hasattr(cursor, "timeout"):
                try:
                    cursor.timeout = max_seconds
                except Exception as ee:
                    _logger.info(repr(ee))
                    pass
            cursor.execute('SELECT 1')
            cursor.fetchone()

            elapsed = time.monotonic() - start
            ok = (not max_seconds) or elapsed <= max_seconds
        except Exception as ex:
            _logger.error(f"Connection probe error: {ex}")
            ok = False
        finally:
            if cursor:
                try:
                    cursor.close()
                except Exception as ee:
                    _logger.info(repr(ee))
                    pass
            if conn:
                try:
                    conn.close()
                except Exception as ee:
                    _logger.info(repr(ee))
                    pass
        return ok

    def is_connection_valid(
            self,
            conn,
            max_seconds=None,
            cache_key=None,
            cache_ttl=None,
            cache_fail_ttl=None,
            use_cache=True,
            server=None,
            db=DB,
            user=USER,
            password=None,
            param_str='%s',
            charset='CP1256',
            port=1433,
    ):
        """Check if the connection is still valid."""
        if max_seconds is None:
            max_seconds = DEFAULT_VALIDATE_TIMEOUT
        if cache_ttl is None:
            cache_ttl = DEFAULT_VALIDATE_TTL
        if cache_fail_ttl is None:
            cache_fail_ttl = DEFAULT_VALIDATE_FAIL_TTL

        if use_cache and cache_key:
            cached = self._connection_health_cache.get(cache_key)
            if cached:
                cached_until, cached_ok = cached
                if time.monotonic() <= cached_until:
                    return cached_ok
                self._connection_health_cache.pop(cache_key, None)

        ok = False
        if server:
            if max_seconds and max_seconds > 0:
                result = {}

                def _run():
                    result["ok"] = self._probe_connection(
                        server, db, user, password, param_str, charset, port, max_seconds
                    )

                thread = threading.Thread(target=_run, daemon=True)
                thread.start()
                thread.join(max_seconds)
                if thread.is_alive():
                    _logger.warning("Connection probe timed out after %ss", max_seconds)
                    ok = False
                else:
                    ok = bool(result.get("ok", False))
            else:
                ok = self._probe_connection(
                    server, db, user, password, param_str, charset, port, max_seconds
                )
        elif conn:
            ok = self._validate_connection_now(conn, max_seconds)

        if cache_key:
            ttl = cache_ttl if ok else cache_fail_ttl
            if ttl and ttl > 0:
                self._connection_health_cache[cache_key] = (
                    time.monotonic() + ttl,
                    bool(ok),
                )
        return ok

    @staticmethod
    def _is_disconnect_error(ex):
        codes = {
            "08S02",  # communication link failure
            "08S01",  # communication link failure
            "08001",  # client unable to establish connection
            "08003",  # connection does not exist
            "08007",  # connection failure during transaction
            "HYT00",  # timeout expired
            "HYT01",  # connection timeout
        }
        message_snippets = {
            "physical connection is not usable",
            "connection is closed",
            "connection not open",
            "dbprocess is dead",
            "db-lib error message 20047",
            "connection reset",
            "broken pipe",
        }
        for arg in getattr(ex, "args", []):
            if isinstance(arg, (bytes, bytearray)):
                try:
                    arg = arg.decode("utf-8", errors="ignore")
                except Exception as ee:
                    _logger.info(repr(ee))
                    continue
            if not isinstance(arg, str):
                continue
            for code in codes:
                if code in arg:
                    return True
            lowered = arg.lower()
            for snippet in message_snippets:
                if snippet in lowered:
                    return True
        return False

    @contextmanager
    def connect_eplus(self, server=None,
                      db=DB, user=USER,
                      password=None,
                      param_str='%s',
                      charset='CP1256',
                      autocommit=True,
                      port=1433,
                      propagate_error=False,
                      validation_timeout=None,
                      connect_timeout=None,
                      ):
        if server is None:
            server = _get_main_server()
        elif not server:  # server is given server even if None or ''
            raise UserError(_("You pass empty server %s") % (server,))

        if not is_port_open(server, port):
            raise UserError(_("No MSSQL at ip %s port %s") % (server, port))

        user_id = (self.env.uid, server, param_str, charset, autocommit)
        if validation_timeout is None:
            validation_timeout = DEFAULT_VALIDATE_TIMEOUT
        if connect_timeout is None:
            connect_timeout = DEFAULT_CONNECT_TIMEOUT
        if validation_timeout and connect_timeout:
            connect_timeout = min(connect_timeout, validation_timeout)

        probe_password = password or self.decrypt_password()
        # noinspection PyTypeChecker
        probe_key = ("probe",) + user_id
        if not self.is_connection_valid(
                None,
                max_seconds=validation_timeout,
                cache_key=probe_key,
                server=server,
                db=db,
                user=user,
                password=probe_password,
                param_str=param_str,
                charset=charset,
                port=port,
        ):
            raise UserError(_("Server %s is offline or too slow") % server)

        if user_id in self._connection_pool:
            conn = self._connection_pool.get(user_id)
            if not self.is_connection_valid(
                    conn,
                    max_seconds=validation_timeout,
                    cache_key=user_id,
                    server=server,
                    db=db,
                    user=user,
                    password=probe_password,
                    param_str=param_str,
                    charset=charset,
                    port=port,
            ):
                _logger.info(f"Connection for user {user_id} is no longer valid. Creating a new connection.")
                self._connection_pool.pop(user_id, None)
            else:
                _logger.info(f"Using Current Connection for user {user_id}.")

        if user_id not in self._connection_pool:
            password = password or self.decrypt_password()
            _logger.info(f"Creating New Connection For {user_id} ...")
            connect_started = time.monotonic()

            if param_str == '?':
                backend = "pyodbc"

                def _open_pyodbc_connection():
                    sqldrivers = [sqldriver for sqldriver in pyodbc.drivers() if 'SQL Server' in sqldriver]
                    if not sqldrivers:
                        raise UserError(_("No ODBC Driver for SQL Server available, Please Contact dev team."))
                    return pyodbc.connect(
                        f'Driver={sqldrivers[-1]};'
                        f'Server={server};'
                        f'Database={db};'
                        f'Port={port};'
                        'TrustServerCertificate=yes;'
                        'MARS_Connection=yes;'
                        f'UID={user};'
                        f'PWD={password};'
                        f'Connection Timeout={connect_timeout}',
                        autocommit=autocommit)

                raw_conn = _open_pyodbc_connection()
                # conn.setencoding(encoding=charset)
                # conn.setdecoding(pyodbc.SQL_CHAR, encoding=charset)
                # conn.setdecoding(pyodbc.SQL_WCHAR, encoding=charset)
                conn = ConnectionProxy(
                    raw_conn,
                    reconnect_cb=_open_pyodbc_connection,
                    should_reconnect_cb=self._is_disconnect_error,
                    wrap_dict_cursor=True,
                )
            else:
                backend = "pymssql"

                def _open_pymssql_connection():
                    return pymssql.connect(
                        server=server,
                        user=user,
                        password=password,
                        database=db,
                        timeout=0,
                        port=str(port),
                        appname=None,
                        login_timeout=connect_timeout,
                        charset=charset,
                        autocommit=autocommit)

                conn = ConnectionProxy(
                    _open_pymssql_connection(),
                    reconnect_cb=_open_pymssql_connection,
                    should_reconnect_cb=self._is_disconnect_error,
                    wrap_dict_cursor=False,
                )

            self._connection_pool[user_id] = conn
            self._attach_sql_message_logger(conn, backend)
            self._connection_pool[user_id] = conn
            connect_elapsed = time.monotonic() - connect_started
            if validation_timeout and connect_elapsed > validation_timeout:
                self._connection_pool.pop(user_id, None)
                try:
                    conn.close()
                except Exception as ee:
                    _logger.info(repr(ee))
                    pass
                raise UserError(_("Connection is too slow or unavailable."))
            if not self.is_connection_valid(
                    conn,
                    max_seconds=validation_timeout,
                    cache_key=user_id,
                    use_cache=False,
            ):
                self._connection_pool.pop(user_id, None)
                try:
                    conn.close()
                except Exception as ee:
                    _logger.info(repr(ee))
                    pass
                raise UserError(_("Connection is too slow or unavailable."))

        # Use the existing connection
        conn = self._connection_pool[user_id]

        try:
            yield conn
        except pymssqlProgrammingError as pymssql_er:
            raise UserError(f"pymssqlProgrammingError: {repr(pymssql_er)}")
        except pyodbcProgrammingError as pyodbc_er:
            raise UserError(f"pyodbcProgrammingError: {repr(pyodbc_er)}")
        except Exception as ex:
            err = self._format_db_error(ex)
            _logger.exception("Unhandled DB error: %s", err)
            if propagate_error:
                raise Exception("Unhandled DB error: %s", err)
        finally:
            # conn.close()
            # Optionally close the connection if needed (e.g., on logout)
            pass

    @staticmethod
    def _format_db_error(ex):
        parts = []
        for a in getattr(ex, "args", []):
            if isinstance(a, (bytes, bytearray)):
                for enc in ("utf-8", "cp1256", sys.getdefaultencoding()):
                    try:
                        parts.append(a.decode(enc, errors="replace"))
                        break
                    except Exception as ee:
                        _logger.info(repr(ee))
                        continue
                else:
                    parts.append(repr(a))
            else:
                parts.append(str(a))
        name = ex.__class__.__name__
        return f"{name}: " + " | ".join(parts) if parts else f"{name}: {ex!r}"

    @staticmethod
    def _attach_sql_message_logger(conn, backend):
        try:
            if backend == "pymssql":
                low = getattr(conn, "_conn", None)  # _mssql.MSSQLConnection
                if low is not None:
                    def _msgh(msgstate, severity, srvname, procname, line, msgtext):
                        _logger.error(
                            "MSSQL msg sev=%s srvname=%s state=%s proc=%s line=%s: %s",
                            severity, srvname, msgstate, procname, line, msgtext
                        )

                    low.set_msghandler(_msgh)
            # elif backend == "pyodbc":
            #     # Make sure Arabic survives
            #     try:
            #         conn.setencoding("utf-8")
            #         conn.setdecoding(pyodbc.SQL_WCHAR, encoding="utf-8")
            #         conn.setdecoding(pyodbc.SQL_CHAR, encoding="utf-8")
            #     except Exception as ee:
            #         pass
        except Exception as e:
            _logger.warning("Could not attach SQL message logger: %r", e)

    @api.model
    def set_cp1265(self, text):
        try:
            return text.encode('cp1256', errors='replace')
        except Exception as ex:
            _logger.info(repr(ex))
            return text


class FetchAllDictCursor:
    """Only fetchall() returns list[dict]; everything else unchanged."""

    def __init__(self, inner):
        self._c = inner

    # --- context manager support ---
    def __enter__(self):
        # If the underlying cursor supports CM, use it; otherwise just return self
        enter = getattr(self._c, "__enter__", None)
        if enter:
            enter()
        return self

    def __exit__(self, exc_type, exc, tb):
        exit_ = getattr(self._c, "__exit__", None)
        if exit_:
            return exit_(exc_type, exc, tb)
        # Fallback: ensure cursor closes
        try:
            self._c.close()
        except Exception as ee:
            _logger.info(repr(ee))
            pass
        return False  # do not suppress exceptions

    # --- pass-through methods/props ---
    def execute(self, *a, **kw):
        return self._c.execute(*a, **kw)

    def executemany(self, *a, **kw):
        return self._c.executemany(*a, **kw)

    def fetchone(self, *a, **kw):
        return self._c.fetchone(*a, **kw)

    def fetchmany(self, *a, **kw):
        return self._c.fetchmany(*a, **kw)  # tuples

    def __iter__(self):
        return iter(self._c)  # tuples

    @property
    def description(self):
        return self._c.description

    @property
    def rowcount(self):
        return self._c.rowcount

    def close(self):
        return self._c.close()

    # --- only fetchall is dictified ---
    def fetchall(self):
        rows = self._c.fetchall()
        desc = self._c.description
        if not desc:
            return rows
        cols = [d[0] for d in desc]
        # optional: dedupe duplicate column names
        seen = {}
        names = []
        for n in cols:
            i = seen.get(n, 0)
            names.append(n if i == 0 else f"{n}_{i + 1}")
            seen[n] = i + 1
        return [dict(zip(names, r)) for r in rows]


class ConnectionProxy:
    """Expose .cursor(as_dict=True) like pymssql; supports reconnect on disconnect errors."""

    def __init__(self, inner, reconnect_cb=None, should_reconnect_cb=None, wrap_dict_cursor=False):
        self._cn = inner
        self._reconnect_cb = reconnect_cb
        self._should_reconnect_cb = should_reconnect_cb
        self._wrap_dict_cursor = wrap_dict_cursor

    def _should_reconnect(self, ex):
        if self._should_reconnect_cb:
            return self._should_reconnect_cb(ex)
        return False

    def _reconnect(self):
        if not self._reconnect_cb:
            return False
        old_conn = self._cn
        new_conn = self._reconnect_cb()
        if new_conn:
            self._cn = new_conn
            try:
                old_conn.close()
            except Exception as ee:
                _logger.info(repr(ee))
                pass
            return True
        return False

    def cursor(self, *args, **kwargs):
        as_dict = kwargs.get("as_dict", False)
        if self._wrap_dict_cursor:
            kwargs.pop("as_dict", None)
        return ReconnectingCursor(self, args, kwargs, as_dict=as_dict, wrap_dict=self._wrap_dict_cursor)

    def __getattr__(self, name):
        return getattr(self._cn, name)


class ReconnectingCursor:
    """Retry once on disconnect errors by recreating the connection."""

    def __init__(self, proxy, args, kwargs, as_dict=False, wrap_dict=False):
        self._proxy = proxy
        self._args = args
        self._kwargs = kwargs
        self._as_dict = as_dict
        self._wrap_dict = wrap_dict
        self._c = self._make_cursor()

    def _make_cursor(self):
        try:
            cur = self._proxy._cn.cursor(*self._args, **self._kwargs)
        except Exception as ex:
            if self._proxy._should_reconnect(ex) and self._proxy._reconnect():
                cur = self._proxy._cn.cursor(*self._args, **self._kwargs)
            else:
                raise
        if self._as_dict and self._wrap_dict:
            return FetchAllDictCursor(cur)
        return cur

    def _exec(self, method, *a, **kw):
        try:
            return getattr(self._c, method)(*a, **kw)
        except Exception as ex:
            if self._proxy._should_reconnect(ex):
                _logger.warning("E-Plus connection lost; reconnecting and retrying once.")
                if self._proxy._reconnect():
                    self._c = self._make_cursor()
                    return getattr(self._c, method)(*a, **kw)
            raise

    def execute(self, *a, **kw):
        return self._exec("execute", *a, **kw)

    def executemany(self, *a, **kw):
        return self._exec("executemany", *a, **kw)

    def __enter__(self):
        enter = getattr(self._c, "__enter__", None)
        if enter:
            enter()
        return self

    def __exit__(self, exc_type, exc, tb):
        exit_ = getattr(self._c, "__exit__", None)
        if exit_:
            # noinspection PyArgumentList
            return exit_(exc_type, exc, tb)
        try:
            self._c.close()
        except Exception as ex:
            _logger.info(repr(ex))
        return False

    def __getattr__(self, name):
        return getattr(self._c, name)
