# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from contextlib import contextmanager
import pymssql


class TimeOutError(Exception):
    pass


class PyMssqlConnectabdin_eplus(models.AbstractModel):
    _name = 'abdin_eplus.pymssqlconnect'
    _description = 'Connect to pymssql server'

    @contextmanager
    def connect_sql(self, server='192.168.1.150',
                    user='data',
                    password='123',
                    database='genius',
                    timeout=0,
                    login_timeout=10,
                    charset='UTF-8',
                    as_dict=False,
                    host='',
                    appname=None,
                    port='1433',
                    conn_properties=None,
                    autocommit=False,
                    tds_version=None):
        # ده سترنج كونكشن لل pymssql
        cnx = pymssql.connect(server=server,
                              user=user,
                              password=password,
                              database=database,
                              timeout=timeout,
                              login_timeout=login_timeout,
                              charset=charset,
                              as_dict=as_dict,
                              host=host,
                              appname=appname,
                              port=port,
                              conn_properties=conn_properties,
                              autocommit=autocommit,
                              tds_version=tds_version)
        try:
            yield cnx

        except Exception as e:
            # err_msg = _('Somthing went wrong, local server may be offline.')
            raise Exception(e)
        finally:
            if cnx:
                cnx.close()
