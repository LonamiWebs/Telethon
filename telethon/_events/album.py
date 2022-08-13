import asyncio
import time
import weakref

from .base import EventBuilder
from .._misc import utils
from .. import _tl
from ..types import _custom

_IGNORE_MAX_SIZE = 100  # len()
_IGNORE_MAX_AGE = 5  # seconds

# IDs to ignore, and when they were added. If it grows too large, we will
# remove old entries. Although it should generally not be bigger than 10,
# it may be possible some updates are not processed and thus not removed.
_IGNORE_DICT = {}


_HACK_DELAY = 0.5


class AlbumHack:
    """
    When receiving an album from a different data-center, they will come in
    separate `Updates`, so we need to temporarily remember them for a while
    and only after produce the event.

    Of course events are not designed for this kind of wizardy, so this is
    a dirty hack that gets the job done.

    When cleaning up the code base we may want to figure out a better way
    to do this, or just leave the album problem to the users; the update
    handling code is bad enough as it is.
    """
    def __init__(self, client, event):
        # It's probably silly to use a weakref here because this object is
        # very short-lived but might as well try to do "the right thing".
        self._client = weakref.ref(client)
        self._event = event  # parent event
        self._due = asyncio.get_running_loop().time() + _HACK_DELAY

        asyncio.create_task(self.deliver_event())

    def extend(self, messages):
        client = self._client()
        if client:  # weakref may be dead
            self._event.messages.extend(messages)
            self._due = asyncio.get_running_loop().time() + _HACK_DELAY

    async def deliver_event(self):
        while True:
            client = self._client()
            if client is None:
                return  # weakref is dead, nothing to deliver

            diff = self._due - asyncio.get_running_loop().time()
            if diff <= 0:
                # We've hit our due time, deliver event. It won't respect
                # sequential updates but fixing that would just worsen this.
                await client._dispatch_event(self._event)
                return

            del client  # Clear ref and sleep until our due time
            await asyncio.sleep(diff)


