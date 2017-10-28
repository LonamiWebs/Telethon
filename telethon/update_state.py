import logging
import pickle
import asyncio
from collections import deque
from datetime import datetime

from .tl import types as tl


class UpdateState:
    """Used to hold the current state of processed updates.
       To retrieve an update, .poll() should be called.
    """
    WORKER_POLL_TIMEOUT = 5.0  # Avoid waiting forever on the workers

    def __init__(self, loop=None):
        self.handlers = []
        self._latest_updates = deque(maxlen=10)
        self._loop = loop if loop else asyncio.get_event_loop()

        self._logger = logging.getLogger(__name__)

        # https://core.telegram.org/api/updates
        self._state = tl.updates.State(0, 0, datetime.now(), 0, 0)

    def handle_update(self, update):
        for handler in self.handlers:
            asyncio.ensure_future(handler(update), loop=self._loop)

    def process(self, update):
        """Processes an update object. This method is normally called by
           the library itself.
        """
        if isinstance(update, tl.updates.State):
            self._state = update
            return  # Nothing else to be done

        pts = getattr(update, 'pts', self._state.pts)
        if hasattr(update, 'pts') and pts <= self._state.pts:
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
            return  # Duplicated too

        self._latest_updates.append(data)

        if type(update).SUBCLASS_OF_ID == 0x8af52aac:  # crc32(b'Updates')
            # Expand "Updates" into "Update", and pass these to callbacks.
            # Since .users and .chats have already been processed, we
            # don't need to care about those either.
            if isinstance(update, tl.UpdateShort):
                self.handle_update(update.update)

            elif isinstance(update, (tl.Updates, tl.UpdatesCombined)):
                for upd in update.updates:
                    self.handle_update(upd)

            elif not isinstance(update, tl.UpdatesTooLong):
                # TODO Handle "Updates too long"
                self.handle_update(update)

        elif type(update).SUBCLASS_OF_ID == 0x9f89304e:  # crc32(b'Update')
            self.handle_update(update)
        else:
            self._logger.debug('Ignoring "update" of type {}'.format(
                type(update).__name__)
            )
