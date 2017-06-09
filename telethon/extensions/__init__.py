"""
Several extensions Python is missing, such as a proper class to handle a TCP
communication with support for cancelling the operation, and an utility class
to work with arbitrary binary data in a more comfortable way (writing ints,
strings, bytes, etc.)
"""
from .binary_writer import BinaryWriter
from .binary_reader import BinaryReader
from .tcp_client import TcpClient