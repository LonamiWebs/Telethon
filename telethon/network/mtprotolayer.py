import io
import logging
import struct

from .mtprotostate import MTProtoState
from ..tl import TLRequest
from ..tl.core.tlmessage import TLMessage
from ..tl.core.messagecontainer import MessageContainer

__log__ = logging.getLogger(__name__)


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

    def connect(self, timeout=None):
        """
        Wrapper for ``self._connection.connect()``.
        """
        return self._connection.connect(timeout=timeout)

    def disconnect(self):
        """
        Wrapper for ``self._connection.disconnect()``.
        """
        self._connection.disconnect()

    def reset_state(self):
        self._state = MTProtoState(self._state.auth_key)

    async def send(self, state_list):
        """
        The list of `RequestState` that will be sent. They will
        be updated with their new message and container IDs.

        Nested lists imply an order is required for the messages in them.
        Message containers will be used if there is more than one item.
        """
        for data in filter(None, self._pack_state_list(state_list)):
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
        # Note that the simplest case is writing a single query data into
        # a message, and returning the message data and ID. For efficiency
        # purposes this method supports more than one message and automatically
        # uses containers if deemed necessary.
        #
        # Technically the message and message container classes could be used
        # to store and serialize the data. However, to keep the context local
        # and relevant to the only place where such feature is actually used,
        # this is not done.
        #
        # When iterating over the state_list there are two branches, one
        # being just a state and the other being a list so the inner states
        # depend on each other. In either case, if the packed size exceeds
        # the maximum container size, it must be sent. This code is non-
        # trivial so it has been factored into an inner function.
        #
        # A new buffer instance will be used once the size should be "flushed"
        buffer = io.BytesIO()
        # The batch of requests sent in a single buffer-flush. We need to
        # remember which states were written to set their container ID.
        batch = []
        # The currently written size. Reset when it exceeds the maximum.
        size = 0

        def write_state(state, after_id=None):
            nonlocal buffer, batch, size
            if state:
                batch.append(state)
                size += len(state.data) + TLMessage.SIZE_OVERHEAD

            # Flush whenever the current size exceeds the maximum,
            # or if there's no state, which indicates force flush.
            if not state or size > MessageContainer.MAXIMUM_SIZE:
                size -= MessageContainer.MAXIMUM_SIZE
                if len(batch) > 1:
                    # Inlined code to pack several messages into a container
                    data = struct.pack(
                        '<Ii', MessageContainer.CONSTRUCTOR_ID, len(batch)
                    ) + buffer.getvalue()
                    buffer = io.BytesIO()
                    container_id = self._state.write_data_as_message(
                        buffer, data, content_related=False
                    )
                    for s in batch:
                        s.container_id = container_id

                # At this point it's either a single msg or a msg + container
                data = buffer.getvalue()
                __log__.debug('Packed %d message(s) in %d bytes for sending',
                              len(batch), len(data))
                batch.clear()
                buffer = io.BytesIO()
                return data

            if not state:
                return  # Just forcibly flushing

            # If even after flushing it still exceeds the maximum size,
            # this message payload cannot be sent. Telegram would forcibly
            # close the connection, and the message would never be confirmed.
            if size > MessageContainer.MAXIMUM_SIZE:
                state.future.set_exception(
                    ValueError('Request payload is too big'))
                return

            # This is the only requirement to make this work.
            state.msg_id = self._state.write_data_as_message(
                buffer, state.data, isinstance(state.request, TLRequest),
                after_id=after_id
            )
            __log__.debug('Assigned msg_id = %d to %s (%x)',
                          state.msg_id, state.request.__class__.__name__,
                          id(state.request))

        # TODO Yield in the inner loop -> Telegram "Invalid container". Why?
        for state in state_list:
            if not isinstance(state, list):
                yield write_state(state)
            else:
                after_id = None
                for s in state:
                    yield write_state(s, after_id)
                    after_id = s.msg_id

        yield write_state(None)

    def __str__(self):
        return str(self._connection)
