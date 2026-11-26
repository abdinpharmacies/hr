import hashlib
import json
import logging
import os
import time


logger = logging.getLogger('crm_messaging.timing')


def correlation_id(account, reference):
    return hashlib.sha256(json.dumps([account, str(reference)]).encode()).hexdigest()[:32]


def trace(stage, account, reference):
    if os.environ.get('CRM_MESSAGING_TRACE') == '1':
        logger.warning('stage=%s correlation_id=%s timestamp_ns=%s',
            stage, correlation_id(account, reference), time.time_ns())
