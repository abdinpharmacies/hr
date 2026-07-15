from odoo.tools.translate import _
# -*- coding: utf-8 -*-
from time import sleep
from xmlrpc import client
import logging
from odoo.exceptions import UserError
from cryptography.fernet import Fernet
from odoo.tools import config

_logger = logging.getLogger(__name__)
DECRYPTION_KEY = config.get('decryption_key')


class OdooConnectionSingleton:
    _instance = None
    _conn = None
    _uid = None
    _db = None
    _password = None
    _srv = None
    _user = None
    _db_name = None
    _password_param = None
    _checking = False

    # must pass env ot OdooConnectionSingleton(env) (__new__ is replacement for __init__)
    def __new__(cls, env):
        """
        # check if OdooConnectionSingleton class does not have _instance attribute,
        #    then create _instance.
        #    _instance is object of type OdooConnectionSingleton().
        #    _instance._setup_connection_params(env) will add available connection to _instance,
        #      via using env which has odoo environment (to get ir.config_parameter).
        """
        if cls._instance is None:
            cls._instance = super(OdooConnectionSingleton, cls).__new__(cls)
            cls._instance._setup_connection_params(env)
            _logger.info('Created new instance of OdooConnectionSingleton.')
        else:
            # if connection is not valid - via query res.partner -,
            #   then create new _instance and reconnect
            if not cls._instance.check_connection():
                _logger.warning('Connection is invalid. Creating a new instance.')
                cls._instance = super(OdooConnectionSingleton, cls).__new__(cls)
                cls._instance._setup_connection_params(env)
                cls._instance.connect_to_server()
        return cls._instance

    def _setup_connection_params(self, env):
        """Set up connection parameters only once."""
        conf_mo = env['ir.config_parameter'].sudo()
        self._srv = conf_mo.get_param('server_address')
        self._user = conf_mo.get_param('server_user')
        self._db_name = conf_mo.get_param('server_db')
        self._password_param = self._decrypt_password(conf_mo.get_param('server_password'))

        # Initialize connection
        self.connect_to_server()

    @staticmethod
    def _decrypt_password(encrypted_password):
        if not encrypted_password:
            return encrypted_password
        cipher = Fernet(bytes(DECRYPTION_KEY, 'utf-8'))
        return cipher.decrypt(bytes(encrypted_password, 'utf-8')).decode('utf-8')

    def connect_to_server(self):
        try:
            common = client.ServerProxy(f"{self._srv}/xmlrpc/2/common")
            uid = common.authenticate(self._db_name, self._user, self._password_param, {})
            conn = client.ServerProxy(f"{self._srv}/xmlrpc/2/object", allow_none=True)

            if uid:
                self._conn = conn
                self._uid = uid
                self._db = self._db_name
                self._password = self._password_param
            else:
                msg = "Authentication failed. Exiting ..."
                _logger.warning(msg)
                raise UserError(_(msg))
        except Exception as e:
            _logger.error(f"Connection failed: {e}. Retrying in 5 seconds...")
            sleep(5)  # Optionally add retry logic

    def check_connection(self):
        """Check if the current connection is still valid by querying a small model."""
        if self._checking:
            return False
        self._checking = True
        try:
            if not (self._srv and self._db_name and self._user and self._password_param):
                return False
            proxy = self._conn
            if not isinstance(proxy, client.ServerProxy):
                proxy = client.ServerProxy(f"{self._srv}/xmlrpc/2/object", allow_none=True)
            # Query the 'res.partner' model for a single record and only return the 'id' field
            result = proxy.execute_kw(
                self._db,
                self._uid,
                self._password,
                'res.partner',
                'search_read',
                [[]],
                {'fields': ['id'], 'limit': 1}
            )
            if result:
                return True
            else:
                _logger.warning("Connection to the server is not valid.")
                return False
        except Exception as e:
            _logger.error(f"Connection validation failed: {e}")
            return False
        finally:
            self._checking = False

    def get_connection(self):
        """Return connection details if the connection is valid. Attempt to reconnect if not."""
        if not self.check_connection():
            _logger.warning("Invalid connection detected. Attempting to reconnect...")
            self.connect_to_server()

            # Recheck the connection after attempting to reconnect
            if not self.check_connection():
                _logger.error("Reconnection attempt failed.")
                raise UserError(_("Reconnection attempt failed."))

        return self._conn, self._uid, self._db, self._password

    def execute_kw(self, model_name, method, params, kwargs=None):
        """
        A wrapper for the execute_kw method that automatically supplies the db, uid,
        and password retrieved from the connection pool.
        """
        if kwargs is None:
            kwargs = {}
        conn, uid, db, password = self.get_connection()
        return conn.execute_kw(db, uid, password, model_name, method, params, kwargs)
