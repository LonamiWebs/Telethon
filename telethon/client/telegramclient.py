import logging
import warnings

from ..tl.functions.updates import GetDifferenceRequest
from ..tl.types.updates import (
    DifferenceSlice, DifferenceEmpty, Difference, DifferenceTooLong
)

try:
    import socks
except ImportError:
    socks = None


from .telegrambaseclient import TelegramBaseClient
from .. import events

from ..tl.types import (
    UpdateNewMessage, Updates
)

__log__ = logging.getLogger(__name__)


class TelegramClient(TelegramBaseClient):
    """
    Initializes the Telegram client with the specified API ID and Hash. This
    is identical to the `telethon.telegram_bare_client.TelegramBareClient`
    but it contains "friendly methods", so please refer to its documentation
    to know what parameters you can use when creating a new instance.
    """

    # region Telegram requests functions

    # region Event handling

    def on(self, event):
        """
        Decorator helper method around add_event_handler().

        Args:
            event (`_EventBuilder` | `type`):
                The event builder class or instance to be used,
                for instance ``events.NewMessage``.
        """
        def decorator(f):
            self.add_event_handler(f, event)
            return f

        return decorator

    def _check_events_pending_resolve(self):
        if self._events_pending_resolve:
            for event in self._events_pending_resolve:
                event.resolve(self)
            self._events_pending_resolve.clear()

    def _on_handler(self, update):
        for builder, callback in self._event_builders:
            event = builder.build(update)
            if event:
                if hasattr(event, '_set_client'):
                    event._set_client(self)
                else:
                    event._client = self

                event.original_update = update
                try:
                    callback(event)
                except events.StopPropagation:
                    __log__.debug(
                        "Event handler '{}' stopped chain of "
                        "propagation for event {}."
                        .format(callback.__name__, type(event).__name__)
                    )
                    break

    def add_event_handler(self, callback, event=None):
        """
        Registers the given callback to be called on the specified event.

        Args:
            callback (`callable`):
                The callable function accepting one parameter to be used.

            event (`_EventBuilder` | `type`, optional):
                The event builder class or instance to be used,
                for instance ``events.NewMessage``.

                If left unspecified, `telethon.events.raw.Raw` (the
                :tl:`Update` objects with no further processing) will
                be passed instead.
        """
        if self.updates.workers is None:
            warnings.warn(
                "You have not setup any workers, so you won't receive updates."
                " Pass update_workers=1 when creating the TelegramClient,"
                " or set client.self.updates.workers = 1"
            )

        self.updates.handler = self._on_handler
        if isinstance(event, type):
            event = event()
        elif not event:
            event = events.Raw()

        if self.is_user_authorized():
            event.resolve(self)
            self._check_events_pending_resolve()
        else:
            self._events_pending_resolve.append(event)

        self._event_builders.append((event, callback))

    def remove_event_handler(self, callback, event=None):
        """
        Inverse operation of :meth:`add_event_handler`.

        If no event is given, all events for this callback are removed.
        Returns how many callbacks were removed.
        """
        found = 0
        if event and not isinstance(event, type):
            event = type(event)

        i = len(self._event_builders)
        while i:
            i -= 1
            ev, cb = self._event_builders[i]
            if cb == callback and (not event or isinstance(ev, event)):
                del self._event_builders[i]
                found += 1

        return found

    def list_event_handlers(self):
        """
        Lists all added event handlers, returning a list of pairs
        consisting of (callback, event).
        """
        return [(callback, event) for event, callback in self._event_builders]

    def add_update_handler(self, handler):
        """Deprecated, see :meth:`add_event_handler`."""
        warnings.warn(
            'add_update_handler is deprecated, use the @client.on syntax '
            'or add_event_handler(callback, events.Raw) instead (see '
            'https://telethon.rtfd.io/en/latest/extra/basic/working-'
            'with-updates.html)'
        )
        return self.add_event_handler(handler, events.Raw)

    def remove_update_handler(self, handler):
        return self.remove_event_handler(handler)

    def list_update_handlers(self):
        return [callback for callback, _ in self.list_event_handlers()]

    def catch_up(self):
        state = self.session.get_update_state(0)
        if not state or not state.pts:
            return

        self.session.catching_up = True
        try:
            while True:
                d = self(GetDifferenceRequest(state.pts, state.date, state.qts))
                if isinstance(d, DifferenceEmpty):
                    state.date = d.date
                    state.seq = d.seq
                    break
                elif isinstance(d, (DifferenceSlice, Difference)):
                    if isinstance(d, Difference):
                        state = d.state
                    elif d.intermediate_state.pts > state.pts:
                        state = d.intermediate_state
                    else:
                        # TODO Figure out why other applications can rely on
                        # using always the intermediate_state to eventually
                        # reach a DifferenceEmpty, but that leads to an
                        # infinite loop here (so check against old pts to stop)
                        break

                    self.updates.process(Updates(
                        users=d.users,
                        chats=d.chats,
                        date=state.date,
                        seq=state.seq,
                        updates=d.other_updates + [UpdateNewMessage(m, 0, 0)
                                                   for m in d.new_messages]
                    ))
                elif isinstance(d, DifferenceTooLong):
                    break
        finally:
            self.session.set_update_state(0, state)
            self.session.catching_up = False

    # endregion

    # region Small utilities to make users' life easier

    def _set_connected_and_authorized(self):
        super()._set_connected_and_authorized()
        self._check_events_pending_resolve()

    # endregion
