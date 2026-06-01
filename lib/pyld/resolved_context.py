"""
Representation for a resolved Context.

.. module:: resolved_context
  :synopsis: Creates a ContextResolver

.. moduleauthor:: Dave Longley
.. moduleauthor:: Gregg Kellogg <gregg@greggkellogg.net>
"""

import threading

from cachetools import LRUCache

MAX_ACTIVE_CONTEXTS = 10


# cachetools.LRUCache is not thread-safe. pyld shares both the module-level
# inverse-context/resolved-context caches and the per-`ResolvedContext`
# processed-context cache below across `JsonLdProcessor` invocations from any
# thread (a `ResolvedContext` is itself stored in the shared resolved-context
# cache, so its `cache` attribute is reached concurrently). Without this
# wrapper, concurrent compaction races on popitem/__setitem__ and corrupts the
# underlying OrderedDict, surfacing as
# `RuntimeError: OrderedDict mutated during iteration`.
class ThreadSafeLRUCache(LRUCache):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # RLock because LRUCache.__setitem__ may call self.popitem()
        # internally on eviction; both methods need to acquire the lock.
        self._lock = threading.RLock()

    def __getitem__(self, key):
        with self._lock:
            return super().__getitem__(key)

    def __setitem__(self, key, value):
        with self._lock:
            super().__setitem__(key, value)

    def __delitem__(self, key):
        with self._lock:
            super().__delitem__(key)

    def __contains__(self, key):
        with self._lock:
            return super().__contains__(key)

    def __len__(self):
        with self._lock:
            return super().__len__()

    def __iter__(self):
        with self._lock:
            return iter(list(super().__iter__()))

    def get(self, key, default=None):
        with self._lock:
            return super().get(key, default)

    def pop(self, *args, **kwargs):
        with self._lock:
            return super().pop(*args, **kwargs)

    def popitem(self):
        with self._lock:
            return super().popitem()


class ResolvedContext:
    """
    A cached contex document, with a cache indexed by referencing active context.
    """

    def __init__(self, document):
        """
        Creates a ResolvedContext with caching for processed contexts
        relative to some other Active Context.
        """
        # processor-specific RDF parsers
        self.document = document
        self.cache = ThreadSafeLRUCache(maxsize=MAX_ACTIVE_CONTEXTS)

    def get_processed(self, active_ctx):
        """
        Returns any processed context for this resolved context relative to an active context.
        """
        return self.cache.get(active_ctx['_uuid'])

    def set_processed(self, active_ctx, processed_ctx):
        """
        Sets any processed context for this resolved context relative to an active context.
        """
        self.cache[active_ctx['_uuid']] = processed_ctx
