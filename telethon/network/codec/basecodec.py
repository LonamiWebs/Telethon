import abc


class BaseCodec(abc.ABC):
    @staticmethod
    @abc.abstractmethod
    def header_length():
        """
        Returns the initial length of the header.
        """
        raise NotImplementedError

    @staticmethod
    @abc.abstractmethod
    def tag():
        """
        The bytes tag that identifies the codec.

        It may be ``None`` if there is no tag to send.

        The tag will be sent upon successful connections to the
        server so that it knows which codec we will be using next.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def encode_packet(self, data):
        """
        Encodes the given data with the current codec instance.

        Should return header + body.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def decode_header(self, header):
        """
        Decodes the header.

        Should return the length of the body as a positive number.

        If more data is needed, a ``-length`` should be returned, where
        ``length`` is how much more data is needed for the full header.
        """
        raise NotImplementedError

    def decode_body(self, header, body):
        """
        Decodes the body.

        The default implementation returns ``body``.
        """
        return body
