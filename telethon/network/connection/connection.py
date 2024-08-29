import abc
import asyncio
import socket
import sys

try:
    import ssl as ssl_mod
except ImportError:
    ssl_mod = None

try:
    import python_socks
except ImportError:
    python_socks = None

from ...errors import InvalidChecksumError, InvalidBufferError
from ... import helpers


class Connection(abc.ABC):
    """
    The `Connection` class is a wrapper around ``asyncio.open_connection``.

    Subclasses will implement different transport modes as atomic operations,
    which this class eases doing since the exposed interface simply puts and
    gets complete data payloads to and from queues.

    The only error that will raise from send and receive methods is
    ``ConnectionError``, which will raise when attempting to send if
    the client is disconnected (includes remote disconnections).
    """
    # this static attribute should be redefined by `Connection` subclasses and
    # should be one of `PacketCodec` implementations
    packet_codec = None

    def __init__(self, ip, port, dc_id, *, loggers, proxy=None, local_addr=None):
        self._ip = ip
        self._port = port
        self._dc_id = dc_id  # only for MTProxy, it's an abstraction leak
        self._log = loggers[__name__]
        self._proxy = proxy
        self._local_addr = local_addr
        self._reader = None
        self._writer = None
        self._connected = False
        self._send_task = None
        self._recv_task = None
        self._codec = None
        self._obfuscation = None  # TcpObfuscated and MTProxy
        self._send_queue = asyncio.Queue(1)
        self._recv_queue = asyncio.Queue(1)

    @staticmethod
    def _wrap_socket_ssl(sock):
        if ssl_mod is None:
            raise RuntimeError(
                'Cannot use proxy that requires SSL '
                'without the SSL module being available'
            )

        return ssl_mod.wrap_socket(
            sock,
            do_handshake_on_connect=True,
            ssl_version=ssl_mod.PROTOCOL_SSLv23,
            ciphers='ADH-AES256-SHA')

    @staticmethod
    def _parse_proxy(proxy_type, addr, port, rdns=True, username=None, password=None):
        if isinstance(proxy_type, str):
            proxy_type = proxy_type.lower()

        # Always prefer `python_socks` when available
        if python_socks:
            from python_socks import ProxyType

            # We do the check for numerical values here
            # to be backwards compatible with PySocks proxy format,
            # (since socks.SOCKS5 == 2, socks.SOCKS4 == 1, socks.HTTP == 3)
            if proxy_type == ProxyType.SOCKS5 or proxy_type == 2 or proxy_type == "socks5":
                protocol = ProxyType.SOCKS5
            elif proxy_type == ProxyType.SOCKS4 or proxy_type == 1 or proxy_type == "socks4":
                protocol = ProxyType.SOCKS4
            elif proxy_type == ProxyType.HTTP or proxy_type == 3 or proxy_type == "http":
                protocol = ProxyType.HTTP
            else:
                raise ValueError("Unknown proxy protocol type: {}".format(proxy_type))

            # This tuple must be compatible with `python_socks`' `Proxy.create()` signature
            return protocol, addr, port, username, password, rdns

        else:
            from socks import SOCKS5, SOCKS4, HTTP

            if proxy_type == 2 or proxy_type == "socks5":
                protocol = SOCKS5
            elif proxy_type == 1 or proxy_type == "socks4":
                protocol = SOCKS4
            elif proxy_type == 3 or proxy_type == "http":
                protocol = HTTP
            else:
                raise ValueError("Unknown proxy protocol type: {}".format(proxy_type))

            # This tuple must be compatible with `PySocks`' `socksocket.set_proxy()` signature
            return protocol, addr, port, rdns, username, password

    async def _proxy_connect(self, timeout=None, local_addr=None):
        if isinstance(self._proxy, (tuple, list)):
            parsed = self._parse_proxy(*self._proxy)
        elif isinstance(self._proxy, dict):
            parsed = self._parse_proxy(**self._proxy)
        else:
            raise TypeError("Proxy of unknown format: {}".format(type(self._proxy)))

        # Always prefer `python_socks` when available
        if python_socks:
            # python_socks internal errors are not inherited from
            # builtin IOError (just from Exception). Instead of adding those
            # in exceptions clauses everywhere through the code, we
            # rather monkey-patch them in place. Keep in mind that
            # ProxyError takes error_code as keyword argument.

            class ConnectionErrorExtra(ConnectionError):
                def __init__(self, message, error_code=None):
                    super().__init__(message)
                    self.error_code = error_code

            python_socks._errors.ProxyError = ConnectionErrorExtra
            python_socks._errors.ProxyConnectionError = ConnectionError
            python_socks._errors.ProxyTimeoutError = ConnectionError

            from python_socks.async_.asyncio import Proxy

            proxy = Proxy.create(*parsed)

            # WARNING: If `local_addr` is set we use manual socket creation, because,
            # unfortunately, `Proxy.connect()` does not expose `local_addr`
            # argument, so if we want to bind socket locally, we need to manually
            # create, bind and connect socket, and then pass to `Proxy.connect()` method.

            if local_addr is None:
                sock = await proxy.connect(
                    dest_host=self._ip,
                    dest_port=self._port,
                    timeout=timeout
                )
            else:
                # Here we start manual setup of the socket.
                # The `address` represents the proxy ip and proxy port,
                # not the destination one (!), because the socket
                # connects to the proxy server, not destination server.
                # IPv family is also checked on proxy address.
                if ':' in proxy.proxy_host:
                    mode, address = socket.AF_INET6, (proxy.proxy_host, proxy.proxy_port, 0, 0)
                else:
                    mode, address = socket.AF_INET, (proxy.proxy_host, proxy.proxy_port)

                # Create a non-blocking socket and bind it (if local address is specified).
                sock = socket.socket(mode, socket.SOCK_STREAM)
                sock.setblocking(False)
                sock.bind(local_addr)

                # Actual TCP connection is performed here.
                await asyncio.wait_for(
                    helpers.get_running_loop().sock_connect(sock=sock, address=address),
                    timeout=timeout
                )

                # As our socket is already created and connected,
                # this call sets the destination host/port and
                # starts protocol negotiations with the proxy server.
                sock = await proxy.connect(
                    dest_host=self._ip,
                    dest_port=self._port,
                    timeout=timeout,
                    _socket=sock
                )

        else:
            import socks

            # Here `address` represents destination address (not proxy), because of
            # the `PySocks` implementation of the connection routine.
            # IPv family is checked on proxy address, not destination address.
            if ':' in parsed[1]:
                mode, address = socket.AF_INET6, (self._ip, self._port, 0, 0)
            else:
                mode, address = socket.AF_INET, (self._ip, self._port)

            # Setup socket, proxy, timeout and bind it (if necessary).
            sock = socks.socksocket(mode, socket.SOCK_STREAM)
            sock.set_proxy(*parsed)
            sock.settimeout(timeout)

            if local_addr is not None:
                sock.bind(local_addr)

            # Actual TCP connection and negotiation performed here.
            await asyncio.wait_for(
                helpers.get_running_loop().sock_connect(sock=sock, address=address),
                timeout=timeout
            )

            sock.setblocking(False)

        return sock

    async def _connect(self, timeout=None, ssl=None):
        if self._local_addr is not None:
            # NOTE: If port is not specified, we use 0 port
            # to notify the OS that port should be chosen randomly
            # from the available ones.
            if isinstance(self._local_addr, tuple) and len(self._local_addr) == 2:
                local_addr = self._local_addr
            elif isinstance(self._local_addr, str):
                local_addr = (self._local_addr, 0)
            else:
                raise ValueError("Unknown local address format: {}".format(self._local_addr))
        else:
            local_addr = None

        if not self._proxy:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(
                    host=self._ip,
                    port=self._port,
                    ssl=ssl,
                    local_addr=local_addr
                ), timeout=timeout)
        else:
            # Proxy setup, connection and negotiation is performed here.
            sock = await self._proxy_connect(
                timeout=timeout,
                local_addr=local_addr
            )

            # Wrap socket in SSL context (if provided)
            if ssl:
                sock = self._wrap_socket_ssl(sock)

            self._reader, self._writer = await asyncio.open_connection(sock=sock)

        self._codec = self.packet_codec(self)
        self._init_conn()
        await self._writer.drain()

    async def connect(self, timeout=None, ssl=None):
        """
        Establishes a connection with the server.
        """
        await self._connect(timeout=timeout, ssl=ssl)
        self._connected = True

        loop = helpers.get_running_loop()
        self._send_task = loop.create_task(self._send_loop())
        self._recv_task = loop.create_task(self._recv_loop())

    async def disconnect(self):
        """
        Disconnects from the server, and clears
        pending outgoing and incoming messages.
        """
        if not self._connected:
            return

        self._connected = False

        await helpers._cancel(
            self._log,
            send_task=self._send_task,
            recv_task=self._recv_task
        )

        if self._writer:
            self._writer.close()
            if sys.version_info >= (3, 7):
                try:
                    await asyncio.wait_for(self._writer.wait_closed(), timeout=10)
                except asyncio.TimeoutError:
                    # See issue #3917. For some users, this line was hanging indefinitely.
                    # The hard timeout is not ideal (connection won't be properly closed),
                    # but the code will at least be able to procceed.
                    self._log.warning('Graceful disconnection timed out, forcibly ignoring cleanup')
                except Exception as e:
                    # Disconnecting should never raise. Seen:
                    # * OSError: No route to host and
                    # * OSError: [Errno 32] Broken pipe
                    # * ConnectionResetError
                    self._log.info('%s during disconnect: %s', type(e), e)

    def send(self, data):
        """
        Sends a packet of data through this connection mode.

        This method returns a coroutine.
        """
        if not self._connected:
            raise ConnectionError('Not connected')

        return self._send_queue.put(data)

    async def recv(self):
        """
        Receives a packet of data through this connection mode.

        This method returns a coroutine.
        """
        while self._connected:
            result, err = await self._recv_queue.get()
            if err:
                raise err
            if result:
                return result

        raise ConnectionError('Not connected')

    async def _send_loop(self):
        """
        This loop is constantly popping items off the queue to send them.
        """
        try:
            while self._connected:
                self._send(await self._send_queue.get())
                await self._writer.drain()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            if isinstance(e, IOError):
                self._log.info('The server closed the connection while sending')
            else:
                self._log.exception('Unexpected exception in the send loop')

            await self.disconnect()

    async def _recv_loop(self):
        """
        This loop is constantly putting items on the queue as they're read.
        """
        try:
            while self._connected:
                try:
                    data = await self._recv()
                except asyncio.CancelledError:
                    break
                except (IOError, asyncio.IncompleteReadError) as e:
                    self._log.warning('Server closed the connection: %s', e)
                    await self._recv_queue.put((None, e))
                    await self.disconnect()
                except InvalidChecksumError as e:
                    self._log.warning('Server response had invalid checksum: %s', e)
                    await self._recv_queue.put((None, e))
                except InvalidBufferError as e:
                    self._log.warning('Server response had invalid buffer: %s', e)
                    await self._recv_queue.put((None, e))
                except Exception as e:
                    self._log.exception('Unexpected exception in the receive loop')
                    await self._recv_queue.put((None, e))
                    await self.disconnect()
                else:
                    await self._recv_queue.put((data, None))
        finally:
            await self.disconnect()


    def _init_conn(self):
        """
        This method will be called after `connect` is called.
        After this method finishes, the writer will be drained.

        Subclasses should make use of this if they need to send
        data to Telegram to indicate which connection mode will
        be used.
        """
        if self._codec.tag:
            self._writer.write(self._codec.tag)

    def _send(self, data):
        self._writer.write(self._codec.encode_packet(data))

    async def _recv(self):
        return await self._codec.read_packet(self._reader)

    def __str__(self):
        return '{}:{}/{}'.format(
            self._ip, self._port,
            self.__class__.__name__.replace('Connection', '')
        )


class ObfuscatedConnection(Connection):
    """
    Base class for "obfuscated" connections ("obfuscated2", "mtproto proxy")
    """
    """
    This attribute should be redefined by subclasses
    """
    obfuscated_io = None

    def _init_conn(self):
        self._obfuscation = self.obfuscated_io(self)
        self._writer.write(self._obfuscation.header)

    def _send(self, data):
        self._obfuscation.write(self._codec.encode_packet(data))

    async def _recv(self):
        return await self._codec.read_packet(self._obfuscation)


class PacketCodec(abc.ABC):
    """
    Base class for packet codecs
    """

    """
    This attribute should be re-defined by subclass to define if some
    "magic bytes" should be sent to server right after connection is made to
    signal which protocol will be used
    """
    tag = None

    def __init__(self, connection):
        """
        Codec is created when connection is just made.
        """
        self._conn = connection

    @abc.abstractmethod
    def encode_packet(self, data):
        """
        Encodes single packet and returns encoded bytes.
        """
        raise NotImplementedError

    @abc.abstractmethod
    async def read_packet(self, reader):
        """
        Reads single packet from `reader` object that should have
        `readexactly(n)` method.
        """
        raise NotImplementedError
