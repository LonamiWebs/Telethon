"""
Several extensions Python is missing, such as a proper class to handle a TCP
communication with support for cancelling the operation, and an utility class
to read arbitrary binary data in a more comfortable way, with int/strings/etc.
"""
from .binaryreader import BinaryReader
from .tcpclient import TcpClient
