import io
import struct

from .mtprotostate import MTProtoState
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

    async def send(self, data_list):
        """
        A list of serialized RPC queries as bytes must be given to be sent.
        Nested lists imply an order is required for the messages in them.
        Message containers will be used if there is more than one item.

        Returns ``(container_id, msg_ids)``.
        """
        data, container_id, msg_ids = self._pack_data_list(data_list)
        await self._connection.send(self._state.encrypt_message_data(data))
        return container_id, msg_ids

    async def recv(self):
        """
        Reads a single message from the network, decrypts it and returns it.
        """
        body = await self._connection.recv()
        return self._state.decrypt_message_data(body)

    def _pack_data_list(self, data_list):
        """
        A list of serialized RPC queries as bytes must be given to be packed.
        Nested lists imply an order is required for the messages in them.

        Returns ``(data, container_id, msg_ids)``.
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
        msg_ids = []
        buffer = io.BytesIO()
        for data in data_list:
            if not isinstance(data, list):
                msg_ids.append(self._state.write_data_as_message(buffer, data))
            else:
                last_id = None
                for d in data:
                    last_id = self._state.write_data_as_message(
                        buffer, d, after_id=last_id)
                    msg_ids.append(last_id)

        if len(msg_ids) == 1:
            container_id = None
        else:
            # Inlined code to pack several messages into a container
            #
            # TODO This part and encrypting data prepend a few bytes but
            # force a potentially large payload to be appended, which
            # may be expensive. Can we do better?
            data = struct.pack(
                '<Ii', MessageContainer.CONSTRUCTOR_ID, len(msg_ids)
            ) + buffer.getvalue()
            buffer = io.BytesIO()
            container_id = self._state.write_data_as_message(buffer, data)

        return buffer.getvalue(), container_id, msg_ids

    def __str__(self):
        return str(self._connection)
