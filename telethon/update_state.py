import logging
from collections import deque
from datetime import datetime
from threading import RLock, Event, Thread

from .tl import types as tl


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
                       any of them will invoke all the self.handlers.
        """
        self._workers = workers
        self._worker_threads = []

        self.handlers = []
        self._updates_lock = RLock()
        self._updates_available = Event()
        self._updates = deque()

        self._logger = logging.getLogger(__name__)

        # https://core.telegram.org/api/updates
        self._state = tl.updates.State(0, 0, datetime.now(), 0, 0)
        self._setup_workers()

    def can_poll(self):
        """Returns True if a call to .poll() won't lock"""
        return self._updates_available.is_set()

    def poll(self, timeout=None):
        """Polls an update or blocks until an update object is available.
           If 'timeout is not None', it should be a floating point value,
           and the method will 'return None' if waiting times out.
        """
        if not self._updates_available.wait(timeout=timeout):
            return

        with self._updates_lock:
            if not self._updates_available.is_set():
                return

            update = self._updates.popleft()
            if not self._updates:
                self._updates_available.clear()

        if isinstance(update, Exception):
            raise update  # Some error was set through (surely StopIteration)

        return update

    def get_workers(self):
        return self._workers

    def set_workers(self, n):
        """Changes the number of workers running.
           If 'n is None', clears all pending updates from memory.
        """
        self._stop_workers()
        self._workers = n
        if n is None:
            self._updates.clear()
        else:
            self._setup_workers()

    workers = property(fget=get_workers, fset=set_workers)

    def _stop_workers(self):
        """Raises "StopIterationException" on the worker threads to stop them,
           and also clears all of them off the list
        """
        if self._workers:
            with self._updates_lock:
                # Insert at the beginning so the very next poll causes an error
                # on all the worker threads
                # TODO Should this reset the pts and such?
                for _ in range(self._workers):
                    self._updates.appendleft(StopIteration())
                self._updates_available.set()

        for t in self._worker_threads:
            t.join()

        self._worker_threads.clear()

    def _setup_workers(self):
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
        while True:
            try:
                update = self.poll(timeout=UpdateState.WORKER_POLL_TIMEOUT)
                # TODO Maybe people can add different handlers per update type
                if update:
                    for handler in self.handlers:
                        handler(update)
            except StopIteration:
                break
            except Exception as e:
                # We don't want to crash a worker thread due to any reason
                self._logger.debug(
                    '[ERROR] Unhandled exception on worker {}'.format(wid), e
                )

    def process(self, update):
        """Processes an update object. This method is normally called by
           the library itself.
        """
        if self._workers is None:
            return  # No processing needs to be done if nobody's working

        with self._updates_lock:
            if isinstance(update, tl.updates.State):
                self._state = update
                return  # Nothing else to be done

            pts = getattr(update, 'pts', self._state.pts)
            if hasattr(update, 'pts') and pts <= self._state.pts:
                return  # We already handled this update

            self._state.pts = pts
            self._updates.append(update)
            self._updates_available.set()
