import hashlib

from .tcpobfuscated import ConnectionTcpObfuscated


class ConnectionTcpMTProxy(ConnectionTcpObfuscated):
    """
    Wrapper around the "obfuscated2" mode that modifies it a little and allows
    user to connect to the Telegram proxy servers commonly known as MTProxy.
    Implemented very ugly due to the leaky abstractions in Telethon networking
    classes that should be refactored later (TODO).

    .. warning::

        The support for MTProtoProxies class is **EXPERIMENTAL** and prone to
        be changed. You shouldn't be using this class yet.
    """
    @staticmethod
    def address_info(proxy_info):
        if proxy_info is None:
            raise ValueError("No proxy info specified for MTProxy connection")
        return proxy_info[:2]

    def __init__(self, ip, port, dc_id, *, loop, loggers, proxy=None):
        proxy_host, proxy_port = self.address_info(proxy)
        super().__init__(
            proxy_host, proxy_port, dc_id, loop=loop, loggers=loggers)

        # TODO: Implement the dd-secret secure mode (adds noise to fool DPI)
        self._secret = bytes.fromhex(proxy[2])
        if len(self._secret) != 16:
            raise ValueError(
                "MTProxy secure mode is not implemented for now"
                if len(self._secret) == 17 and self._secret[0] == 0xDD else
                "MTProxy secret must be a hex-string representing 16 bytes"
            )

    def _compose_key(self, data):
        return hashlib.sha256(data + self._secret).digest()

    def _compose_tail(self, data):
        dc_id_bytes = self._dc_id.to_bytes(2, "little", signed=True)
        return super()._compose_tail(data[:60] + dc_id_bytes + data[62:])
