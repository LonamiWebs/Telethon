import abc


class SenderGetter(abc.ABC):
    """
    Helper base class that introduces the `sender`, `input_sender`
    and `sender_id` properties and `get_sender` and `get_input_sender`
    methods.

    Subclasses **must** have the following private members: `_sender`,
    `_input_sender`, `_sender_id` and `_client`. As an end user, you
    should not worry about this.
    """
    @property
    def sender(self):
        """
        Returns the :tl:`User` that created this object. It may be ``None``
        if the object has no sender or if Telegram didn't send the sender.

        If you're using `telethon.events`, use `get_sender` instead.
        """
        return self._sender

    async def get_sender(self):
        """
        Returns `sender`, but will make an API call to find the
        sender unless it's already cached.
        """
        if self._sender is None and await self.get_input_sender():
            try:
                self._sender =\
                    await self._client.get_entity(self._input_sender)
            except ValueError:
                await self._reload_message()
        return self._sender

    @property
    def input_sender(self):
        """
        This :tl:`InputPeer` is the input version of the user who
        sent the message. Similarly to `input_chat`, this doesn't have
        things like username or similar, but still useful in some cases.

        Note that this might not be available if the library can't
        find the input chat, or if the message a broadcast on a channel.
        """
        if self._input_sender is None and self._sender_id:
            try:
                self._input_sender = self._client.session\
                    .get_input_entity(self._sender_id)
            except ValueError:
                pass
        return self._input_sender

    async def get_input_sender(self):
        """
        Returns `input_sender`, but will make an API call to find the
        input sender unless it's already cached.
        """
        if self.input_sender is None and self._sender_id:
            await self._refetch_sender()
        return self._input_sender

    @property
    def sender_id(self):
        """
        Returns the marked sender integer ID, if present.
        """
        return self._sender_id

    async def _refetch_sender(self):
        """
        Re-fetches sender information through other means.
        """
