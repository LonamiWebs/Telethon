from threading import Lock, Event
from collections import deque


class UpdateState:
    """Used to hold the current state of processed updates.
       To retrieve an update, .pop_update() should be called.
    """
    def __init__(self, enabled):
        self.enabled = enabled
        self._updates_lock = Lock()
        self._updates_available = Event()
        self._updates = deque()

    def has_any(self):
        """Returns True if a call to .pop_update() won't lock"""
        return self._updates_available.is_set()

    def pop(self):
        """Pops an update or blocks until an update object is available"""
        self._updates_available.wait()
        with self._updates_lock:
            update = self._updates.popleft()
            if not self._updates:
                self._updates_available.clear()

            return update

    def process(self, update):
        """Processes an update object. This method is normally called by
           the library itself.
        """
        if not self.enabled:
            return

        with self._updates_lock:
            self._updates.append(update)
            self._updates_available.set()
