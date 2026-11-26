from contextvars import ContextVar
from functools import wraps


_REQUEST = ContextVar('ab_chatter_request', default=None)


def request_cache(method):
    @wraps(method)
    def wrapped(*args, **kwargs):
        if _REQUEST.get() is not None:
            return method(*args, **kwargs)
        token = _REQUEST.set({})
        try:
            return method(*args, **kwargs)
        finally:
            _REQUEST.reset(token)
    return wrapped


def cached_scope(method):
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        cache = _REQUEST.get()
        if cache is None:
            return method(self, *args, **kwargs)
        key = (method.__module__, method.__name__, self.env.uid,
               self.env.su, tuple(self.env.companies.ids), tuple(self.ids),
               repr(self.env.context), repr(args), repr(kwargs))
        if key not in cache:
            cache[key] = method(self, *args, **kwargs)
        return cache[key]
    return wrapped
