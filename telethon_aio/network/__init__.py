"""
This module contains several classes regarding network, low level connection
with Telegram's servers and the protocol used (TCP full, abridged, etc.).
"""
from .mtproto_plain_sender import MtProtoPlainSender
from .authenticator import do_authentication
from .mtproto_sender import MtProtoSender
from .connection import Connection, ConnectionMode
