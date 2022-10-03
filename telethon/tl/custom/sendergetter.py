import abc


class SenderGetter(abc.ABC):
    """
    Helper base class that introduces the `sender`, `input_sender`
    and `sender_id` properties and `get_sender` and `get_input_sender`
    methods.
    """
    def __init__(self, sender_id=None, *, sender=None, input_sender=None):
        self._sender_id = sender_id
        self._sender = sender
        self._input_sender = input_sender
        self._client = None

    @property
    def sender(self):
        """
        Returns the :tl:`User` or :tl:`Channel` that sent this object.
        It may be `None` if Telegram didn't send the sender.

        If you only need the ID, use `sender_id` instead.

        If you need to call a method which needs
        this chat, use `input_sender` instead.

        If you're using `telethon.events`, use `get_sender()` instead.
        """
        return self._sender

    async def get_sender(self):
        """
        Returns `sender`, but will make an API call to find the
        sender unless it's already cached.

        If you only need the ID, use `sender_id` instead.

        If you need to call a method which needs
        this sender, use `get_input_sender()` instead.
        """
        # ``sender.min`` is present both in :tl:`User` and :tl:`Channel`.
        # It's a flag that will be set if only minimal information is
        # available (such as display name, but username may be missing),
        # in which case we want to force fetch the entire thing because
        # the user explicitly called a method. If the user is okay with
        # cached information, they may use the property instead.
        if (self._sender is None or getattr(self._sender, 'min', None)) \
                and await self.get_input_sender():
            # self.get_input_sender may refresh in which case the sender may no longer be min
            # However it could still incur a cost so the cheap check is done twice instead.
            if self._sender is None or getattr(self._sender, 'min', None):
                try:
                    self._sender =\
                        await self._client.get_entity(self._input_sender)
                except ValueError:
                    await self._refetch_sender()
        return self._sender

    @property
    def input_sender(self):
        """
        This :tl:`InputPeer` is the input version of the user/channel who
        sent the message. Similarly to `input_chat
        <telethon.tl.custom.chatgetter.ChatGetter.input_chat>`, this doesn't
        have things like username or similar, but still useful in some cases.

        Note that this might not be available if the library can't
        find the input chat, or if the message a broadcast on a channel.
        """
        if self._input_sender is None and self._sender_id and self._client:
            try:
                self._input_sender = \
                    self._client._entity_cache[self._sender_id]
            except KeyError:
                pass
        return self._input_sender

    async def get_input_sender(self):
        """
        Returns `input_sender`, but will make an API call to find the
        input sender unless it's already cached.
        """
        if self.input_sender is None and self._sender_id and self._client:
            await self._refetch_sender()
        return self._input_sender

    @property
    def sender_id(self):
        """
        Returns the marked sender integer ID, if present.

        If there is a sender in the object, `sender_id` will *always* be set,
        which is why you should use it instead of `sender.id <sender>`.
        """
        return self._sender_id

    async def _refetch_sender(self):
        """
        Re-fetches sender information through other means.
        """
