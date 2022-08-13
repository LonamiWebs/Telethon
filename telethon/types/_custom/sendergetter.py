import abc


class SenderGetter(abc.ABC):
    """
    Helper base class that introduces the sender-related properties and methods.

    The parent class must set both ``_sender`` and ``_client``.
    """
    @property
    def sender(self):
        """
        Returns the `User` or `Chat` who sent this object, or `None` if there is no sender.

        The sender of an event is only guaranteed to include the ``id``.
        If you need the sender to at least have basic information, use `get_sender` instead.

        Senders obtained through friendly methods (not events) will always have complete
        information (so there is no need to use `get_sender` or ``sender.fetch()``).
        """
        return self._sender

    async def get_sender(self):
        """
        Returns `sender`, but will make an API call to find the sender unless it's already cached.

        If you only need the ID, use `sender_id` instead.

        If you need to call a method which needs this sender, prefer `sender` instead.

        Telegram may send a "minimal" version of the sender to save on bandwidth when using events.
        If you need all the information about the sender upfront, you can use ``sender.fetch()``.

        .. code-block:: python

            @client.on(events.NewMessage)
            async def handler(event):
                # I only need the ID -> use sender_id
                sender_id = event.sender_id

                # I'm going to use the sender in a method -> use sender
                await client.send_message(event.sender, 'Hi!')

                # I need the sender's first name -> use get_sender
                sender = await event.get_sender()
                print(sender.first_name)

                # I want to see all the information about the sender -> use fetch
                sender = await event.sender.fetch()
                print(sender.stringify())

            # ...

            async for message in client.get_messages(chat):
                # Here there's no need to fetch the sender - get_messages already did
                print(message.sender.stringify())
        """
        raise RuntimeError('TODO fetch if it is tiny')

    @property
    def sender_id(self):
        """
        Alias for ``self.sender.id``, but checking if ``sender is not None`` first.
        """
        return self._sender.id if sender else None
