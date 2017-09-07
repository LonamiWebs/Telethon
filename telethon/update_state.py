from collections import deque
from datetime import datetime
from threading import RLock, Event

from .tl import types as tl


class UpdateState:
    """Used to hold the current state of processed updates.
       To retrieve an update, .pop_update() should be called.
    """
    def __init__(self, enabled, store_updates):
        self.enabled = enabled
        self._store_updates = store_updates
        self.handlers = []
        self._updates_lock = RLock()
        self._updates_available = Event()
        self._updates = deque()

        # https://core.telegram.org/api/updates
        self._state = tl.updates.State(0, 0, datetime.now(), 0, 0)

    def has_any(self):
        """Returns True if a call to .pop_update() won't lock"""
        return self._updates_available.is_set()

    def poll(self):
        """Polls an update or blocks until an update object is available"""
        if not self._store_updates:
            raise ValueError('Polling updates is not enabled.')

        self._updates_available.wait()
        with self._updates_lock:
            update = self._updates.popleft()
            if not self._updates:
                self._updates_available.clear()

            return update

    def set_polling(self, store):
        self._store_updates = store
        if not store:
            with self._updates_lock:
                self._updates.clear()

    def process(self, update):
        """Processes an update object. This method is normally called by
           the library itself.
        """
        if not self.enabled:
            return

        with self._updates_lock:
            if isinstance(update, tl.updates.State):
                self._state = update
            elif not hasattr(update, 'pts') or update.pts > self._state.pts:
                self._state.pts = getattr(update, 'pts', self._state.pts)
                for handler in self.handlers:
                    handler(update)

                if self._store_updates:
                    self._updates.append(update)
                    self._updates_available.set()
