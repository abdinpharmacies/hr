# -*- coding: utf-8 -*-
import logging
import sys

from odoo import models, _, api
from odoo.exceptions import UserError
from .ping_host import ping
from contextlib import contextmanager
from cryptography.fernet import Fernet
from odoo.tools import config

SERVER = None
try:
    import pymssql

    pymssqlProgrammingError = pymssql.ProgrammingError
except ImportError:
    pymssqlProgrammingError = Exception

try:
    import pyodbc

    pyodbcProgrammingError = pyodbc.ProgrammingError
except ImportError:
    pyodbcProgrammingError = Exception


def _get_main_server():
    global SERVER
    if SERVER:
        return SERVER

    conf_bconnect_ips = [config.get('bconnect_ip1'), config.get('bconnect_ip2'), ]
    if not conf_bconnect_ips:
        raise UserError(_("NO IPs in odoo config file."))

    for value in conf_bconnect_ips:
        _logger.info(f"######## Trying IP {value} #########")
        if ping(value):
            SERVER = value
            return SERVER
    raise UserError(_("All BConnect Server IPs may be Offline."))


USER = config.get('bconnect_user')
DB = config.get('bconnect_db')
DECRYPTION_KEY = config.get('decryption_key')

_logger = logging.getLogger(__name__)


class EPlusConnect(models.AbstractModel):
    _name = 'ab_eplus_connect'
    _description = 'ab_eplus_connect'

    # Connection pool to store connections by user
    _connection_pool = {}

    def decrypt_password(self):
        encrypted_password = bytes(self.env['ir.config_parameter'].sudo().get_param("bconnect_crypt_pass"), 'utf-8')
        cipher = Fernet(bytes(DECRYPTION_KEY, 'utf-8'))
        password = cipher.decrypt(encrypted_password).decode('utf-8')
        return password

    def is_connection_valid(self, conn):
        """Check if the connection is still valid."""
        try:
            # Perform a simple query to check if the connection is alive
            cursor = conn.cursor()
            cursor.execute('SELECT 1')
            cursor.close()
            return True
        except Exception as ex:
            _logger.error(f"Connection validation error: {ex}")
            return False

    @contextmanager
    def connect_eplus(self, server=None,
                      db=DB, user=USER, password=None,
                      param_str='%s',
                      charset='CP1256',
                      autocommit=True,
                      propagate_error=False):
        if server is None:
            server = _get_main_server()
        elif not server:  # server is given server even if None or ''
            raise UserError(_("You pass empty server %s") % (server,))

        user_id = (self.env.uid, server, param_str, charset)
        if user_id in self._connection_pool:
            conn = self._connection_pool.get(user_id)
            if not self.is_connection_valid(conn):
                _logger.info(f"Connection for user {user_id} is no longer valid. Creating a new connection.")
                self._connection_pool.pop(user_id, None)
            else:
                _logger.info(f"Using Current Connection for user {user_id}.")

        if user_id not in self._connection_pool:
            password = password or self.decrypt_password()
            _logger.info(f"Creating New Connection For {user_id} ...")

            if param_str == '?':
                backend = "pyodbc"
                sqldrivers = [sqldriver for sqldriver in pyodbc.drivers() if 'SQL Server' in sqldriver]
                if sqldrivers:
                    conn = pyodbc.connect(
                        f'Driver={sqldrivers[-1]};'
                        f'Server={server};'
                        f'Database={db};'
                        'Port=1433;'
                        'TrustServerCertificate=yes;'
                        'MARS_Connection=yes;'
                        f'UID={user};'
                        f'PWD={password}',
                        autocommit=autocommit)
                    # conn.setencoding(encoding=charset)
                    # conn.setdecoding(pyodbc.SQL_CHAR, encoding=charset)
                    # conn.setdecoding(pyodbc.SQL_WCHAR, encoding=charset)
                    conn = ConnectionProxy(conn)

                else:
                    raise UserError(_("No ODBC Driver for SQL Server available, Please Contact dev team."))
            else:
                backend = "pymssql"
                conn = pymssql.connect(
                    server=server,
                    user=user,
                    password=password,
                    database=db,
                    timeout=0,
                    appname=None,
                    login_timeout=10,
                    charset=charset,
                    autocommit=autocommit)

            self._connection_pool[user_id] = conn
            self._attach_sql_message_logger(conn, backend)
            self._connection_pool[user_id] = conn

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

    def _format_db_error(self, ex):
        parts = []
        for a in getattr(ex, "args", []):
            if isinstance(a, (bytes, bytearray)):
                for enc in ("utf-8", "cp1256", sys.getdefaultencoding()):
                    try:
                        parts.append(a.decode(enc, errors="replace"))
                        break
                    except Exception:
                        continue
                else:
                    parts.append(repr(a))
            else:
                parts.append(str(a))
        name = ex.__class__.__name__
        return f"{name}: " + " | ".join(parts) if parts else f"{name}: {ex!r}"

    def _attach_sql_message_logger(self, conn, backend):
        try:
            if backend == "pymssql":
                low = getattr(conn, "_conn", None)  # _mssql.MSSQLConnection
                if low is not None:
                    def _msgh(msgstate, severity, srvname, procname, line, msgtext):
                        _logger.error(
                            "MSSQL msg sev=%s state=%s proc=%s line=%s: %s",
                            severity, msgstate, procname, line, msgtext
                        )

                    low.set_msghandler(_msgh)
            # elif backend == "pyodbc":
            #     # Make sure Arabic survives
            #     try:
            #         conn.setencoding("utf-8")
            #         conn.setdecoding(pyodbc.SQL_WCHAR, encoding="utf-8")
            #         conn.setdecoding(pyodbc.SQL_CHAR, encoding="utf-8")
            #     except Exception:
            #         pass
        except Exception as e:
            _logger.warning("Could not attach SQL message logger: %r", e)

    @api.model
    def set_cp1265(self, text):
        try:
            return text.encode('cp1256', errors='replace')
        except Exception as ex:
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
        except Exception:
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
    """Expose .cursor(as_dict=True) like pymssql; only affects fetchall()."""

    def __init__(self, inner):
        self._cn = inner

    def cursor(self, *args, **kwargs):
        as_dict = kwargs.pop("as_dict", False)
        cur = self._cn.cursor(*args, **kwargs)
        return FetchAllDictCursor(cur) if as_dict else cur

    def __getattr__(self, name):
        return getattr(self._cn, name)
