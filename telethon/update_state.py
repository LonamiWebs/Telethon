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
                       any of them will invoke all the self.handlers.
        """
        self._workers = workers
        self._worker_threads = []

        self.handlers = []
        self._updates_lock = RLock()
        self._updates = Queue()
        self._latest_updates = deque(maxlen=10)

        # https://core.telegram.org/api/updates
        self._state = tl.updates.State(0, 0, datetime.now(), 0, 0)

    def can_poll(self):
        """Returns True if a call to .poll() won't lock"""
        return not self._updates.empty()

    def poll(self, timeout=None):
        """Polls an update or blocks until an update object is available.
           If 'timeout is not None', it should be a floating point value,
           and the method will 'return None' if waiting times out.
        """
        try:
            update = self._updates.get(timeout=timeout)
        except Empty:
            return

        if isinstance(update, Exception):
            raise update  # Some error was set through (surely StopIteration)

        return update

    def get_workers(self):
        return self._workers

    def set_workers(self, n):
        """Changes the number of workers running.
           If 'n is None', clears all pending updates from memory.
        """
        self.stop_workers()
        self._workers = n
        if n is None:
            while self._updates:
                self._updates.get()
        else:
            self.setup_workers()

    workers = property(fget=get_workers, fset=set_workers)

    def stop_workers(self):
        """Raises "StopIterationException" on the worker threads to stop them,
           and also clears all of them off the list
        """
        if self._workers:
            with self._updates_lock:
                # Insert at the beginning so the very next poll causes an error
                # on all the worker threads
                # TODO Should this reset the pts and such?
                for _ in range(self._workers):
                    self._updates.put(StopIteration())

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
        while True:
            try:
                update = self.poll(timeout=UpdateState.WORKER_POLL_TIMEOUT)
                # TODO Maybe people can add different handlers per update type
                if update:
                    for handler in self.handlers:
                        handler(update)
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

            pts = getattr(update, 'pts', self._state.pts)
            if hasattr(update, 'pts') and pts <= self._state.pts:
                __log__.info('Ignoring %s, already have it', update)
                return  # We already handled this update

            self._state.pts = pts

            # TODO There must be a better way to handle updates rather than
            # keeping a queue with the latest updates only, and handling
            # the 'pts' correctly should be enough. However some updates
            # like UpdateUserStatus (even inside UpdateShort) will be called
            # repeatedly very often if invoking anything inside an update
            # handler. TODO Figure out why.
            """
            client = TelegramClient('anon', api_id, api_hash, update_workers=1)
            client.connect()
            def handle(u):
                client.get_me()
            client.add_update_handler(handle)
            input('Enter to exit.')
            """
            data = pickle.dumps(update.to_dict())
            if data in self._latest_updates:
                __log__.info('Ignoring %s, already have it', update)
                return  # Duplicated too

            self._latest_updates.append(data)

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
