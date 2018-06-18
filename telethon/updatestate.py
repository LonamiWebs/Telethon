import itertools
import logging
from datetime import datetime
from queue import Queue, Empty
from threading import RLock

from . import utils
from .tl import types as tl

__log__ = logging.getLogger(__name__)


class UpdateState:
    """
    Used to hold the current state of processed updates.
    To retrieve an update, :meth:`poll` should be called.
    """
    WORKER_POLL_TIMEOUT = 5.0  # Avoid waiting forever on the workers

    def __init__(self):
        self.handler = None
        self._updates_lock = RLock()
        self._updates = Queue()

        # https://core.telegram.org/api/updates
        self._state = tl.updates.State(0, 0, datetime.now(), 0, 0)

    def can_poll(self):
        """Returns True if a call to .poll() won't lock"""
        return not self._updates.empty()

    def poll(self, timeout=None):
        """
        Polls an update or blocks until an update object is available.
        If 'timeout is not None', it should be a floating point value,
        and the method will 'return None' if waiting times out.
        """
        try:
            return self._updates.get(timeout=timeout)
        except Empty:
            return None

    def get_update_state(self, entity_id):
        """Gets the updates.State corresponding to the given entity or 0."""
        return self._state

    def process(self, update):
        """Processes an update object. This method is normally called by
           the library itself.
        """
        if isinstance(update, tl.updates.State):
            __log__.debug('Saved new updates state')
            self._state = update
            return  # Nothing else to be done

        if hasattr(update, 'pts'):
            self._state.pts = update.pts

        # After running the script for over an hour and receiving over
        # 1000 updates, the only duplicates received were users going
        # online or offline. We can trust the server until new reports.
        # This should only be used as read-only.
        if isinstance(update, tl.UpdateShort):
            update.update._entities = {}
            self._updates.put(update.update)

        # Expand "Updates" into "Update", and pass these to callbacks.
        # Since .users and .chats have already been processed, we
        # don't need to care about those either.
        elif isinstance(update, (tl.Updates, tl.UpdatesCombined)):
            entities = {utils.get_peer_id(x): x for x in
                        itertools.chain(update.users, update.chats)}
            for u in update.updates:
                u._entities = entities
                self._updates.put(u)
        else:
            update._entities = {}
            self._updates.put(update)
