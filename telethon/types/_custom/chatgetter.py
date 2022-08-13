import abc

from ..._misc import utils
from ... import errors, _tl


class ChatGetter(abc.ABC):
    """
    Helper base class that introduces the chat-related properties and methods.

    The parent class must set both ``_chat`` and ``_client``.
    """
    @property
    def chat(self):
        """
        Returns the `User` or `Chat` who sent this object, or `None` if there is no chat.

        The chat of an event is only guaranteed to include the ``id``.
        If you need the chat to at least have basic information, use `get_chat` instead.

        Chats obtained through friendly methods (not events) will always have complete
        information (so there is no need to use `get_chat` or ``chat.fetch()``).
        """
        return self._chat

    async def get_chat(self):
        """
        Returns `chat`, but will make an API call to find the chat unless it's already cached.

        If you only need the ID, use `chat_id` instead.

        If you need to call a method which needs this chat, prefer `chat` instead.

        Telegram may send a "minimal" version of the chat to save on bandwidth when using events.
        If you need all the information about the chat upfront, you can use ``chat.fetch()``.

        .. code-block:: python

            @client.on(events.NewMessage)
            async def handler(event):
                # I only need the ID -> use chat_id
                chat_id = event.chat_id

                # I'm going to use the chat in a method -> use chat
                await client.send_message(event.chat, 'Hi!')

                # I need the chat's title -> use get_chat
                chat = await event.get_chat()
                print(chat.title)

                # I want to see all the information about the chat -> use fetch
                chat = await event.chat.fetch()
                print(chat.stringify())

            # ...

            async for message in client.get_messages(chat):
                # Here there's no need to fetch the chat - get_messages already did
                print(message.chat.stringify())
        """
        raise RuntimeError('TODO fetch if it is tiny')

    @property
    def chat_id(self):
        """
        Alias for ``self.chat.id``, but checking if ``chat is not None`` first.
        """
        return self._chat.id if self._chat else None
