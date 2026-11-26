import hashlib
import json
import logging
import os
import time


logger = logging.getLogger(__name__)


def correlation_id(account, reference):
    return hashlib.sha256(json.dumps([account, str(reference)]).encode()).hexdigest()[:32]


def message_correlation(message):
    if message.provider_event:
        return message.provider_event[:32]
    account = message.conversation_id.messaging_account_id.code
    if message.direction == 'in' and message.provider_reference:
        return correlation_id(account, message.provider_reference)
    operation = message.sudo().messaging_operation_ids[:1]
    return correlation_id(account, operation.token if operation else f'outgoing:{message.id}')


def trace(stage, correlations):
    if os.environ.get('CRM_MESSAGING_TRACE') == '1':
        for correlation in correlations:
            logger.info('stage=%s correlation_id=%s timestamp_ns=%s', stage, correlation, time.time_ns())
