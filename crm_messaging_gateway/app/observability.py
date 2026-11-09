from contextlib import contextmanager
import logging
import time

logger = logging.getLogger('crm_messaging.metrics')
logger.setLevel(logging.INFO)


@contextmanager
def latency(operation):
    started = time.monotonic()
    try:
        yield
    finally:
        logger.info(
            'operation=%s elapsed_ms=%.3f',
            operation,
            (time.monotonic() - started) * 1000,
        )
