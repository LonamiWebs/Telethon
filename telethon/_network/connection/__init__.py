from .connection import Connection
from .tcpfull import ConnectionTcpFull
from .tcpintermediate import ConnectionTcpIntermediate
from .tcpabridged import ConnectionTcpAbridged
from .tcpobfuscated import ConnectionTcpObfuscated
from .tcpmtproxy import (
    TcpMTProxy,
    ConnectionTcpMTProxyAbridged,
    ConnectionTcpMTProxyIntermediate,
    ConnectionTcpMTProxyRandomizedIntermediate
)
from .http import ConnectionHttp
