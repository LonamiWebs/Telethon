"""
This module contains several classes regarding network, low level connection
with Telegram's servers and the protocol used (TCP full, abridged, etc.).
"""
from .mtprotoplainsender import MTProtoPlainSender
from .authenticator import do_authentication
from .mtprotosender import MTProtoSender
from .codec import BaseCodec, FullCodec, IntermediateCodec, AbridgedCodec
from .connection import BaseConnection, AsyncioConnection
