import io
import struct

from .mtprotostate import MTProtoState
from ..tl import TLRequest
from ..tl.core.messagecontainer import MessageContainer


class MTProtoLayer:
    """
    This class is the message encryption layer between the methods defined
    in the schema and the response objects. It also holds the necessary state
    necessary for this encryption to happen.

    The `connection` parameter is through which these messages will be sent
    and received.

    The `auth_key` must be a valid authorization key which will be used to
    encrypt these messages. This class is not responsible for generating them.
    """
    def __init__(self, connection, auth_key):
        self._connection = connection
        self._state = MTProtoState(auth_key)

    def connect(self):
        """
        Wrapper for ``self._connection.connect()``.
        """
        return self._connection.connect()

    def disconnect(self):
        """
        Wrapper for ``self._connection.disconnect()``.
        """
        self._connection.disconnect()

    async def send(self, state_list):
        """
        The list of `RequestState` that will be sent. They will
        be updated with their new message and container IDs.

        Nested lists imply an order is required for the messages in them.
        Message containers will be used if there is more than one item.
        """
        data = self._pack_state_list(state_list)
        await self._connection.send(self._state.encrypt_message_data(data))

    async def recv(self):
        """
        Reads a single message from the network, decrypts it and returns it.
        """
        body = await self._connection.recv()
        return self._state.decrypt_message_data(body)

    def _pack_state_list(self, state_list):
        """
        The list of `RequestState` that will be sent. They will
        be updated with their new message and container IDs.

        Packs all their serialized data into a message (possibly
        nested inside another message and message container) and
        returns the serialized message data.
        """
        # TODO write_data_as_message raises on invalid messages, handle it
        # TODO This method could be an iterator yielding messages while small
        # respecting the ``MessageContainer.MAXIMUM_SIZE`` limit.
        #
        # Note that the simplest case is writing a single query data into
        # a message, and returning the message data and ID. For efficiency
        # purposes this method supports more than one message and automatically
        # uses containers if deemed necessary.
        #
        # Technically the message and message container classes could be used
        # to store and serialize the data. However, to keep the context local
        # and relevant to the only place where such feature is actually used,
        # this is not done.
        n = 0
        buffer = io.BytesIO()
        for state in state_list:
            if not isinstance(state, list):
                n += 1
                state.msg_id = self._state.write_data_as_message(
                    buffer, state.data, isinstance(state.request, TLRequest))
            else:
                last_id = None
                for s in state:
                    n += 1
                    last_id = s.msg_id = self._state.write_data_as_message(
                        buffer, s.data, isinstance(s.request, TLRequest),
                        after_id=last_id)

        if n > 1:
            # Inlined code to pack several messages into a container
            #
            # TODO This part and encrypting data prepend a few bytes but
            # force a potentially large payload to be appended, which
            # may be expensive. Can we do better?
            data = struct.pack(
                '<Ii', MessageContainer.CONSTRUCTOR_ID, n
            ) + buffer.getvalue()
            buffer = io.BytesIO()
            container_id = self._state.write_data_as_message(
                buffer, data, content_related=False
            )
            for state in state_list:
                if not isinstance(state, list):
                    state.container_id = container_id
                else:
                    for s in state:
                        s.container_id = container_id

        return buffer.getvalue()

    def __str__(self):
        return str(self._connection)
