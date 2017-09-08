from collections import deque
from datetime import datetime
from threading import RLock, Event

from .tl import types as tl


class UpdateState:
    """Used to hold the current state of processed updates.
       To retrieve an update, .poll() should be called.
    """
    def __init__(self, polling):
        self._polling = polling
        self.handlers = []
        self._updates_lock = RLock()
        self._updates_available = Event()
        self._updates = deque()

        # https://core.telegram.org/api/updates
        self._state = tl.updates.State(0, 0, datetime.now(), 0, 0)

    def can_poll(self):
        """Returns True if a call to .poll() won't lock"""
        return self._updates_available.is_set()

    def poll(self):
        """Polls an update or blocks until an update object is available"""
        if not self._polling:
            raise ValueError('Updates are not being polled hence not saved.')

        self._updates_available.wait()
        with self._updates_lock:
            update = self._updates.popleft()
            if not self._updates:
                self._updates_available.clear()

            return update

    def get_polling(self):
        return self._polling

    def set_polling(self, polling):
        self._polling = polling
        if not polling:
            with self._updates_lock:
                self._updates.clear()

    polling = property(fget=get_polling, fset=set_polling)

    def process(self, update):
        """Processes an update object. This method is normally called by
           the library itself.
        """
        if not self._polling and not self.handlers:
            return

        with self._updates_lock:
            if isinstance(update, tl.updates.State):
                self._state = update
            elif not hasattr(update, 'pts') or update.pts > self._state.pts:
                self._state.pts = getattr(update, 'pts', self._state.pts)
                for handler in self.handlers:
                    handler(update)

                if self._polling:
                    self._updates.append(update)
                    self._updates_available.set()
