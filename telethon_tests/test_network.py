import random
import socket
import threading
import unittest

import telethon.network.authenticator as authenticator
from telethon.extensions import TcpClient
from telethon.network import Connection


def run_server_echo_thread(port):
    def server_thread():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', port))
            s.listen(1)
            connection, address = s.accept()
            with connection:
                data = connection.recv(16)
                connection.send(data)

    server = threading.Thread(target=server_thread)
    server.start()


class NetworkTests(unittest.TestCase):

    @unittest.skip("test_tcp_client needs fix")
    def test_tcp_client(self):
        port = random.randint(50000, 60000)  # Arbitrary non-privileged port
        run_server_echo_thread(port)

        msg = b'Unit testing...'
        client = TcpClient()
        client.connect('localhost', port)
        client.write(msg)
        self.assertEqual(msg, client.read(15),
                         msg='Read message does not equal sent message')
        client.close()

    @unittest.skip("Some parameters changed, so IP doesn't go there anymore.")
    def test_authenticator(self):
        transport = Connection('149.154.167.91', 443)
        self.assertTrue(authenticator.do_authentication(transport))
        transport.close()
