from ...utils import get_input_peer


class Forward:
    """
    Custom class that encapsulates a :tl:`MessageFwdHeader` providing an
    abstraction to easily access information like the original sender.

    Attributes:

        original_fwd (:tl:`MessageFwdHeader`):
            The original :tl:`MessageFwdHeader` instance.

        Any other attribute:
            Attributes not described here are the same as those available
            in the original :tl:`MessageFwdHeader`.
    """
    def __init__(self, client, original, entities):
        self.__dict__ = original.__dict__
        self._client = client
        self.original_fwd = original
        self._sender = entities.get(original.from_id)
        self._chat = entities.get(original.channel_id)

        self._input_sender =\
            get_input_peer(self._sender) if self._sender else None
        self._input_chat =\
            get_input_peer(self._chat) if self._chat else None

    # TODO The pattern to get sender and chat is very similar
    # and copy pasted in/to several places. Reuse the code.
    #
    # It could be an ABC with some ``resolve_sender`` abstract,
    # so every subclass knew what tricks it can make to get
    # the sender.

    @property
    def sender(self):
        """
        The :tl:`User` that sent the original message. This may be ``None``
        if it couldn't be found or the message wasn't forwarded from an user
        but instead was forwarded from e.g. a channel.
        """
        return self._sender

    async def get_sender(self):
        """
        Returns `sender` but will make an API if necessary.
        """
        if not self.sender and self.original_fwd.from_id:
            try:
                self._sender = await self._client.get_entity(
                    await self.get_input_sender())
            except ValueError:
                # TODO We could reload the message
                pass

        return self._sender

    @property
    def input_sender(self):
        """
        Returns the input version of `user`.
        """
        if not self._input_sender and self.original_fwd.from_id:
            try:
                self._input_sender = self._client.session.get_input_entity(
                    self.original_fwd.from_id)
            except ValueError:
                pass

        return self._input_sender

    async def get_input_sender(self):
        """
        Returns `input_sender` but will make an API call if necessary.
        """
        # TODO We could reload the message
        return self.input_sender

    @property
    def chat(self):
        """
        The :tl:`Channel` where the original message was sent. This may be
        ``None`` if it couldn't be found or the message wasn't forwarded
        from a channel but instead was forwarded from e.g. an user.
        """
        return self._chat

    async def get_chat(self):
        """
        Returns `chat` but will make an API if necessary.
        """
        if not self.chat and self.original_fwd.channel_id:
            try:
                self._chat = await self._client.get_entity(
                    await self.get_input_chat())
            except ValueError:
                # TODO We could reload the message
                pass

        return self._chat

    @property
    def input_chat(self):
        """
        Returns the input version of `chat`.
        """
        if not self._input_chat and self.original_fwd.channel_id:
            try:
                self._input_chat = self._client.session.get_input_entity(
                    self.original_fwd.channel_id)
            except ValueError:
                pass

        return self._input_chat

    async def get_input_chat(self):
        """
        Returns `input_chat` but will make an API call if necessary.
        """
        # TODO We could reload the message
        return self.input_chat
