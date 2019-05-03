"""
This module contains several classes regarding network, low level connection
with Telegram's servers and the protocol used (TCP full, abridged, etc.).
"""
from .mtprotoplainsender import MTProtoPlainSender
from .authenticator import do_authentication
from .mtprotosender import MTProtoSender
from .connection import (
    Connection,
    ConnectionTcpFull, ConnectionTcpIntermediate, ConnectionTcpAbridged,
    ConnectionTcpObfuscated, ConnectionTcpMTProxyAbridged,
    ConnectionTcpMTProxyIntermediate,
    ConnectionTcpMTProxyRandomizedIntermediate, ConnectionHttp, TcpMTProxy
)