class Album(EventBuilder, _custom.chatgetter.ChatGetter, _custom.sendergetter.SenderGetter):
    """
    Occurs whenever you receive an album. This event only exists
    to ease dealing with an unknown amount of messages that belong
    to the same album.

    Members:
        messages (Sequence[`Message <telethon.tl._custom.message.Message>`]):
            The list of messages belonging to the same album.

    Example
        .. code-block:: python

            from telethon import events

            @client.on(events.Album)
            async def handler(event):
                # Counting how many photos or videos the album has
                print('Got an album with', len(event), 'items')

                # Forwarding the album as a whole to some chat
                event.forward_to(chat)

                # Printing the caption
                print(event.text)

                # Replying to the fifth item in the album
                await event.messages[4].reply('Cool!')
    """

    def __init__(self, messages):
        message = messages[0]
        if not message.out and isinstance(message.peer_id, _tl.PeerUser):
            # Incoming message (e.g. from a bot) has peer_id=us, and
            # from_id=bot (the actual "chat" from a user's perspective).
            chat_peer = message.from_id
        else:
            chat_peer = message.peer_id

        _custom.chatgetter.ChatGetter.__init__(self, chat_peer=chat_peer, broadcast=bool(message.post))
        _custom.sendergetter.SenderGetter.__init__(self, message.sender_id)
        self.messages = messages

    def _build(cls, client, update, entities):
        if not others:
            return  # We only care about albums which come inside the same Updates

        if isinstance(update,
                      (_tl.UpdateNewMessage, _tl.UpdateNewChannelMessage)):
            if not isinstance(update.message, _tl.Message):
                return  # We don't care about MessageService's here

            group = update.message.grouped_id
            if group is None:
                return  # It must be grouped

            # Check whether we are supposed to skip this update, and
            # if we do also remove it from the ignore list since we
            # won't need to check against it again.
            if _IGNORE_DICT.pop(id(update), None):
                return

            # Check if the ignore list is too big, and if it is clean it
            # TODO time could technically go backwards; time is not monotonic
            now = time.time()
            if len(_IGNORE_DICT) > _IGNORE_MAX_SIZE:
                for i in [i for i, t in _IGNORE_DICT.items() if now - t > _IGNORE_MAX_AGE]:
                    del _IGNORE_DICT[i]

            # Add the other updates to the ignore list
            for u in others:
                if u is not update:
                    _IGNORE_DICT[id(u)] = now

            # Figure out which updates share the same group and use those
            return cls.Event([
                u.message for u in others
                if (isinstance(u, (_tl.UpdateNewMessage, _tl.UpdateNewChannelMessage))
                    and isinstance(u.message, _tl.Message)
                    and u.message.grouped_id == group)
            ])

        self = cls.__new__(cls)
        self._client = client
        self._sender = entities.get(_tl.PeerUser(update.user_id))
        self._chat = entities.get(_tl.PeerUser(update.user_id))
        return self

    def _set_client(self, client):
        super()._set_client(client)
        self._sender, self._input_sender = utils._get_entity_pair(self.sender_id, self._entities)

        self.messages = [
            _custom.Message._new(client, m, self._entities, None)
            for m in self.messages
        ]

        if len(self.messages) == 1:
            # This will require hacks to be a proper album event
            hack = client._albums.get(self.grouped_id)
            if hack is None:
                client._albums[self.grouped_id] = AlbumHack(client, self)
            else:
                hack.extend(self.messages)

    @property
    def grouped_id(self):
        """
        The shared ``grouped_id`` between all the messages.
        """
        return self.messages[0].grouped_id

    @property
    def text(self):
        """
        The message text of the first photo with a caption,
        formatted using the client's default parse mode.
        """
        return next((m.text for m in self.messages if m.text), '')

    @property
    def raw_text(self):
        """
        The raw message text of the first photo
        with a caption, ignoring any formatting.
        """
        return next((m.raw_text for m in self.messages if m.raw_text), '')

    @property
    def is_reply(self):
        """
        `True` if the album is a reply to some other message.

        Remember that you can access the ID of the message
        this one is replying to through `reply_to_msg_id`,
        and the `Message` object with `get_reply_message()`.
        """
        # Each individual message in an album all reply to the same message
        return self.messages[0].is_reply

    @property
    def forward(self):
        """
        The `Forward <telethon.tl._custom.forward.Forward>`
        information for the first message in the album if it was forwarded.
        """
        # Each individual message in an album all reply to the same message
        return self.messages[0].forward

    # endregion Public Properties

    # region Public Methods

    async def get_reply_message(self):
        """
        The `Message <telethon.tl._custom.message.Message>`
        that this album is replying to, or `None`.

        The result will be cached after its first use.
        """
        return await self.messages[0].get_reply_message()

    async def respond(self, *args, **kwargs):
        """
        Responds to the album (not as a reply). Shorthand for
        `telethon.client.messages.MessageMethods.send_message`
        with ``entity`` already set.
        """
        return await self.messages[0].respond(*args, **kwargs)

    async def reply(self, *args, **kwargs):
        """
        Replies to the first photo in the album (as a reply). Shorthand
        for `telethon.client.messages.MessageMethods.send_message`
        with both ``entity`` and ``reply_to`` already set.
        """
        return await self.messages[0].reply(*args, **kwargs)

    async def forward_to(self, *args, **kwargs):
        """
        Forwards the entire album. Shorthand for
        `telethon.client.messages.MessageMethods.forward_messages`
        with both ``messages`` and ``from_peer`` already set.
        """
        if self._client:
            kwargs['messages'] = self.messages
            kwargs['from_peer'] = await self.get_input_chat()
            return await self._client.forward_messages(*args, **kwargs)

    async def edit(self, *args, **kwargs):
        """
        Edits the first caption or the message, or the first messages'
        caption if no caption is set, iff it's outgoing. Shorthand for
        `telethon.client.messages.MessageMethods.edit_message`
        with both ``entity`` and ``message`` already set.

        Returns `None` if the message was incoming,
        or the edited `Message` otherwise.

        .. note::

            This is different from `client.edit_message
            <telethon.client.messages.MessageMethods.edit_message>`
            and **will respect** the previous state of the message.
            For example, if the message didn't have a link preview,
            the edit won't add one by default, and you should force
            it by setting it to `True` if you want it.

            This is generally the most desired and convenient behaviour,
            and will work for link previews and message buttons.
        """
        for msg in self.messages:
            if msg.raw_text:
                return await msg.edit(*args, **kwargs)

        return await self.messages[0].edit(*args, **kwargs)

    async def delete(self, *args, **kwargs):
        """
        Deletes the entire album. You're responsible for checking whether
        you have the permission to do so, or to except the error otherwise.
        Shorthand for
        `telethon.client.messages.MessageMethods.delete_messages` with
        ``entity`` and ``message_ids`` already set.
        """
        if self._client:
            return await self._client.delete_messages(
                await self.get_input_chat(), self.messages,
                *args, **kwargs
            )

    async def mark_read(self):
        """
        Marks the entire album as read. Shorthand for
        `client.mark_read()
        <telethon.client.messages.MessageMethods.mark_read>`
        with both ``entity`` and ``message`` already set.
        """
        if self._client:
            await self._client.mark_read(
                await self.get_input_chat(), max_id=self.messages[-1].id)

    async def pin(self, *, notify=False):
        """
        Pins the first photo in the album. Shorthand for
        `telethon.client.messages.MessageMethods.pin_message`
        with both ``entity`` and ``message`` already set.
        """
        return await self.messages[0].pin(notify=notify)

    def __len__(self):
        """
        Return the amount of messages in the album.

        Equivalent to ``len(self.messages)``.
        """
        return len(self.messages)

    def __iter__(self):
        """
        Iterate over the messages in the album.

        Equivalent to ``iter(self.messages)``.
        """
        return iter(self.messages)

    def __getitem__(self, n):
        """
        Access the n'th message in the album.

        Equivalent to ``event.messages[n]``.
        """
        return self.messages[n]
