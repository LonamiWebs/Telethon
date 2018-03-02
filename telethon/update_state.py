import logging
import pickle
from collections import deque
from queue import Queue, Empty
from datetime import datetime
from threading import RLock, Thread

from .tl import types as tl

__log__ = logging.getLogger(__name__)


class UpdateState:
    """Used to hold the current state of processed updates.
       To retrieve an update, .poll() should be called.
    """
    WORKER_POLL_TIMEOUT = 5.0  # Avoid waiting forever on the workers

    def __init__(self, workers=None):
        """
        :param workers: This integer parameter has three possible cases:
          workers is None: Updates will *not* be stored on self.
          workers = 0: Another thread is responsible for calling self.poll()
          workers > 0: 'workers' background threads will be spawned, any
                       any of them will invoke the self.handler.
        """
        self._workers = workers
        self._worker_threads = []

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

    def get_workers(self):
        return self._workers

    def set_workers(self, n):
        """Changes the number of workers running.
           If 'n is None', clears all pending updates from memory.
        """
        if n is None:
            self.stop_workers()
        else:
            self._workers = n
            self.setup_workers()

    workers = property(fget=get_workers, fset=set_workers)

    def stop_workers(self):
        """
        Waits for all the worker threads to stop.
        """
        # Put dummy ``None`` objects so that they don't need to timeout.
        n = self._workers
        self._workers = None
        if n:
            with self._updates_lock:
                for _ in range(n):
                    self._updates.put(None)

        for t in self._worker_threads:
            t.join()

        self._worker_threads.clear()

    def setup_workers(self):
        if self._worker_threads or not self._workers:
            # There already are workers, or workers is None or 0. Do nothing.
            return

        for i in range(self._workers):
            thread = Thread(
                target=UpdateState._worker_loop,
                name='UpdateWorker{}'.format(i),
                daemon=True,
                args=(self, i)
            )
            self._worker_threads.append(thread)
            thread.start()

    def _worker_loop(self, wid):
        while self._workers is not None:
            try:
                update = self.poll(timeout=UpdateState.WORKER_POLL_TIMEOUT)
                if update and self.handler:
                    self.handler(update)
            except StopIteration:
                break
            except:
                # We don't want to crash a worker thread due to any reason
                __log__.exception('Unhandled exception on worker %d', wid)

    def process(self, update):
        """Processes an update object. This method is normally called by
           the library itself.
        """
        if self._workers is None:
            return  # No processing needs to be done if nobody's working

        with self._updates_lock:
            if isinstance(update, tl.updates.State):
                __log__.debug('Saved new updates state')
                self._state = update
                return  # Nothing else to be done

            if hasattr(update, 'pts'):
                self._state.pts = update.pts

            # After running the script for over an hour and receiving over
            # 1000 updates, the only duplicates received were users going
            # online or offline. We can trust the server until new reports.
            if isinstance(update, tl.UpdateShort):
                self._updates.put(update.update)
            # Expand "Updates" into "Update", and pass these to callbacks.
            # Since .users and .chats have already been processed, we
            # don't need to care about those either.
            elif isinstance(update, (tl.Updates, tl.UpdatesCombined)):
                for u in update.updates:
                    self._updates.put(u)
            # TODO Handle "tl.UpdatesTooLong"
            else:
                self._updates.put(update)
